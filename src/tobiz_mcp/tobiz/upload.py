"""Подготовка файла изображения к загрузке: путь в inbox или base64 из аргумента."""

from __future__ import annotations

import base64
import binascii
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..errors import (
    BAD_ARGUMENT,
    INBOX_NOT_FOUND,
    UPLOAD_INVALID,
    UPLOAD_TOO_LARGE,
    TobizError,
)

MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


@dataclass
class PreparedImage:
    file_name: str
    content: bytes
    content_type: str
    width: int | None = None
    height: int | None = None

    @property
    def size(self) -> int:
        return len(self.content)

    @property
    def aspect_ratio(self) -> float | None:
        return round(self.width / self.height, 4) if self.width and self.height else None

    def metadata(self, filename: str | None = None) -> dict[str, object]:
        return {"filename": filename or self.file_name, "width": self.width,
                "height": self.height, "aspect_ratio": self.aspect_ratio,
                "content_type": self.content_type, "bytes": self.size}


def _sniff(content: bytes, file_name: str) -> str:
    for magic, mime in MAGIC:
        if content.startswith(magic):
            return mime
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    head = content[:400].lstrip()
    if head.startswith(b"<svg") or head.startswith(b"<?xml"):
        return "image/svg+xml"
    # никаких догадок по расширению: имя файла подделывается тривиально
    return "application/octet-stream"


def _dimensions(content: bytes, content_type: str) -> tuple[int | None, int | None]:
    if content_type == "image/png" and len(content) >= 24:
        return struct.unpack(">II", content[16:24])
    if content_type == "image/gif" and len(content) >= 10:
        return struct.unpack("<HH", content[6:10])
    if content_type == "image/jpeg":
        index = 2
        sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
               0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while index + 8 < len(content):
            if content[index] != 0xFF:
                index += 1
                continue
            while index < len(content) and content[index] == 0xFF:
                index += 1
            if index >= len(content):
                break
            marker = content[index]
            index += 1
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if index + 2 > len(content):
                break
            length = int.from_bytes(content[index:index + 2], "big")
            if marker in sof and index + 7 <= len(content):
                return (int.from_bytes(content[index + 5:index + 7], "big"),
                        int.from_bytes(content[index + 3:index + 5], "big"))
            if length < 2:
                break
            index += length
    if content_type == "image/webp" and len(content) >= 30:
        chunk = content[12:16]
        if chunk == b"VP8X":
            return (1 + int.from_bytes(content[24:27], "little"),
                    1 + int.from_bytes(content[27:30], "little"))
        if chunk == b"VP8L" and content[20] == 0x2F:
            b0, b1, b2, b3 = content[21:25]
            return 1 + (b0 | ((b1 & 0x3F) << 8)), 1 + ((b1 >> 6) | (b2 << 2) | ((b3 & 0x0F) << 10))
        marker = content.find(b"\x9d\x01\x2a", 20)
        if marker >= 0 and marker + 7 <= len(content):
            return (int.from_bytes(content[marker + 3:marker + 5], "little") & 0x3FFF,
                    int.from_bytes(content[marker + 5:marker + 7], "little") & 0x3FFF)
    if content_type == "image/svg+xml":
        head = content[:4096].decode("utf-8", "ignore")
        width = re.search(r'\bwidth=["\'](\d+(?:\.\d+)?)(?:px)?["\']', head, re.I)
        height = re.search(r'\bheight=["\'](\d+(?:\.\d+)?)(?:px)?["\']', head, re.I)
        if width and height:
            return int(float(width.group(1))), int(float(height.group(1)))
        viewbox = re.search(
            r'\bviewBox=["\']\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)\s*["\']',
            head, re.I)
        if viewbox:
            return int(float(viewbox.group(1))), int(float(viewbox.group(2)))
    return None, None


def prepare(config: Config, path: str | None, content_base64: str | None,
            file_name: str | None = None) -> PreparedImage:
    if bool(path) == bool(content_base64):
        raise TobizError(
            BAD_ARGUMENT,
            "Укажите ровно одно из полей: path или content_base64",
            "path — файл внутри /data/inbox, content_base64 — содержимое изображения",
        )
    if path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = config.inbox_dir / candidate
        try:
            resolved = candidate.resolve()
            root = config.inbox_dir.resolve()
        except OSError as exc:
            raise TobizError(INBOX_NOT_FOUND, f"Не удалось открыть путь: {exc}")
        if root not in resolved.parents and resolved != root:
            raise TobizError(
                INBOX_NOT_FOUND,
                "Файл вне каталога /data/inbox",
                f"Положите файл в {config.inbox_dir} (том смонтирован в контейнер)",
            )
        if not resolved.is_file():
            raise TobizError(INBOX_NOT_FOUND, f"Файл не найден: {path}")
        content = resolved.read_bytes()
        name = file_name or resolved.name
    else:
        try:
            content = base64.b64decode(str(content_base64), validate=True)
        except (binascii.Error, ValueError):
            raise TobizError(BAD_ARGUMENT, "content_base64 не декодируется",
                             "Передайте корректный base64 без переводов строк")
        name = file_name or "upload.png"

    suffix = Path(name).suffix.lower() or ".png"
    if suffix not in ALLOWED_SUFFIXES:
        raise TobizError(
            UPLOAD_INVALID,
            f"Расширение {suffix} не поддерживается",
            f"Разрешены: {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )
    limit = config.max_upload_mb * 1024 * 1024
    if len(content) > limit:
        raise TobizError(
            UPLOAD_TOO_LARGE,
            f"Файл {len(content)} байт больше лимита {config.max_upload_mb} МБ",
            "Увеличьте TOBIZ_MAX_UPLOAD_MB или уменьшите файл",
        )
    if not content:
        raise TobizError(UPLOAD_INVALID, "Пустой файл")
    content_type = _sniff(content, name)
    if content_type == "application/octet-stream":
        raise TobizError(
            UPLOAD_INVALID,
            "Файл не распознан как изображение",
            "Поддерживаются PNG, JPEG, WEBP, GIF, SVG",
        )
    width, height = _dimensions(content, content_type)
    return PreparedImage(file_name=name, content=content, content_type=content_type,
                         width=width, height=height)
