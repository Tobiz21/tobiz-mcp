"""Conservative content-only batches; native structure is immutable."""
import copy
import hashlib
import json
import re
from html import unescape

from ..errors import BAD_ARGUMENT, CONFLICT, TobizError

TEXT = re.compile(r"^(title\d*|sub_title|subtitle\d*|text\d*|txt\d*|descr\d*|description|price\d*|phone\d*|address\d*|logo_text|alt\d*|placeholder|popup_form_title|popup_thanks_title|popup_thanks_text|form_title|form_text)$")
IMAGE = re.compile(r"^(image\d*(?:_\d+)?|bg_image|logo_img)$")
LINK = re.compile(r"^(link\d*|logo_url|link_(?:vk|tg|youtube|rutube|whatsup|vimeo|zen|max))$")


def fields(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"form_html", "html", "code", "css", "cache", "styles"} or key.startswith("form_html"):
                continue
            pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if isinstance(child, str):
                kind = "image" if IMAGE.fullmatch(key) else "text" if TEXT.fullmatch(key) else "link" if LINK.fullmatch(key) else None
                if kind:
                    yield pointer, kind, child
            else:
                yield from fields(child, pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from fields(child, path + f"/{index}")


def fingerprint(draft):
    data = {"meta": draft.page_meta, "blocks": [
        [bid, draft.blocks[bid].type_id, draft.blocks[bid].deleted, draft.blocks[bid].values]
        for bid in draft.order]}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def content_map(draft):
    blocks = []
    for bid in draft.order:
        b = draft.blocks[bid]
        if b.deleted:
            continue
        blocks.append({"block_id": bid, "type_id": b.type_id,
                       "fields": [{"path": p, "kind": k, "value": v} for p, k, v in fields(b.values)]})
    return {"hash": fingerprint(draft), "blocks": blocks,
            "note": "Only listed string fields are editable; layout, arrays and custom code are not replaced."}


def _plain(value):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _field_profile(path, kind, block_type):
    key = path.rsplit("/", 1)[-1]
    if kind == "image":
        if key == "logo_img":
            return {"role": "logo", "image_hint": "brand artwork; preserve transparency and proportions"}
        if key == "bg_image":
            return {"role": "background", "image_hint": "wide image with a safe text area; usually at least 1900px"}
        if block_type == "130":
            return {"role": "catalog_image", "image_hint": "same aspect ratio and scale as sibling cards"}
        if block_type == "144":
            return {"role": "gallery_image", "image_hint": "use the block image_size ratio consistently"}
        return {"role": "content_image", "image_hint": "match the native slot ratio and subject"}
    if kind == "link":
        return {"role": "link"}
    if "/btn" in path and key == "title":
        return {"role": "button", "recommended_max_chars": 28, "mobile_lines": "1-2"}
    if re.fullmatch(r"title", key):
        return {"role": "section_title", "recommended_max_chars": 70, "mobile_lines": "2-4"}
    if re.fullmatch(r"title\d+", key):
        return {"role": "card_title", "recommended_max_chars": 55, "mobile_lines": "1-3"}
    if key == "sub_title" or re.fullmatch(r"subtitle\d*", key):
        return {"role": "subtitle", "recommended_max_chars": 140, "mobile_lines": "2-5"}
    if re.fullmatch(r"(txt|descr|description)\d*", key):
        return {"role": "body", "recommended_max_chars": 320}
    return {"role": "text"}


def passport(draft):
    blocks, warnings = [], []
    for index, bid in enumerate(draft.order):
        block = draft.blocks[bid]
        if block.deleted:
            continue
        profiled = []
        for path, kind, value in fields(block.values):
            profile = _field_profile(path, kind, block.type_id)
            plain = _plain(value) if kind == "text" else value
            item = {"path": path, "kind": kind, **profile}
            if kind == "text":
                item["current_chars"] = len(plain)
            limit = profile.get("recommended_max_chars")
            if limit and len(plain) > limit:
                warnings.append({"block_id": bid, "path": path, "code": "text_over_recommended",
                                 "current_chars": len(plain), "recommended_max_chars": limit})
            profiled.append(item)
        blocks.append({"block_index": index, "block_id": bid, "type_id": block.type_id,
                       "fields": profiled})
    return {"hash": fingerprint(draft), "blocks": blocks, "warnings": warnings,
            "note": "Text limits are conservative design guidance, not TOBIZ technical limits."}


def compact_blueprint(passport_data, content_data):
    """Convert the verbose passport into an editable recipe and grouped media plan."""
    values = {
        (str(block.get("block_id")), field.get("path")): field.get("value", "")
        for block in content_data.get("blocks", [])
        for field in block.get("fields", [])
    }
    recipe_slots = []
    media_groups = {}
    block_types = []
    for block in passport_data.get("blocks", []):
        block_index = block.get("block_index")
        block_id = str(block.get("block_id"))
        block_type = str(block.get("type_id"))
        block_types.append(block_type)
        for field in block.get("fields", []):
            path = str(field.get("path") or "")
            kind = field.get("kind")
            current = values.get((block_id, path), "")
            if kind in {"text", "link"} and str(current).strip():
                recipe_slots.append({
                    "block_index": block_index,
                    "path": path,
                    "kind": kind,
                    "role": field.get("role"),
                    "current": current,
                    **({"recommended_max_chars": field["recommended_max_chars"]}
                       if field.get("recommended_max_chars") else {}),
                })
            elif kind == "image":
                canonical = re.sub(r"_\d+$", "", path)
                key = (block_index, block_type, canonical, field.get("role"), field.get("image_hint"))
                group = media_groups.setdefault(key, {
                    "block_index": block_index,
                    "type_id": block_type,
                    "path_pattern": canonical,
                    "role": field.get("role"),
                    "image_hint": field.get("image_hint"),
                    "slots": 0,
                })
                group["slots"] += 1
    return {
        "hash": passport_data.get("hash"),
        "recipe": {"types": block_types, "slots": recipe_slots},
        "photo_slots": list(media_groups.values()),
        "text_slots": len(recipe_slots),
        "image_slots": sum(item["slots"] for item in media_groups.values()),
        "image_groups": len(media_groups),
    }


def recipe_edits(draft, recipe):
    """Bind positional content slots to a copy with different native block IDs."""
    active = [draft.blocks[bid] for bid in draft.order if not draft.blocks[bid].deleted]
    if not isinstance(recipe, dict) or recipe.get('types') != [b.type_id for b in active]:
        raise TobizError(CONFLICT, 'Template block sequence differs; no edits applied')
    edits = []
    for slot in recipe.get('slots', []):
        if not isinstance(slot, dict) or type(slot.get('block_index')) is not int:
            raise TobizError(BAD_ARGUMENT, 'Slot requires integer block_index')
        index = slot['block_index']
        if not 0 <= index < len(active):
            raise TobizError(BAD_ARGUMENT, 'Slot index outside template')
        edits.append({'block_id': active[index].block_id, 'path': slot.get('path'), 'value': slot.get('value')})
    return edits


def prepare(draft, edits, image=None, expected_hash=None):
    if expected_hash and expected_hash != fingerprint(draft):
        raise TobizError(CONFLICT, "Content changed; read tobiz_page_content again")
    if not isinstance(edits, list):
        raise TobizError(BAD_ARGUMENT, "edits must be a list")
    if image is not None and (not isinstance(image, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.(?:png|jpg|jpeg|webp)", image)):
        raise TobizError(BAD_ARGUMENT, "image must be a filename returned by tobiz_upload_image")
    candidate = copy.deepcopy(draft)
    lookup = {(bid, p): (kind, value) for bid in draft.order if not draft.blocks[bid].deleted
              for p, kind, value in fields(draft.blocks[bid].values)}
    operations = {}
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) - {"block_id", "path", "value"}:
            raise TobizError(BAD_ARGUMENT, "Each edit needs block_id, path and value")
        key = (str(edit.get("block_id", "")), edit.get("path"))
        if not isinstance(key[1], str) or key not in lookup or not isinstance(edit.get("value"), str):
            raise TobizError(BAD_ARGUMENT, f"Not an existing content string: {key}")
        if key in operations:
            raise TobizError(BAD_ARGUMENT, f"Duplicate edit: {key}")
        kind = lookup[key][0]
        value = edit["value"]
        if kind == "link" and value and not (value.startswith(("https://", "http://", "tel:", "mailto:", "#", "/"))):
            raise TobizError(BAD_ARGUMENT, "Unsupported link protocol")
        if kind == "text" and re.search(r"<\s*(script|iframe|style|object)\b|\bon\w+\s*=|javascript:", value, re.I):
            raise TobizError(BAD_ARGUMENT, "Custom executable markup is not content")
        if kind == "image" and value and not re.fullmatch(r"[A-Za-z0-9_. -]+\.(?:png|jpg|jpeg|webp|gif)", value):
            raise TobizError(BAD_ARGUMENT, "Image must be a native filename")
        operations[key] = value
    if image:
        for key, (kind, value) in lookup.items():
            if kind == "image" and value and value != "null.png":
                if key in operations and operations[key] != image:
                    raise TobizError(BAD_ARGUMENT, "Explicit image edit conflicts with global replacement")
                operations[key] = image
    changed = []
    for (bid, path), value in operations.items():
        if lookup[(bid, path)][1] == value:
            continue
        node = candidate.blocks[bid].values
        parts = [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]
        for part in parts[:-1]:
            node = node[int(part)] if isinstance(node, list) else node[part]
        node[parts[-1]] = value
        if path not in candidate.blocks[bid].changed_paths:
            candidate.blocks[bid].changed_paths.append(path)
        changed.append({"block_id": bid, "path": path, "kind": lookup[(bid, path)][0]})
    return candidate, changed
