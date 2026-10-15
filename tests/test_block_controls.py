from __future__ import annotations

from types import SimpleNamespace

from tobiz_mcp.domain.blocks import control_schema, normalize_values, validate_values


def test_control_schema_returns_checkbox_dependencies_and_labeled_options() -> None:
    block_type = SimpleNamespace(
        values={"show_btns": 1, "mode": "count3", "title": "Demo"},
        settings=[
            {"name": "show_btns", "type": "checkbox", "title": "Показывать кнопки"},
            {"name": "mode", "type": "select", "title": "Количество в ряд",
             "require": {"show_btns": 1}, "vars": [
                 {"val": "count3", "title": "Три"},
                 {"val": "count4", "title": "Четыре"},
             ]},
            {"name": "title", "type": "text", "title": "Заголовок"},
        ],
    )

    controls = control_schema(block_type)

    assert [item["name"] for item in controls] == ["show_btns", "mode"]
    assert controls[0]["default"] == 1
    assert controls[1]["require"] == {"show_btns": 1}
    assert controls[1]["options"] == [
        {"value": "count3", "title": "Три"},
        {"value": "count4", "title": "Четыре"},
    ]


def test_control_schema_can_return_only_checkboxes_or_all_fields() -> None:
    block_type = SimpleNamespace(
        values={"enabled": 0, "color": "#fff", "text": "Demo"},
        settings=[
            {"name": "enabled", "type": "checkbox", "title": "Включить"},
            {"name": "color", "type": "color", "title": "Цвет"},
            {"name": "text", "type": "text", "title": "Текст"},
        ],
    )

    assert [item["name"] for item in control_schema(block_type, "checkbox")] == ["enabled"]
    assert [item["name"] for item in control_schema(block_type, "all")] == [
        "enabled", "color", "text",
    ]


def test_normalize_values_accepts_human_friendly_native_settings() -> None:
    block_type = SimpleNamespace(
        type_id="130", values={}, vars=[], settings=[
            {"name": "items_count", "type": "select", "vars": [
                {"val": "count3"}, {"val": "count4"}, {"val": "count5"},
            ]},
            {"name": "padd_top", "type": "int"},
        ],
    )

    normalized = normalize_values(block_type, {"items_count": 4, "padd_top": "55px"})

    assert normalized == {"items_count": "count4", "padd_top": "55"}
    validate_values(block_type, normalized)
