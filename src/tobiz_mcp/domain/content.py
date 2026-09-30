"""Conservative content-only batches; native structure is immutable."""
import copy
import hashlib
import json
import re

from ..errors import BAD_ARGUMENT, CONFLICT, TobizError

TEXT = re.compile(r"^(title\d*|sub_title|text\d*|txt\d*|descr\d*|description|price\d*|phone\d*|address\d*|logo_text|alt\d*|placeholder|popup_form_title|popup_thanks_title|popup_thanks_text)$")
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
