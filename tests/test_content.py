import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tobiz_mcp.domain.content import content_map, fingerprint, prepare
from tobiz_mcp.domain.draft import Draft, DraftBlock, DraftStore
from tobiz_mcp.errors import TobizError
from tobiz_mcp.tools import register


def sample():
    return Draft('1', '2', blocks={'3': DraftBlock('3', '130', {
        'title': 'Old', 'image': 'old.jpg', 'items': [{'title': 'Item', 'image': 'null.png'}],
        'columns': 4, 'html': '<p>untouched</p>', 'styles': {'title': 'skip'},
    })}, order=['3'])


def test_map_and_structure():
    draft = sample()
    assert len(content_map(draft)['blocks'][0]['fields']) == 4
    candidate, changes = prepare(draft, [{'block_id': '3', 'path': '/items/0/title', 'value': 'New'}], 'gray.png')
    assert len(changes) == 2
    assert draft.blocks['3'].values['image'] == 'old.jpg'
    assert candidate.blocks['3'].values['items'][0]['image'] == 'null.png'
    assert candidate.blocks['3'].values['columns'] == 4
    assert candidate.order == draft.order


@pytest.mark.parametrize('path', ['/columns', '/missing', '/styles/title', '/html'])
def test_invalid_batch_is_atomic(path):
    draft = sample()
    before = copy.deepcopy(draft)
    with pytest.raises(TobizError):
        prepare(draft, [{'block_id': '3', 'path': '/title', 'value': 'New'},
                        {'block_id': '3', 'path': path, 'value': 'bad'}])
    assert draft == before


def test_hash_and_duplicates():
    draft = sample()
    edit = {'block_id': '3', 'path': '/title', 'value': 'New'}
    with pytest.raises(TobizError):
        prepare(draft, [edit], expected_hash='stale')
    with pytest.raises(TobizError):
        prepare(draft, [edit, edit])
    assert prepare(draft, [], expected_hash=fingerprint(draft))[1] == []


@pytest.mark.asyncio
async def test_preview_then_one_save():
    draft = sample()
    store = DraftStore()
    store.put(draft)
    service = SimpleNamespace(config=SimpleNamespace(read_only=False, dry_run=False),
                              drafts=store, resolve_page=AsyncMock(return_value=('1', None)),
                              draft=AsyncMock(return_value=draft), save_page=AsyncMock(return_value={'status': 'saved'}))
    functions = {}
    class MCP:
        def tool(self, name, description):
            def capture(fn):
                functions[name] = fn
                return fn
            return capture
    register(MCP(), service)
    arguments = dict(project_id='1', page_id='2', expected_hash=fingerprint(draft),
                     edits=[{'block_id': '3', 'path': '/title', 'value': 'New'}])
    result = await functions['tobiz_apply_content'](**arguments)
    assert result['ok'] and result['data']['preview']
    assert store.get('1', '2') == draft
    service.save_page.assert_not_called()
    result = await functions['tobiz_apply_content'](**arguments, apply=True, save=True)
    assert result['ok'] and result['data']['saved']
    assert store.get('1', '2').blocks['3'].values['title'] == 'New'
    service.save_page.assert_awaited_once()
