from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from tobiz_mcp.config import Config
from tobiz_mcp.tobiz.upload import prepare


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/"
    "h6Y3vQAAAABJRU5ErkJggg=="
)


def config(tmp_path: Path) -> Config:
    return Config(email=None, password=None, inbox_dir=tmp_path)


def test_png_metadata_is_measured_from_bytes(tmp_path: Path) -> None:
    image = prepare(config(tmp_path), None, base64.b64encode(PNG).decode(), "pixel.png")
    assert (image.width, image.height, image.aspect_ratio) == (1, 1, 1.0)
    assert image.metadata()["content_type"] == "image/png"
    assert image.metadata()["sha256"] == hashlib.sha256(PNG).hexdigest()


def test_jpeg_dimensions_are_read_from_sof_segment(tmp_path: Path) -> None:
    jpeg = (b"\xff\xd8" + b"\xff\xc0\x00\x11\x08" +
            (720).to_bytes(2, "big") + (1280).to_bytes(2, "big") + b"\x00" * 12)
    image = prepare(config(tmp_path), None, base64.b64encode(jpeg).decode(), "wide.jpg")
    assert (image.width, image.height) == (1280, 720)
    assert image.aspect_ratio == 1.7778


def test_webp_vp8x_dimensions_are_read_from_canvas_header(tmp_path: Path) -> None:
    width, height = 1920, 1080
    webp = (b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"VP8X" +
            b"\x0a\x00\x00\x00" + b"\x00\x00\x00\x00" +
            (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little"))
    image = prepare(config(tmp_path), None, base64.b64encode(webp).decode(), "hero.webp")
    assert (image.width, image.height) == (width, height)
    assert image.aspect_ratio == 1.7778


def test_svg_viewbox_is_used_when_absolute_dimensions_are_absent(tmp_path: Path) -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"></svg>'
    image = prepare(config(tmp_path), None, base64.b64encode(svg).decode(), "art.svg")
    assert (image.width, image.height, image.aspect_ratio) == (640, 360, 1.7778)
