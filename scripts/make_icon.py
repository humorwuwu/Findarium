#!/usr/bin/env python
"""Generate the Findarium app icon (PNG + macOS .icns + frontend favicons).

Run from the project root with:  uv run python scripts/make_icon.py
The design is drawn programmatically so it can be tweaked and regenerated.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
PUBLIC = ROOT / "frontend" / "public"

SIZE = 2048  # supersampled working canvas
FINAL = 1024

INDIGO = (67, 56, 202)  # #4338CA
CYAN = (6, 182, 212)  # #06B6D4
INK = (2, 6, 23)
BLUE = (37, 99, 235)
LIGHT_BLUE = (125, 211, 252)
SLATE = (148, 163, 184)


def _rounded_mask(size: int, margin_ratio: float, radius_ratio: float) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    margin = int(size * margin_ratio)
    radius = int(size * radius_ratio)
    ImageDraw.Draw(mask).rounded_rectangle(
        [margin, margin, size - margin, size - margin], radius=radius, fill=255
    )
    return mask


def _gradient(size: int) -> Image.Image:
    yy, xx = np.mgrid[0:size, 0:size]
    t = (xx + yy) / (2 * size - 2)
    t = t * t * (3 - 2 * t)  # smoothstep
    channels = []
    for start, end in zip(INDIGO, CYAN, strict=True):
        channels.append((start + (end - start) * t).astype(np.uint8))
    alpha = np.full_like(channels[0], 255)
    return Image.fromarray(np.dstack([*channels, alpha]), "RGBA")


def _top_highlight(size: int, mask: Image.Image) -> Image.Image:
    yy, xx = np.mgrid[0:size, 0:size]
    dist = np.sqrt((xx - 0.26 * size) ** 2 + (yy - 0.18 * size) ** 2) / (0.72 * size)
    alpha = (np.clip(1 - dist, 0, 1) ** 2 * 78).astype(np.uint8)
    white = np.full_like(alpha, 255)
    layer = Image.fromarray(np.dstack([white, white, white, alpha]), "RGBA")
    transparent = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return Image.composite(layer, transparent, mask)


def _card(size: int) -> tuple[Image.Image, tuple[int, int]]:
    width = int(size * 0.42)
    height = int(size * 0.52)
    radius = int(width * 0.10)
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle(
        [0, 0, width - 1, height - 1], radius=radius, fill=(255, 255, 255, 248)
    )
    line_x = int(width * 0.15)
    line_h = max(6, int(height * 0.055))
    line_full = int(width * 0.70)
    lines = [
        (0.20, 1.00, (BLUE[0], BLUE[1], BLUE[2], 240)),
        (0.37, 0.80, (BLUE[0], BLUE[1], BLUE[2], 190)),
        (0.54, 0.92, (BLUE[0], BLUE[1], BLUE[2], 215)),
        (0.71, 0.55, (SLATE[0], SLATE[1], SLATE[2], 200)),
    ]
    for offset, factor, color in lines:
        y = int(height * offset)
        draw.rounded_rectangle(
            [line_x, y, line_x + int(line_full * factor), y + line_h],
            radius=line_h // 2,
            fill=color,
        )
    # A small accent block, like a highlighted search hit.
    hit_y = int(height * 0.50)
    draw.rounded_rectangle(
        [line_x + int(line_full * 0.18), hit_y, line_x + int(line_full * 0.72), hit_y + line_h],
        radius=line_h // 2,
        fill=(250, 204, 21, 235),
    )
    return card, (int(size * 0.17), int(size * 0.16))


def _shadow(size: int, card: Image.Image, position: tuple[int, int]) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pad = 90
    blob = Image.new("RGBA", (card.width + pad, card.height + pad), (0, 0, 0, 0))
    ImageDraw.Draw(blob).rounded_rectangle(
        [pad // 2, pad // 2, pad // 2 + card.width, pad // 2 + card.height],
        radius=int(card.width * 0.10),
        fill=(*INK, 130),
    )
    layer.alpha_composite(blob, (position[0] - pad // 2, position[1] - pad // 2 + 18))
    return layer.filter(ImageFilter.GaussianBlur(30))


def _lens(size: int) -> tuple[Image.Image, Image.Image]:
    center = (int(size * 0.66), int(size * 0.66))
    radius = int(size * 0.165)
    ring = int(size * 0.052)
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(
        [
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        ],
        fill=(*INK, 120),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))

    lens = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(lens)
    handle_start = (
        center[0] + int(radius * 0.70),
        center[1] + int(radius * 0.70),
    )
    handle_end = (
        center[0] + int(radius * 1.42),
        center[1] + int(radius * 1.42),
    )
    draw.line(
        [handle_start, handle_end],
        fill=(*INK, 55),
        width=int(size * 0.092),
    )
    draw.line(
        [handle_start, handle_end],
        fill=(255, 255, 255, 255),
        width=int(size * 0.072),
    )
    # Dark outer edge keeps the white ring readable over the white card.
    draw.ellipse(
        [
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        ],
        outline=(*INK, 70),
        width=ring + int(size * 0.012),
    )
    draw.ellipse(
        [
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        ],
        outline=(255, 255, 255, 255),
        width=ring,
    )
    glass = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glass).ellipse(
        [
            center[0] - radius + ring,
            center[1] - radius + ring,
            center[0] + radius - ring,
            center[1] + radius - ring,
        ],
        fill=(*LIGHT_BLUE, 80),
    )
    return shadow, Image.alpha_composite(glass, lens)


def render() -> Image.Image:
    mask = _rounded_mask(SIZE, 0.055, 0.225)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(_gradient(SIZE), (0, 0), mask)
    canvas = Image.alpha_composite(canvas, _top_highlight(SIZE, mask))

    card, position = _card(SIZE)
    canvas = Image.alpha_composite(canvas, _shadow(SIZE, card, position))
    rotated = card.rotate(-7, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(
        rotated,
        (position[0] - (rotated.width - card.width) // 2, position[1] - (rotated.height - card.height) // 2),
    )

    lens_shadow, lens = _lens(SIZE)
    canvas = Image.alpha_composite(canvas, lens_shadow)
    canvas = Image.alpha_composite(canvas, lens)
    return canvas.resize((FINAL, FINAL), Image.LANCZOS)


ICONSET = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def write_outputs(image: Image.Image) -> None:
    PACKAGING.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    icon_png = PACKAGING / "icon.png"
    image.save(icon_png)
    image.resize((64, 64), Image.LANCZOS).save(PUBLIC / "icon-64.png")
    image.resize((64, 64), Image.LANCZOS).save(PUBLIC / "favicon.png")
    image.resize((180, 180), Image.LANCZOS).save(PUBLIC / "apple-touch-icon.png")

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "Findarium.iconset"
        iconset.mkdir()
        for name, size in ICONSET.items():
            image.resize((size, size), Image.LANCZOS).save(iconset / name)
        icns = PACKAGING / "AppIcon.icns"
        try:
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
                check=True,
            )
            print(f"wrote {icns}")
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"iconutil failed ({exc}); PNG outputs are still available")


def main() -> None:
    image = render()
    write_outputs(image)
    print(f"wrote {PACKAGING / 'icon.png'} and frontend/public assets")


if __name__ == "__main__":
    main()
