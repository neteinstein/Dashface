"""Frames for the README video (docs/video/dashface.*), drawn with the real preview renderer.

Usage (from the repo root):
    python3 tools/generate_watchface.py      # icons + build/preview/icons
    python3 tools/video/make_frames.py       # writes build/video/frames.json + face SVGs
    node tools/video/render_video.js         # renders frames, encodes MP4 / GIF / JPG

Every face state comes from generate_watchface.build_preview_svg, so the video always shows the
current design. Scenes, captions and timing are defined in SCENES below.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import generate_watchface as g  # noqa: E402

FPS = 30
DURATION = 22.0
OUT = ROOT / "build" / "video"
ICONS = ROOT / "build" / "preview" / "icons"
DRAWABLES = ROOT / "watchface" / "src" / "main" / "res" / "drawable-nodpi"

BASE = {name: m for name, m in g.METRICS.items()}


def ease(t: float) -> float:
    """easeInOutCubic on 0..1."""
    t = min(max(t, 0.0), 1.0)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def face_svg(*, time="10:08", battery=0.72, steps=0.48, step_count=4821, stress=0.27, heart=62,
             celsius=33.6, layout=None, accent=None, ambient=False, meetings=None) -> str:
    """One face state as SVG (sample data patched into the generator's preview values)."""
    g.METRICS["battery"] = dataclasses.replace(BASE["battery"], preview_value=battery,
                                               preview_text=f"{round(battery * 100)}%")
    g.METRICS["steps"] = dataclasses.replace(BASE["steps"], preview_value=steps,
                                             preview_text=str(step_count))
    g.METRICS["stress"] = dataclasses.replace(BASE["stress"], preview_value=stress,
                                              preview_text=str(round(stress * 100)))
    g.METRICS["heart"] = dataclasses.replace(BASE["heart"], preview_value=min(max((heart - 40) / 140, 0), 1),
                                             preview_text=str(round(heart)))
    g.THERMO_PREVIEW = (celsius, f"{celsius:.1f}°")
    svg = g.build_preview_svg(layout=layout or g.DEFAULT_LAYOUT, single_accent=accent,
                              ambient=ambient, meetings=meetings, icons_dir="icons/")
    hh, mm = time.split(":")
    svg = svg.replace('letter-spacing="-3">10</text>', f'letter-spacing="-3">{hh}</text>', 1)
    svg = svg.replace('letter-spacing="-3">08</text>', f'letter-spacing="-3">{mm}</text>', 1)
    ensure_icons(svg)
    return svg


def ensure_icons(svg: str) -> None:
    """Writes any pre-tinted icon the SVG references that the generator did not produce."""
    from PIL import Image

    for name, col in set(re.findall(r'icons/(ic_[a-z0-9_]+?)_([0-9A-F]{6})\.png', svg)):
        out = ICONS / f"{name}_{col}.png"
        if out.exists():
            continue
        base = Image.open(DRAWABLES / f"{name}.png").convert("RGBA")
        tinted = Image.new("RGBA", base.size, tuple(int(col[i:i + 2], 16) for i in (0, 2, 4)) + (255,))
        tinted.putalpha(base.getchannel("A"))
        tinted.save(out)


# Captions: (kicker, HTML headline, small print). <b> = accent blue, <o>/<r> = orange/red,
# <a> = current accent color.
CAPTIONS = {
    "intro": ("Wear OS watch face", "Your day<br>at a glance,<br><b>on your wrist.</b>", ""),
    "brand": ("", '<span class="brand">Dashface</span>',
              "A battery-friendly Wear OS watch face.<br>Battery, steps, stress and heart rate hug the bezel."),
    "calendar": ("Calendar", "Your <b>next<br>meetings</b>,<br>under the time.", ""),
    "custom": ("Customize", "Any metric,<br>any corner.<br><a>Five accents.</a>", ""),
    "thermo": ("Skin temperature", "<b>Cool blue</b>,<br><o>warm orange</o>,<br><r>red.</r>",
               "On watches that measure it."),
    "battery": ("Battery &amp; privacy", "No internet.<br>No analytics.<br><b>Built to sip power.</b>", ""),
    "outro": ("", '<span class="brand">Dashface</span>',
              'For Wear OS 5 and later.<br><span class="mono">github.com/neteinstein/Dashface</span>'),
}

# Scenes: (start, end, caption, camera zoom, camera focus y offset in face px).
SCENES = [
    (0.0, 3.6, "intro", 1.0, 0),
    (3.6, 7.0, "brand", 1.0, 0),
    (7.0, 11.0, "calendar", 1.3, -40),
    (11.0, 14.2, "custom", 1.0, 0),
    (14.2, 17.2, "thermo", 1.35, 70),
    (17.2, 19.4, "battery", 1.0, 0),
    (19.4, 22.0, "outro", 1.0, 0),
]
ACCENT_HEX = {a[0]: g.hex6(a[2]) for a in g.ACCENTS}


def state_at(t: float) -> tuple[dict, str]:
    """Face parameters and caption accent color at time t."""
    accent_col = ACCENT_HEX["cyan"]
    if t < 3.6:  # bars and trails sweep in
        k = ease_out((t - 0.3) / 2.2)
        return dict(battery=0.72 * k, steps=0.48 * k, step_count=round(4821 * k), stress=0.27 * k,
                    heart=40 + 22 * k), accent_col
    if t < 7.0:
        return {}, accent_col
    if t < 8.2:
        return dict(time="10:29"), accent_col
    if t < 9.6:
        return dict(time="10:30", meetings=(("Now", "Team standup"), ("13:00", "Design review"))), accent_col
    if t < 11.0:
        return dict(time="18:05", battery=0.41, steps=0.93, step_count=9341, stress=0.34, heart=69,
                    meetings=(("", "No more meetings today"),)), accent_col
    custom = dict(time="12:14", battery=0.64, steps=0.61, step_count=6127)
    if t < 11.8:
        return custom, accent_col
    if t < 12.6:
        return dict(custom, layout=g.FLAVORS[1][2]), accent_col
    if t < 13.4:
        return dict(custom, accent="white"), ACCENT_HEX["white"]
    if t < 14.2:
        return dict(custom, accent="amber"), ACCENT_HEX["amber"]
    if t < 17.2:
        k = ease((t - 14.6) / 2.2)
        return dict(time="12:40", battery=0.60, steps=0.66, step_count=6629,
                    celsius=round(lerp(30.7, 36.4, k), 1)), accent_col
    if t < 19.4:
        return dict(time="23:12", battery=0.38, ambient=True), accent_col
    return {}, accent_col


def camera_at(t: float) -> tuple[float, float]:
    """(zoom, focus y) eased between scenes over 0.8 s around each boundary."""
    for i, (s0, s1, _, z, fy) in enumerate(SCENES):
        if s0 <= t < s1 or i == len(SCENES) - 1:
            pz, pfy = (SCENES[i - 1][3], SCENES[i - 1][4]) if i else (z, fy)
            k = ease((t - s0 + 0.4) / 0.8)
            return lerp(pz, z, k), lerp(pfy, fy, k)
    return 1.0, 0.0


def caption_at(t: float) -> tuple[str, float, float]:
    """(caption id, opacity, slide px)."""
    for s0, s1, cap, *_ in SCENES:
        if s0 <= t < s1 or (cap == "outro" and t >= s0):
            fade_in = ease_out((t - s0) / 0.45) if s0 > 0 else ease_out((t - 0.1) / 0.5)
            fade_out = 1.0 if cap == "outro" else ease_out((s1 - t) / 0.3)
            op = min(fade_in, fade_out)
            return cap, op, (1 - fade_in) * 24
    return "outro", 1.0, 0.0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    faces: dict[str, str] = {}
    frames = []
    for i in range(int(DURATION * FPS)):
        t = i / FPS
        params, accent_col = state_at(t)
        svg = face_svg(**params)
        key = hashlib.sha1(svg.encode()).hexdigest()[:12]
        if key not in faces:
            faces[key] = svg
            (OUT / f"face_{key}.svg").write_text(svg)
        zoom, focus = camera_at(t)
        cap, op, slide = caption_at(t)
        frames.append(dict(face=key, zoom=round(zoom, 4), focus=round(focus, 2), caption=cap,
                           op=round(op, 3), slide=round(slide, 2), accent=accent_col))
    (OUT / "frames.json").write_text(json.dumps(dict(fps=FPS, frames=frames, captions=CAPTIONS)))
    print(f"{len(frames)} frames, {len(faces)} distinct faces")
    return 0


if __name__ == "__main__":
    sys.exit(main())
