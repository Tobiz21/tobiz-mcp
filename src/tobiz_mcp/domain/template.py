"""Safe, native-only preparation of copied TOBIZ templates."""
import copy
import re

from ..errors import CONFLICT, TobizError
from .content import fingerprint

SOCIALS = {
    "vk": "link_vk", "whatsup": "link_whatsup", "youtube": "link_youtube",
    "vimeo": "link_vimeo", "zen": "link_zen", "rutube": "link_rutube",
    "tg": "link_tg", "max": "link_max", "ins": "link_ins", "fb": "link_fb",
}
DEMO = re.compile(
    r"Название товара|Подробное описание продукта|Плиточные работы|Тариф [А-ЯA-Z]|"
    r"Замеры с ювелирной точностью|\+7\s*800\s*333\s*22\s*33",
    re.I,
)
DEMO_LINK = re.compile(r"^https?://(?:www\.)?tobiz\.net(?:/|$)", re.I)


def _set(block, path, value, changes, reason):
    node = block.values
    parts = path.strip("/").split("/")
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    key = int(parts[-1]) if isinstance(node, list) else parts[-1]
    if node[key] == value:
        return
    node[key] = value
    if path not in block.changed_paths:
        block.changed_paths.append(path)
    changes.append({"block_id": block.block_id, "path": path, "value": value, "reason": reason})


def _walk(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            yield child_path, key, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}/{index}")


def prepare_template(draft, expected_hash=None):
    """Return a prepared copy, deterministic fixes, and unresolved warnings."""
    if expected_hash and expected_hash != fingerprint(draft):
        raise TobizError(CONFLICT, "Template changed; read tobiz_page_content again")
    candidate = copy.deepcopy(draft)
    changes, warnings = [], []
    anchors = {
        str(block.values.get("anchor"))
        for block in candidate.blocks.values()
        if not block.deleted and block.values.get("anchor")
    }
    for bid in candidate.order:
        block = candidate.blocks[bid]
        if block.deleted:
            continue
        values = block.values

        for social, link_key in SOCIALS.items():
            show_key = f"show_{social}"
            link = str(values.get(link_key, "")).strip()
            if values.get(show_key) in (1, "1", True) and (not link or DEMO_LINK.match(link)):
                reason = "hide_demo_social" if link else "hide_empty_social"
                _set(block, f"/{show_key}", 0, changes, reason)

        form_title = str(values.get("form_title", ""))
        if (values.get("show_form_title") in (1, "1", True)
                and values.get("back_dark") in (1, "1", True)
                and form_title
                and not re.search(r"color\s*:\s*(?:#fff(?:fff)?|white)\b", form_title, re.I)):
            cleaned = re.sub(r"color\s*:\s*(?:#000(?:000)?|black)\s*;?", "", form_title,
                             flags=re.I)
            _set(block, "/form_title", f'<span style="color:#ffffff">{cleaned}</span>',
                 changes, "keep_form_title_visible_on_dark_background")

        if block.type_id == "144" and values.get("arr1"):
            has_labels = any(
                str(item.get("image_box", {}).get("title", "")).strip()
                or str(item.get("image_box", {}).get("descr", "")).strip()
                for item in values["arr1"] if isinstance(item, dict)
            )
            if has_labels:
                if "fix_txt_img" in values:
                    _set(block, "/fix_txt_img", 1, changes, "keep_gallery_text_visible")
                if "active_off" in values:
                    _set(block, "/active_off", 1, changes, "disable_hover_only_content")

        forms = {key for key, child in values.items()
                 if re.fullmatch(r"form\d+", key) and isinstance(child, list) and child}
        for path, key, child in list(_walk(values)):
            if not re.fullmatch(r"btn\d+", key) or not isinstance(child, dict):
                continue
            link = str(child.get("link", "")).strip()
            if link.startswith("#") and link[1:] not in anchors:
                form_key = key.replace("btn", "form")
                if form_key in forms and "use_form" in child:
                    _set(block, f"{path}/link", "", changes, "replace_broken_anchor_with_native_form")
                    _set(block, f"{path}/use_form", "1", changes, "replace_broken_anchor_with_native_form")
                else:
                    warnings.append({"block_id": bid, "path": f"{path}/link",
                                     "code": "missing_anchor", "value": link})

        for path, key, child in _walk(values):
            if isinstance(child, str) and DEMO.search(child):
                warnings.append({"block_id": bid, "path": path, "code": "demo_content"})

    return candidate, changes, warnings
