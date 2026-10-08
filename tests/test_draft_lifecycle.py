from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tobiz_mcp.domain.draft import Draft, DraftStore
from tobiz_mcp.service import Service
from tobiz_mcp.errors import TobizError


def run_mocked(coroutine):
    # All I/O is AsyncMock; these unit tests must not suspend for real I/O.
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coroutine.close()
    raise AssertionError("Unexpected real async I/O in unit test")


def loaded():
    store = DraftStore()
    draft = store.create("1", "2", {})
    store.load_blocks(draft, [
        {"id": "10", "type_id": "226", "data_obj": {"title": "old"}},
        {"id": "11", "type_id": "226", "sort_id": 1, "data_obj": {}},
    ])
    return store, draft


def test_saved_created_block_becomes_clean():
    _, draft = loaded()
    draft.add_created("12", "226", {})
    assert draft.has_changes
    draft.mark_saved()
    assert not draft.has_changes
    assert not draft.changed_blocks
    assert not draft.blocks["12"].to_dict()["changed"]


def test_move_and_delete_are_changes_until_saved():
    _, draft = loaded()
    draft.move_block("11", position=0)
    assert draft.has_changes
    draft.mark_saved()
    assert not draft.has_changes
    draft.remove_block("10")
    assert draft.has_changes
    draft.mark_saved()
    assert not draft.has_changes


def test_clean_read_refreshes_but_dirty_read_preserves_edits(monkeypatch):
    service = Service.__new__(Service)
    service.drafts, old = loaded()
    service.config = SimpleNamespace(lp_base=lambda _: "https://example.invalid")
    service._editor_page_meta = AsyncMock(return_value={"title": "fresh"})
    service.client = SimpleNamespace(editor_ajax=AsyncMock(return_value=SimpleNamespace(ok=True)))
    monkeypatch.setattr("tobiz_mcp.service.blocks_from", lambda _: [
        {"id": "10", "type_id": "226", "data_obj": {"title": "external edit"}},
    ])
    fresh = run_mocked(service.draft("1", "2"))
    assert fresh.blocks["10"].values["title"] == "external edit"
    assert fresh is not old
    fresh.blocks["10"].values["title"] = "local edit"
    assert run_mocked(service.draft("1", "2")) is fresh
    assert service.client.editor_ajax.await_count == 1


def test_failed_refresh_preserves_existing_draft():
    service = Service.__new__(Service)
    service.drafts, old = loaded()
    service.config = SimpleNamespace(lp_base=lambda _: "https://example.invalid")
    service._editor_page_meta = AsyncMock(return_value={"title": "new"})
    service.client = SimpleNamespace(editor_ajax=AsyncMock(side_effect=RuntimeError("offline")))
    with pytest.raises(RuntimeError):
        run_mocked(service.draft("1", "2"))
    assert service.drafts.get("1", "2") is old
    assert old.page_meta == {}


@pytest.mark.parametrize("external", [False, True])
def test_remote_conflict_preserves_local_changes(monkeypatch, external):
    service = Service.__new__(Service)
    service.drafts, draft = loaded()
    draft.blocks["10"].values["title"] = "local edit"
    draft.add_created("12", "226", {})
    service.config = SimpleNamespace(lp_base=lambda _: "https://example.invalid")
    service.client = SimpleNamespace(editor_ajax=AsyncMock(return_value=SimpleNamespace(ok=True)))
    monkeypatch.setattr("tobiz_mcp.service.blocks_from", lambda _: [
        {"id": "10", "type_id": "226", "data_obj": {"title": "external" if external else "old"}},
        {"id": "11", "type_id": "226", "sort_id": 1, "data_obj": {}},
        {"id": "12", "type_id": "226", "sort_id": 2, "data_obj": {}},
    ])
    if external:
        with pytest.raises(TobizError):
            run_mocked(service._check_remote_blocks(draft))
    else:
        remote = run_mocked(service._check_remote_blocks(draft))
        assert remote.blocks["10"].values["title"] == "old"
    assert draft.blocks["10"].values["title"] == "local edit"
    assert draft.has_changes


def test_backup_roundtrip_and_scope(tmp_path):
    service = Service.__new__(Service)
    service.config = SimpleNamespace(audit_dir=tmp_path)
    _, draft = loaded()
    backup = service._write_page_backup(draft)
    listing = service.list_page_backups("1", "2")
    assert listing["backups"][0]["backup_id"] == backup["backup_id"]
    stored = (tmp_path / "backups" / "1" / "2" / f"{backup['backup_id']}.json")
    body = __import__("json").loads(stored.read_text(encoding="utf-8"))
    assert body["project_id"] == "1"
    assert [item["id"] for item in body["payload"]["userBlocks"]] == ["10", "11"]


def test_restore_requires_confirmation_and_rejects_path(tmp_path):
    service = Service.__new__(Service)
    service.config = SimpleNamespace(audit_dir=tmp_path, read_only=False)
    service.client = SimpleNamespace()
    with pytest.raises(TobizError):
        run_mocked(service.restore_page_backup("1", "2", "missing", confirm=False))
    with pytest.raises(TobizError):
        run_mocked(service.restore_page_backup("1", "2", "../backup", confirm=True))
