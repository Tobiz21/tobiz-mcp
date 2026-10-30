import json

import pytest

from tobiz_mcp.tobiz.envelope import decode_json_response, parse


def test_plain_json_contract_is_unchanged() -> None:
    payload = decode_json_response('{"status":"OK","data":{"id":1}}')
    assert payload == {"status": "OK", "data": {"id": 1}}


def test_utf8_bom_before_json_is_accepted() -> None:
    envelope = parse('\ufeff  {"status":"OK","html":"ready"}')
    assert envelope.ok
    assert envelope.payload["html"] == "ready"


@pytest.mark.parametrize("prefix", [
    "PHP Warning: Undefined array key project_id in /var/www/ajax.php on line 42\n",
    "<br><b>Deprecated</b>: Creation of dynamic property Item::$id is deprecated in "
    "/var/www/items.php on line 17<br>\n",
    "Notice: Undefined variable: result in /var/www/editor.php on line 9\n",
])
def test_php82_diagnostic_prefix_before_json_is_recovered(prefix: str) -> None:
    payload = decode_json_response(prefix + '{"status":"OK","data":[]}')
    assert payload == {"status": "OK", "data": []}


@pytest.mark.parametrize("body", [
    "<html><body>502 Bad Gateway</body></html>",
    '<script>window.data={"status":"OK"}</script>',
    'random prefix {"status":"OK"}',
    'PHP Warning: broken response without JSON',
])
def test_non_json_or_arbitrary_html_is_still_rejected(body: str) -> None:
    with pytest.raises(json.JSONDecodeError):
        decode_json_response(body)


def test_envelope_uses_recovered_php82_json() -> None:
    envelope = parse(
        "PHP Deprecated: legacy call in /var/www/editor.php on line 3\n"
        '{"status":"OK","respons":"Сохранил"}'
    )
    assert envelope.ok
    assert envelope.message == "Сохранил"
