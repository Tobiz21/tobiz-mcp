from __future__ import annotations

from types import SimpleNamespace

from tobiz_mcp.domain.draft import Draft, DraftBlock
from tobiz_mcp.domain.layout import prepare, registry


def block_type(type_id, settings, title="Cards"):
    return SimpleNamespace(type_id=type_id, settings=settings, title=title)


def test_registry_extracts_safe_and_mobile_layout_controls():
    types = {
        "130": block_type("130", [
            {"name": "flex_fix", "type": "checkbox", "title": "Выровнять по кнопке"},
            {"name": "btn_move", "type": "select", "title": "Анимация кнопки при наведении",
             "vars": [{"val": "none", "title": "Нет"}, {"val": "pulse", "title": "Пульсация"}]},
            {"name": "mobile_columns", "type": "select", "title": "Колонки в мобильной версии",
             "vars": [{"val": "1", "title": "Одна"}, {"val": "2", "title": "Две"}]},
            {"name": "unrelated", "type": "text", "title": "Произвольное поле"},
        ]),
    }
    result = registry(types)
    assert result["type_count"] == 1
    assert result["control_count"] == 3
    controls = {item["name"]: item for item in result["types"][0]["controls"]}
    assert controls["flex_fix"]["safe_automatic"] is True
    assert controls["btn_move"]["recommended_value"] == "none"
    assert controls["mobile_columns"]["role"] == "mobile_layout"
    assert controls["mobile_columns"]["safe_automatic"] is False


def test_prepare_repairs_only_controls_declared_by_native_type():
    draft = Draft("1", "2", blocks={
        "42": DraftBlock("42", "130", {"flex_fix": 0, "btn_up": 1,
                                          "btn_move": "pulse", "btn_align": "left"}),
    }, order=["42"])
    types = {"130": block_type("130", [
        {"name": "flex_fix", "type": "checkbox", "title": "Выровнять по кнопке"},
        {"name": "btn_up", "type": "checkbox", "title": "Появление кнопки"},
        {"name": "btn_move", "type": "select", "title": "Анимация кнопки при наведении",
         "vars": [{"val": "none", "title": "Нет"}, {"val": "pulse", "title": "Пульсация"}]},
        {"name": "btn_align", "type": "select", "title": "Выравнивание кнопки",
         "vars": [{"val": "center", "title": "По центру"}]},
    ])}
    audit = {"block_evidence": {"42": [
        {"code": "card_heights_misaligned"}, {"code": "card_button_hidden_initially"},
        {"code": "card_button_alignment_mismatch"},
    ]}}
    candidate, changes, warnings = prepare(draft, audit, types)
    assert candidate.blocks["42"].values == {
        "flex_fix": 1, "btn_up": 0, "btn_move": "none", "btn_align": "center"}
    assert len(changes) == 4
    assert warnings == []
    assert draft.blocks["42"].values["flex_fix"] == 0


def test_prepare_reports_mobile_candidates_without_guessing_value():
    draft = Draft("1", "2", blocks={"42": DraftBlock("42", "130", {
        "mobile_columns": "2"})}, order=["42"])
    types = {"130": block_type("130", [{
        "name": "mobile_columns", "type": "select", "title": "Колонки в мобильной версии",
        "vars": [{"val": "1", "title": "Одна"}, {"val": "2", "title": "Две"}],
    }])}
    candidate, changes, warnings = prepare(draft, {"block_evidence": {
        "42": [{"code": "cards_not_stacked_mobile"}]}}, types)
    assert changes == []
    assert candidate.blocks["42"].values["mobile_columns"] == "2"
    assert warnings[0]["candidates"][0]["name"] == "mobile_columns"
    assert warnings[0]["candidates"][0]["options"][0]["value"] == "1"
