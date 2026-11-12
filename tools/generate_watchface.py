#!/usr/bin/env python3
"""Generates the Dashface Watch Face Format XML, raster assets and preview SVGs.

The watch face has 4 corners x 4 metrics x 2 color modes, so writing the XML by
hand would mean ~32 near-identical arc blocks. This script is the single source
of truth for geometry and colors; its outputs are committed so the Android build
does not depend on Python.

Usage (from the repo root):
    python3 tools/generate_watchface.py

Outputs:
    watchface/src/main/res/raw/watchface.xml
    watchface/src/main/res/drawable-nodpi/*.png   (metric + weather icons)
    build/preview/*.svg                            (rendered to PNG by tools/render_previews.js)
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "watchface" / "src" / "main" / "res"
PREVIEW_DIR = ROOT / "build" / "preview"
WEATHER_SRC = ROOT / "third_party" / "weather-icons"

# --------------------------------------------------------------------------------------
# Geometry (450 x 450 canvas, angles in degrees, 0 = 12 o'clock, clockwise positive)
# --------------------------------------------------------------------------------------
SIZE = 450
C = SIZE / 2
STROKE = 14
ARC_D = 420  # arc diameter (bezel inset = (450 - 420) / 2 = 15 => 8 px gap + half stroke)
ARC_R = ARC_D / 2
GAP = 6  # degrees kept free on each side of 12/3/6/9 o'clock
SPAN = 90 - 2 * GAP  # 78 degrees per corner arc

PROVIDER_PKG = "org.neteinstein.dashface.provider"


@dataclass(frozen=True)
class Corner:
    id: str
    label: str
    start: float  # clockwise start angle of the arc
    end: float  # clockwise end angle of the arc
    anchor_at_end: bool  # True => the fill is anchored at `end` and grows toward `start`
    badge_angle: float  # where the icon + value badge sits (inside the ring)
    slot_id: int

    @property
    def anchor(self) -> float:
        return self.end if self.anchor_at_end else self.start

    @property
    def far(self) -> float:
        return self.start if self.anchor_at_end else self.end


# Top arcs grow from 12 o'clock outward, bottom arcs grow from 6 o'clock outward.
CORNERS = [
    Corner("tl", "Top left", 270 + GAP, 360 - GAP, True, 285, 0),
    Corner("tr", "Top right", GAP, 90 - GAP, False, 75, 1),
    Corner("bl", "Bottom left", 180 + GAP, 270 - GAP, False, 255, 2),
    Corner("br", "Bottom right", 90 + GAP, 180 - GAP, True, 105, 3),
]


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    icon: str
    colors: tuple[str, ...]  # empty -> full
    value: str  # normalized 0..1 expression
    text: str  # value text expression
    text_format: str
    preview_value: float
    preview_text: str
    segments: int = 0  # > 0: drawn as that many separate bars instead of a continuous fill
    # Non-empty: drawn as a row of these images along the arc (from the anchor outward) instead
    # of a bar. Image i lights up once the value is above i/n. See TRAIL_* for the styles.
    trail: tuple[str, ...] = ()
    trail_style: str = ""
    trail_size: tuple[int, int] = (20, 20)


ECG_PIECES = 8  # heart-rate line: number of beats along the arc
ECG_W, ECG_H = 36, 24  # one beat image; ~SPAN / ECG_PIECES of arc length wide

COMP_NORM = (
    "clamp(([COMPLICATION.RANGED_VALUE_VALUE] - [COMPLICATION.RANGED_VALUE_MIN]) / "
    "max_guard, 0, 1)"
).replace(
    "max_guard",
    "(([COMPLICATION.RANGED_VALUE_MAX] - [COMPLICATION.RANGED_VALUE_MIN]) == 0 ? 1 : "
    "([COMPLICATION.RANGED_VALUE_MAX] - [COMPLICATION.RANGED_VALUE_MIN]))",
)

METRICS = {
    "battery": Metric(
        "battery", "Battery", "ic_metric_battery",
        # Battery cells: the first (low) bars are light, the last (full) bars darker.
        ("#FFB3E5FC", "#FF4FC3F7", "#FF1E88E5"),
        "clamp([BATTERY_PERCENT], 0, 100) / 100",
        "[BATTERY_PERCENT]", "%s%%", 0.72, "72%", segments=10,
    ),
    "steps": Metric(
        "steps", "Steps", "ic_metric_steps",
        # Footprints: the first steps of the day are pale green, the last ones vivid.
        ("#FFC8E6C9", "#FF81C784", "#FF43A047"),
        "clamp([STEP_PERCENT], 0, 100) / 100",
        "[STEP_COUNT]", "%s", 0.48, "4821",
        trail=("ic_step_left", "ic_step_right") * 5, trail_style="walk",
    ),
    "stress": Metric(
        "stress", "Stress", "ic_metric_stress",
        ("#FF43A047", "#FFFDD835", "#FFE53935"),
        COMP_NORM,
        "round([COMPLICATION.RANGED_VALUE_VALUE])", "%s", 0.27, "27",
        # Weather from calm to stormy: sun, sun + cloud, cloud, rain, thunderstorm.
        trail=tuple(f"ic_stress_{i}" for i in range(5)), trail_style="upright", trail_size=(22, 22),
    ),
    "heart": Metric(
        "heart", "Heart rate", "ic_metric_heart",
        ("#FFC2575A", "#FFFF1744"),
        "clamp(([HEART_RATE] - 40) / 140, 0, 1)",
        "[HEART_RATE] > 0 ? [HEART_RATE] : \"--\"", "%s", 0.16, "62",
        # A heart-monitor line: one beat per piece, the spikes taller further along the arc.
        trail=tuple(f"ic_ecg_{i}" for i in range(ECG_PIECES)), trail_style="tangent",
        trail_size=(ECG_W, ECG_H),
    ),
}

DEFAULT_LAYOUT = {"tl": "battery", "tr": "steps", "bl": "stress", "br": "heart"}

ACCENTS = [
    # id, label, bright, dim
    ("cyan", "Cyan", "#FF29B6F6", "#FF1E4E6B"),
    ("white", "White", "#FFFFFFFF", "#FF5A5A5A"),
    ("green", "Green", "#FF66BB6A", "#FF1F4A22"),
    ("amber", "Amber", "#FFFFB300", "#FF5C4100"),
    ("purple", "Purple", "#FFB388FF", "#FF3D2A63"),
]

# Weather periods: (id, label, window start hour, window end hour, representative hour, night?)
PERIODS = [
    ("morning", "MORNING", 6, 12, 9, False),
    ("afternoon", "AFTERNOON", 12, 18, 15, False),
    ("night", "NIGHT", 18, 6, 21, True),
]
MAX_FORECAST_HOURS = 8  # WFF exposes WEATHER.HOURS.1 .. WEATHER.HOURS.8


def attr(value: str) -> str:
    """Escapes a value for use inside a double-quoted XML attribute."""
    return escape(value, {'"': "&quot;"})


# --------------------------------------------------------------------------------------
# XML building blocks
# --------------------------------------------------------------------------------------
class Xml:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.depth = 0

    def open(self, tag: str, **attrs: object) -> None:
        self.lines.append("  " * self.depth + f"<{tag}{self._attrs(attrs)}>")
        self.depth += 1

    def close(self, tag: str) -> None:
        self.depth -= 1
        self.lines.append("  " * self.depth + f"</{tag}>")

    def leaf(self, tag: str, **attrs: object) -> None:
        self.lines.append("  " * self.depth + f"<{tag}{self._attrs(attrs)}/>")

    def raw(self, text: str) -> None:
        self.lines.append("  " * self.depth + text)

    @staticmethod
    def _attrs(attrs: dict[str, object]) -> str:
        out = []
        for key, value in attrs.items():
            if value is None:
                continue
            key = key.rstrip("_")
            if isinstance(value, float):
                value = f"{value:g}"
            out.append(f' {key}="{attr(str(value))}"')
        return "".join(out)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def full_group(x: Xml, name: str) -> None:
    x.open("Group", name=name, x=0, y=0, width=SIZE, height=SIZE)


def text_part(x: Xml, *, px, py, w, h, template: str, params: list[str], size: float,
              color: str = "#FFFFFFFF", weight: str = "NORMAL", align: str = "CENTER",
              ellipsis: bool = False, upper: bool = False, family: str = "SYNC_TO_DEVICE",
              bitmap: bool = False, name: str | None = None) -> None:
    if not params:
        # The schema requires at least one <Parameter>: emit static text as a string literal.
        params, template = [f'"{template}"'], "%s"
    x.open("PartText", name=name, x=px, y=py, width=w, height=h)
    x.open("Text", align=align, ellipsis="TRUE" if ellipsis else None)
    if bitmap:
        x.open("BitmapFont", family=family, size=size)
    else:
        x.open("Font", family=family, size=size, color=color, weight=weight)
    if upper:
        x.open("Upper")
    x.open("Template")
    x.raw(f"<![CDATA[{template}]]>")
    for p in params:
        x.leaf("Parameter", expression=p)
    x.close("Template")
    if upper:
        x.close("Upper")
    x.close("BitmapFont" if bitmap else "Font")
    x.close("Text")
    x.close("PartText")


def condition(x: Xml, branches: list[tuple[str, callable]], default: callable | None) -> None:
    """branches: (expression, render) pairs evaluated in order; default renders otherwise."""
    x.open("Condition")
    x.open("Expressions")
    for i, (expr, _) in enumerate(branches):
        x.raw(f'<Expression name="c{i}"><![CDATA[{expr}]]></Expression>')
    x.close("Expressions")
    for i, (_, render) in enumerate(branches):
        x.open("Compare", expression=f"c{i}")
        render()
        x.close("Compare")
    if default is not None:
        x.open("Default")
        default()
        x.close("Default")
    x.close("Condition")


# --------------------------------------------------------------------------------------
# Arcs
# --------------------------------------------------------------------------------------
def with_alpha(color: str, alpha: int) -> str:
    return f"#{alpha:02X}{color[3:]}"


def gradient_for(corner: Corner, colors: tuple[str, ...]) -> tuple[str, str]:
    """Returns (colors, positions) for a SweepGradient running clockwise start->end.

    `colors` is ordered empty->full, i.e. anchor->far; reverse it when the anchor is
    the clockwise end so the color at the fill's tip always reflects the value.
    """
    ordered = list(colors) if not corner.anchor_at_end else list(reversed(colors))
    n = len(ordered)
    positions = [i / (n - 1) for i in range(n)]
    return " ".join(ordered), " ".join(f"{p:g}" for p in positions)


def tip_angle(corner: Corner, value: str) -> str:
    sign = "-" if corner.anchor_at_end else "+"
    return f"{corner.anchor:g} {sign} {SPAN:g} * ({value})"


def arc_box() -> dict:
    return dict(centerX=C, centerY=C, width=ARC_D, height=ARC_D)


def draw_track(x: Xml, corner: Corner, color: str) -> None:
    x.open("PartDraw", x=0, y=0, width=SIZE, height=SIZE)
    x.open("Arc", **arc_box(), startAngle=corner.start, endAngle=corner.end)
    x.leaf("Stroke", color=color, thickness=STROKE, cap="ROUND")
    x.close("Arc")
    x.close("PartDraw")


def draw_fill(x: Xml, corner: Corner, metric: Metric, single: bool) -> None:
    tip = tip_angle(corner, metric.value)
    if single:
        x.open("PartDraw", x=0, y=0, width=SIZE, height=SIZE)
        # Single color mode: intensity (alpha) follows the value: dim when low, vivid when full.
        x.leaf("Transform", target="alpha", value=f"90 + 165 * ({metric.value})")
    else:
        x.open("PartDraw", x=0, y=0, width=SIZE, height=SIZE)
    x.open("Arc", **arc_box(), startAngle=corner.start, endAngle=corner.end)
    if single:
        x.leaf("Stroke", color="[CONFIGURATION.accent.0]", thickness=STROKE, cap="ROUND")
    else:
        colors, positions = gradient_for(corner, metric.colors)
        x.open("Stroke", color="#FFFFFFFF", thickness=STROKE, cap="ROUND")
        x.leaf("SweepGradient", centerX=C, centerY=C, startAngle=corner.start,
               endAngle=corner.end, colors=colors, positions=positions)
        x.close("Stroke")
    target = "startAngle" if corner.anchor_at_end else "endAngle"
    x.leaf("Transform", target=target, value=tip)
    x.close("Arc")
    x.close("PartDraw")


SEGMENT_GAP = 2.2  # degrees between battery bars


def segment_angles(corner: Corner, i: int, n: int) -> tuple[float, float]:
    """Clockwise (start, end) of bar i of n, counted from the corner's anchor."""
    seg = SPAN / n
    near, far = i * seg + SEGMENT_GAP / 2, (i + 1) * seg - SEGMENT_GAP / 2
    if corner.anchor_at_end:
        return corner.anchor - far, corner.anchor - near
    return corner.anchor + near, corner.anchor + far


def segment_color(metric: Metric, i: int) -> str:
    """Bar i's color along the metric's colors (first bar = first color, last = last)."""
    n = metric.segments or len(metric.trail)
    return "#FF" + lerp_color(metric.colors, i / (n - 1) if n > 1 else 1)[1:]


def draw_segments(x: Xml, corner: Corner, metric: Metric, single: bool, placeholder: bool) -> None:
    """Segmented bar: a dim track per bar, and each bar lights up once the value reaches it.

    Bar i (of n) is lit when the value is above i/n, so 1-10 % lights the first of ten bars.
    Lit bars have static colors; only their alpha depends on the value (no color math).
    """
    n = metric.segments
    for i in range(n):
        a0, a1 = segment_angles(corner, i, n)
        x.open("PartDraw", x=0, y=0, width=SIZE, height=SIZE)
        x.open("Arc", **arc_box(), startAngle=a0, endAngle=a1)
        x.leaf("Stroke", color="#26FFFFFF" if single else with_alpha(metric.colors[0], 0x2E),
               thickness=STROKE, cap="BUTT")
        x.close("Arc")
        x.close("PartDraw")
        if placeholder:
            continue
        lit = "[CONFIGURATION.accent.0]" if single else segment_color(metric, i)
        on = f"(90 + 165 * ({metric.value}))" if single else "255"
        x.open("PartDraw", x=0, y=0, width=SIZE, height=SIZE)
        x.leaf("Transform", target="alpha", value=f"({metric.value}) > {i / n:g} ? {on} : 0")
        x.open("Arc", **arc_box(), startAngle=a0, endAngle=a1)
        x.leaf("Stroke", color=lit, thickness=STROKE, cap="BUTT")
        x.close("Arc")
        x.close("PartDraw")


# Trail styles: how each image of a Metric.trail sits on the arc.
TRAIL_WALK = "walk"  # footprints: toes along the walking direction, alternating sides
TRAIL_TANGENT = "tangent"  # lies along the arc, image top toward the screen center
TRAIL_UPRIGHT = "upright"  # not rotated, on the arc's center line
FOOT_SIDE = 3.5  # px each footprint sits off the arc's center line (left / right foot)
TRAIL_DIM_ALPHA = 60  # alpha of trail images not reached yet


def trail_spots(corner: Corner, metric: Metric) -> list[tuple[float, float, float, str]]:
    """(x, y, rotation, image) of each trail image, from the corner's anchor outward."""
    out = []
    n = len(metric.trail)
    w, h = metric.trail_size
    seg = SPAN / n
    sign = -1 if corner.anchor_at_end else 1
    for i, image in enumerate(metric.trail):
        a = corner.anchor + sign * (i + 0.5) * seg
        r, rot = ARC_R, 0.0
        if metric.trail_style == TRAIL_WALK:
            rot = a + 90 * sign  # tangent to the arc, in the walking direction
            # Left and right feet alternate; the walker's left is outside the ring when walking
            # clockwise.
            left = i % 2 == 0
            r += FOOT_SIDE if left == (sign > 0) else -FOOT_SIDE
        elif metric.trail_style == TRAIL_TANGENT:
            rot = a + 180  # image top points at the screen center
        px, py = polar(a, r)
        out.append((round(px - w / 2), round(py - h / 2), rot % 360, image))
    return out


def draw_trail(x: Xml, corner: Corner, metric: Metric, single: bool, placeholder: bool) -> None:
    """Image trail: image i (of n) lights up once the value is above i/n.

    Every image is always drawn; ones not reached yet are dim. Colors are static tints, only
    the alpha depends on the value. The placeholder (no data source yet) is the dim trail.
    """
    n = len(metric.trail)
    w, h = metric.trail_size
    for i, (ix, iy, rot, image) in enumerate(trail_spots(corner, metric)):
        tint = "[CONFIGURATION.accent.0]" if single else segment_color(metric, i)
        on = f"(90 + 165 * ({metric.value}))" if single else "255"
        x.open("PartImage", x=ix, y=iy, width=w, height=h,
               angle=round(rot, 2) if rot else None, tintColor=tint,
               alpha=TRAIL_DIM_ALPHA if placeholder else None)
        if not placeholder:
            x.leaf("Transform", target="alpha",
                   value=f"({metric.value}) > {i / n:g} ? {on} : {TRAIL_DIM_ALPHA}")
        x.leaf("Image", resource=image)
        x.close("PartImage")


def draw_knob(x: Xml, corner: Corner, metric: Metric) -> None:
    x.open("PartDraw", x=0, y=0, width=SIZE, height=SIZE)
    k = 10
    x.open("Ellipse", x=C - k / 2, y=(SIZE - ARC_D) / 2 - k / 2, width=k, height=k)
    x.leaf("Fill", color="#FFFFFFFF")
    x.close("Ellipse")
    x.leaf("Transform", target="angle", value=tip_angle(corner, metric.value))
    x.close("PartDraw")


BADGE_R = 170
BADGE_W, BADGE_H = 48, 42


def badge_origin(corner: Corner) -> tuple[float, float]:
    a = math.radians(corner.badge_angle)
    cx = C + BADGE_R * math.sin(a)
    cy = C - BADGE_R * math.cos(a)
    return round(cx - BADGE_W / 2), round(cy - BADGE_H / 2)


def draw_badge(x: Xml, corner: Corner, metric: Metric, single: bool, placeholder: bool) -> None:
    bx, by = badge_origin(corner)
    x.open("Group", name=f"badge_{corner.id}_{metric.id}", x=bx, y=by, width=BADGE_W, height=BADGE_H)

    def icon(tint: str) -> callable:
        def render() -> None:
            x.open("PartImage", x=(BADGE_W - 20) / 2, y=0, width=20, height=20, tintColor=tint)
            x.leaf("Image", resource=metric.icon)
            x.close("PartImage")
        return render

    if single:
        icon("[CONFIGURATION.accent.0]")()
    elif placeholder:
        icon(metric.colors[0])()
    else:
        # Tint the icon with the color of the arc's current bucket (cheap 3-way branch).
        cols = metric.colors if len(metric.colors) == 3 else (metric.colors[0], metric.colors[0], metric.colors[1])
        condition(x, [
            (f"({metric.value}) < 0.34", icon(cols[0])),
            (f"({metric.value}) < 0.67", icon(cols[1])),
        ], icon(cols[2]))

    if placeholder:
        text_part(x, px=0, py=22, w=BADGE_W, h=22, template="--", params=[], size=16,
                  color="#FF9E9E9E", weight="SEMI_BOLD")
    else:
        text_part(x, px=0, py=22, w=BADGE_W, h=22, template=metric.text_format,
                  params=[metric.text], size=16, weight="SEMI_BOLD")
    x.close("Group")


def draw_metric(x: Xml, corner: Corner, metric: Metric, placeholder: bool = False) -> None:
    """Draws one metric's arc in one corner, for both color modes."""
    full_group(x, f"{corner.id}_{metric.id}")
    x.open("ListConfiguration", id="color_mode")
    for mode in ("multi", "single"):
        single = mode == "single"
        x.open("ListOption", id=mode)
        full_group(x, f"{corner.id}_{metric.id}_{mode}")
        if metric.segments:
            draw_segments(x, corner, metric, single, placeholder)
        elif metric.trail:
            draw_trail(x, corner, metric, single, placeholder)
        else:
            track = "#26FFFFFF" if single else with_alpha(metric.colors[-1], 0x33)
            draw_track(x, corner, track)
            if not placeholder:
                draw_fill(x, corner, metric, single)
                draw_knob(x, corner, metric)
        draw_badge(x, corner, metric, single, placeholder)
        x.close("Group")
        x.close("ListOption")
    x.close("ListConfiguration")
    x.close("Group")


def empty_group(x: Xml, name: str) -> None:
    x.leaf("Group", name=name, x=0, y=0, width=1, height=1)


def draw_corner_native(x: Xml, corner: Corner) -> None:
    """Scene-level corner: native metrics plus the stress placeholder (track + "--")."""
    full_group(x, f"corner_{corner.id}")
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    x.open("ListConfiguration", id=f"arc_{corner.id}")
    for metric in METRICS.values():
        x.open("ListOption", id=metric.id)
        # Stress comes from a complication; the scene only draws its empty state.
        draw_metric(x, corner, metric, placeholder=metric.id == "stress")
        x.close("ListOption")
    x.close("ListConfiguration")
    x.close("Group")


def draw_corner_slot(x: Xml, corner: Corner) -> None:
    """Per-corner complication slot that renders Stress (RANGED_VALUE) when chosen there."""
    x.open("ComplicationSlot", slotId=corner.slot_id, name=f"stress_{corner.id}",
           displayName=f"slot_stress_{corner.id}", x=0, y=0, width=SIZE, height=SIZE,
           supportedTypes="RANGED_VALUE EMPTY", isCustomizable="TRUE")
    x.leaf("BoundingArc", **arc_box(), thickness=STROKE + 26, startAngle=corner.start,
           endAngle=corner.end, isRoundEdge="TRUE")
    if DEFAULT_LAYOUT[corner.id] == "stress":
        x.leaf("DefaultProviderPolicy", defaultSystemProvider="EMPTY",
               defaultSystemProviderType="EMPTY",
               primaryProvider=f"{PROVIDER_PKG}/{PROVIDER_PKG}.stress.StressDataSourceService",
               primaryProviderType="RANGED_VALUE")
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    x.open("Complication", type="RANGED_VALUE")
    full_group(x, f"stress_{corner.id}_root")
    x.open("ListConfiguration", id=f"arc_{corner.id}")
    for metric in METRICS.values():
        x.open("ListOption", id=metric.id)
        if metric.id == "stress":
            full_group(x, f"stress_{corner.id}_cover")
            # Paint over the placeholder badge before drawing the live arc + badge.
            bx, by = badge_origin(corner)
            x.open("PartDraw", x=bx, y=by, width=BADGE_W, height=BADGE_H)
            x.open("Rectangle", x=0, y=0, width=BADGE_W, height=BADGE_H)
            x.leaf("Fill", color="#FF000000")
            x.close("Rectangle")
            x.close("PartDraw")
            draw_metric(x, corner, metric)
            x.close("Group")
        else:
            empty_group(x, f"stress_{corner.id}_{metric.id}_off")
        x.close("ListOption")
    x.close("ListConfiguration")
    x.close("Group")
    x.close("Complication")
    x.open("Complication", type="EMPTY")
    empty_group(x, f"stress_{corner.id}_empty")
    x.close("Complication")
    x.close("ComplicationSlot")


# --------------------------------------------------------------------------------------
# Weather (morning / afternoon / night)
# --------------------------------------------------------------------------------------
def in_window(start: int, end: int) -> str:
    h = "[HOUR_0_23]"
    if start < end:
        return f"({h} >= {start} && {h} < {end})"
    return f"({h} >= {start} || {h} < {end})"


def period_expr(period, field_now: str, field_hour: str, field_day: str) -> str:
    """Builds a nested ternary that picks the best available forecast for a period.

    1. Inside the period's window -> current conditions.
    2. Representative hour within the next 8 hours -> hourly forecast.
    3. Otherwise -> daily forecast (today if the hour is still ahead, else tomorrow).
    """
    _, _, start, end, rep, _ = period
    offset = f"(({rep} - [HOUR_0_23] + 24) % 24)"
    expr = (
        f"({rep} > [HOUR_0_23] ? [WEATHER.DAYS.0.{field_day}] : [WEATHER.DAYS.1.{field_day}])"
    )
    for k in range(MAX_FORECAST_HOURS, 0, -1):
        expr = (
            f"(({offset} == {k} && [WEATHER.HOURS.{k}.IS_AVAILABLE]) ? "
            f"[WEATHER.HOURS.{k}.{field_hour}] : {expr})"
        )
    return f"({in_window(start, end)} ? [WEATHER.{field_now}] : {expr})"


def draw_weather(x: Xml) -> None:
    x.open("Group", name="weather", x=105, y=60, width=240, height=50)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    x.open("BooleanConfiguration", id="show_weather")
    x.open("BooleanOption", id="TRUE")
    x.open("Group", name="weather_on", x=0, y=0, width=240, height=50)

    def available() -> None:
        for i, period in enumerate(PERIODS):
            pid, label, *_rest, night = period
            cond = period_expr(period, "CONDITION", "CONDITION", "CONDITION_NIGHT" if night else "CONDITION_DAY")
            temp = period_expr(period, "TEMPERATURE", "TEMPERATURE", "TEMPERATURE_LOW" if night else "TEMPERATURE_HIGH")
            x.open("Group", name=f"weather_{pid}", x=i * 80, y=0, width=80, height=50)
            text_part(x, px=8, py=0, w=28, h=28, family="weather_night" if night else "weather_day",
                      bitmap=True, size=28, template="%s",
                      params=[f"(({cond}) >= 0 && ({cond}) <= 15) ? ({cond}) : 0"])
            text_part(x, px=38, py=2, w=40, h=24, template="%s°", params=[f"round({temp})"],
                      size=17, weight="MEDIUM", align="START")
            text_part(x, px=0, py=30, w=80, h=16, template=label, params=[], size=11,
                      color="#FF9E9E9E", weight="MEDIUM")
            x.close("Group")

    condition(x, [("[WEATHER.IS_AVAILABLE] && ![WEATHER.IS_ERROR]", available)], None)
    x.close("Group")
    x.close("BooleanOption")
    x.open("BooleanOption", id="FALSE")
    empty_group(x, "weather_off")
    x.close("BooleanOption")
    x.close("BooleanConfiguration")
    x.close("Group")


# --------------------------------------------------------------------------------------
# Date, time, meetings
# --------------------------------------------------------------------------------------
DATE_Y, DATE_H = 114, 40
TIME_Y, TIME_H = 152, 114
MEET1_Y, MEET2_Y, MEET_H = 270, 304, 30
MEET_X, MEET_W = 88, 274
MEET_TITLE_W = 78  # time column, right aligned
MEET_TEXT_X = MEET_TITLE_W + 8


def draw_date(x: Xml) -> None:
    x.open("Group", name="date", x=60, y=DATE_Y, width=330, height=DATE_H)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=190)
    text_part(x, px=0, py=0, w=161, h=DATE_H, template="%s", params=["[DAY_OF_WEEK_S]"],
              size=32, weight="BOLD", align="END", upper=True, color="[CONFIGURATION.accent.0]")
    text_part(x, px=171, py=0, w=159, h=DATE_H, template="%s", params=["[DAY]"],
              size=32, weight="BOLD", align="START")
    x.close("Group")


def draw_time(x: Xml) -> None:
    x.open("Group", name="time", x=0, y=TIME_Y, width=SIZE, height=TIME_H)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=215)
    x.open("DigitalClock", x=0, y=0, width=SIZE, height=TIME_H)
    for fmt, px, align in (("hh", 30, "END"), ("mm", 240, "START")):
        x.open("TimeText", format=fmt, hourFormat="SYNC_TO_DEVICE", align=align,
               x=px, y=0, width=180, height=TIME_H)
        x.leaf("Font", family="SYNC_TO_DEVICE", size=96, weight="BOLD", color="#FFFFFFFF")
        x.close("TimeText")
    x.close("DigitalClock")
    text_part(x, px=210, py=0, w=30, h=TIME_H - 10, template=":", params=[], size=88,
              weight="BOLD", color="#FFBDBDBD")
    x.close("Group")


def draw_meeting_slot(x: Xml, slot_id: int, y: int, second: bool) -> None:
    service = "SecondMeetingDataSourceService" if second else "NextMeetingDataSourceService"
    x.open("ComplicationSlot", slotId=slot_id, name=f"meeting_{2 if second else 1}",
           displayName=f"slot_meeting_{2 if second else 1}", x=MEET_X, y=y, width=MEET_W,
           height=MEET_H, supportedTypes="LONG_TEXT SHORT_TEXT EMPTY", isCustomizable="TRUE")
    x.leaf("BoundingBox", x=0, y=0, width=MEET_W, height=MEET_H)
    x.leaf("DefaultProviderPolicy", defaultSystemProvider="NEXT_EVENT",
           defaultSystemProviderType="SHORT_TEXT" if second else "LONG_TEXT",
           primaryProvider=f"{PROVIDER_PKG}/{PROVIDER_PKG}.calendar.{service}",
           primaryProviderType="LONG_TEXT")
    # Ambient shows the battery bar in this place instead (see draw_ambient_battery).
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    size = 19 if second else 22
    title_color = "[CONFIGURATION.accent.0]"
    text_alpha = "#99FFFFFF" if second else "#FFFFFFFF"

    def body(kind: str) -> None:
        x.open("Group", name=f"meeting_{slot_id}_{kind}", x=0, y=0, width=MEET_W, height=MEET_H)
        if second:
            x.open("ListConfiguration", id="meeting_rows")
            x.open("ListOption", id="one")
            empty_group(x, f"meeting_{slot_id}_{kind}_hidden")
            x.close("ListOption")
            x.open("ListOption", id="two")
            x.open("Group", name=f"meeting_{slot_id}_{kind}_shown", x=0, y=0, width=MEET_W, height=MEET_H)

        def with_title() -> None:
            text_part(x, px=0, py=0, w=MEET_TITLE_W, h=MEET_H, template="%s", params=["[COMPLICATION.TITLE]"],
                      size=size, weight="SEMI_BOLD", align="END", color=title_color, ellipsis=True)
            text_part(x, px=MEET_TEXT_X, py=0, w=MEET_W - MEET_TEXT_X, h=MEET_H, template="%s",
                      params=["[COMPLICATION.TEXT]"], size=size, align="START",
                      color=text_alpha, ellipsis=True)

        def text_only() -> None:
            text_part(x, px=0, py=0, w=MEET_W, h=MEET_H, template="%s",
                      params=["[COMPLICATION.TEXT]"], size=size - 2, align="CENTER",
                      color="#FF9E9E9E", ellipsis=True)

        if kind == "long":
            condition(x, [("[COMPLICATION.TITLE] != null", with_title)], text_only)
        else:
            text_only()
        if second:
            x.close("Group")
            x.close("ListOption")
            x.close("ListConfiguration")
        x.close("Group")

    x.open("Complication", type="LONG_TEXT")
    body("long")
    x.close("Complication")
    x.open("Complication", type="SHORT_TEXT")
    body("short")
    x.close("Complication")
    x.open("Complication", type="EMPTY")
    empty_group(x, f"meeting_{slot_id}_empty")
    x.close("Complication")
    x.close("ComplicationSlot")


# --------------------------------------------------------------------------------------
# Ambient battery bar (in place of the next meeting)
# --------------------------------------------------------------------------------------
AMB_BATT_ICON = 20
AMB_BATT_SEG_X, AMB_BATT_SEG_W, AMB_BATT_SEG_GAP, AMB_BATT_SEG_H = 28, 17, 2, 12
AMB_BATT_TEXT_X = AMB_BATT_SEG_X + 10 * (AMB_BATT_SEG_W + AMB_BATT_SEG_GAP) + 6
AMB_BATT_ALPHA = 200  # a little dimmer than the time, like the rest of ambient


def draw_ambient_battery(x: Xml) -> None:
    """Battery as 10 small bars + percentage, shown only in ambient where the meeting row is.

    Hidden (alpha 0) in interactive mode; the AMBIENT variant brings it in. It uses the same
    light (low) -> darker (full) colors as the battery arc.
    """
    battery = METRICS["battery"]
    n = battery.segments or 10
    x.open("Group", name="ambient_battery", x=MEET_X, y=MEET1_Y, width=MEET_W, height=MEET_H, alpha=0)
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=AMB_BATT_ALPHA)
    x.open("PartImage", x=0, y=(MEET_H - AMB_BATT_ICON) / 2, width=AMB_BATT_ICON, height=AMB_BATT_ICON,
           tintColor="#FFBDBDBD")
    x.leaf("Image", resource=battery.icon)
    x.close("PartImage")
    seg_y = (MEET_H - AMB_BATT_SEG_H) / 2
    r = 2
    for i in range(n):
        sx = AMB_BATT_SEG_X + i * (AMB_BATT_SEG_W + AMB_BATT_SEG_GAP)
        for lit in (False, True):
            x.open("PartDraw", x=sx, y=seg_y, width=AMB_BATT_SEG_W, height=AMB_BATT_SEG_H)
            if lit:
                x.leaf("Transform", target="alpha", value=f"({battery.value}) > {i / n:g} ? 255 : 0")
            x.open("RoundRectangle", x=0, y=0, width=AMB_BATT_SEG_W, height=AMB_BATT_SEG_H,
                   cornerRadiusX=r, cornerRadiusY=r)
            x.leaf("Fill", color=segment_color(battery, i) if lit else "#33FFFFFF")
            x.close("RoundRectangle")
            x.close("PartDraw")
    text_part(x, px=AMB_BATT_TEXT_X, py=0, w=MEET_W - AMB_BATT_TEXT_X, h=MEET_H, template=battery.text_format,
              params=[battery.text], size=20, weight="SEMI_BOLD", align="START")
    x.close("Group")


# --------------------------------------------------------------------------------------
# Skin temperature thermometer (under the meetings)
# --------------------------------------------------------------------------------------
THERMO_SLOT = 12
THERMO_X, THERMO_Y, THERMO_W, THERMO_H = 135, 342, 180, 28
BULB_D = 20
TUBE_X, TUBE_Y, TUBE_W, TUBE_H = 12, 9, 96, 10
THERMO_TEXT_X = TUBE_X + TUBE_W + 8
# The whole thermometer takes one color from the reading (°C, as sent by the companion),
# benchmarked on wrist skin, which runs several degrees cooler than the body core:
#   below 32 °C   cool blue    cooler than usual wrist skin (cold room, poor circulation)
#   32 - 35.5 °C  warm orange  the usual range for wrist skin under a watch strap
#   35.5 °C and up  red        above the usual wrist range: heat, exercise or possibly fever
# (upper bound in °C, color); the last band has no upper bound.
THERMO_BANDS = (
    (32.0, "#FF29B6F6"),
    (35.5, "#FFFF9800"),
    (None, "#FFF44336"),
)
THERMO_PREVIEW = (33.6, "33.6°")
THERMO_MIN_C, THERMO_MAX_C = 28.0, 38.0  # must match SkinTemperature.MIN_C / MAX_C


def thermo_band_color(celsius: float) -> str:
    return next(c for upper, c in THERMO_BANDS if upper is None or celsius < upper)


def draw_thermometer_slot(x: Xml) -> None:
    """Skin temperature: a horizontal thermometer whose liquid follows a RANGED_VALUE.

    Wear OS has no platform skin-temperature source, so this is a complication. The default
    provider is the companion's sensor reader; it returns NO_DATA on watches without a skin
    temperature sensor, and nothing is drawn (NO_DATA matches no <Complication> below).
    """
    x.open("ComplicationSlot", slotId=THERMO_SLOT, name="skin_temperature",
           displayName="slot_skin_temperature", x=THERMO_X, y=THERMO_Y, width=THERMO_W,
           height=THERMO_H, supportedTypes="RANGED_VALUE SHORT_TEXT EMPTY", isCustomizable="TRUE")
    x.leaf("BoundingBox", x=0, y=0, width=THERMO_W, height=THERMO_H)
    x.leaf("DefaultProviderPolicy", defaultSystemProvider="EMPTY",
           defaultSystemProviderType="EMPTY",
           primaryProvider=f"{PROVIDER_PKG}/{PROVIDER_PKG}.skin.SkinTemperatureDataSourceService",
           primaryProviderType="RANGED_VALUE")
    x.leaf("Variant", mode="AMBIENT", target="alpha", value=0)
    tube_r = TUBE_H / 2

    def tube(color: str) -> None:
        x.open("RoundRectangle", x=TUBE_X, y=TUBE_Y, width=TUBE_W, height=TUBE_H,
               cornerRadiusX=tube_r, cornerRadiusY=tube_r)
        x.leaf("Fill", color=color)
        x.close("RoundRectangle")

    def bulb(color: str) -> callable:
        def render() -> None:
            x.open("PartDraw", x=0, y=0, width=BULB_D, height=THERMO_H)
            x.open("Ellipse", x=0, y=(THERMO_H - BULB_D) / 2, width=BULB_D, height=BULB_D)
            x.leaf("Fill", color=color)
            x.close("Ellipse")
            x.close("PartDraw")
        return render

    def value_text() -> None:
        text_part(x, px=THERMO_TEXT_X, py=0, w=THERMO_W - THERMO_TEXT_X, h=THERMO_H, template="%s",
                  params=["[COMPLICATION.TEXT]"], size=18, weight="SEMI_BOLD", align="START")

    def thermometer(track: str, color: str) -> callable:
        """Track, liquid and bulb, all in one color. The liquid is the same rounded tube with
        its width following the value; it starts under the bulb, so even a low reading looks
        attached."""
        def render() -> None:
            x.open("PartDraw", x=0, y=0, width=THERMO_W, height=THERMO_H)
            tube(track)
            x.open("RoundRectangle", x=TUBE_X, y=TUBE_Y, width=TUBE_W, height=TUBE_H,
                   cornerRadiusX=tube_r, cornerRadiusY=tube_r)
            x.leaf("Fill", color=color)
            x.leaf("Transform", target="width",
                   value=f"{tube_r * 2:g} + {TUBE_W - tube_r * 2:g} * ({COMP_NORM})")
            x.close("RoundRectangle")
            x.close("PartDraw")
            bulb(color)()
        return render

    def ranged(single: bool) -> None:
        if single:
            thermometer("#26FFFFFF", "[CONFIGURATION.accent.0]")()
        else:
            # One cheap branch per band: the whole thermometer switches color at once.
            value = "[COMPLICATION.RANGED_VALUE_VALUE]"
            bands = [(f"{value} < {upper:g}", thermometer(with_alpha(color, 0x33), color))
                     for upper, color in THERMO_BANDS if upper is not None]
            last = THERMO_BANDS[-1][1]
            condition(x, bands, thermometer(with_alpha(last, 0x33), last))
        value_text()

    x.open("Complication", type="RANGED_VALUE")
    full_thermo = dict(x=0, y=0, width=THERMO_W, height=THERMO_H)
    x.open("Group", name="thermo_ranged", **full_thermo)
    x.open("ListConfiguration", id="color_mode")
    for mode in ("multi", "single"):
        x.open("ListOption", id=mode)
        x.open("Group", name=f"thermo_ranged_{mode}", **full_thermo)
        ranged(mode == "single")
        x.close("Group")
        x.close("ListOption")
    x.close("ListConfiguration")
    x.close("Group")
    x.close("Complication")

    # Other providers may only offer text: an empty tube + the value.
    x.open("Complication", type="SHORT_TEXT")
    x.open("Group", name="thermo_short", **full_thermo)
    x.open("PartDraw", x=0, y=0, width=THERMO_W, height=THERMO_H)
    tube("#26FFFFFF")
    x.close("PartDraw")
    bulb("[CONFIGURATION.accent.0]")()
    value_text()
    x.close("Group")
    x.close("Complication")

    x.open("Complication", type="EMPTY")
    empty_group(x, "thermo_empty")
    x.close("Complication")
    x.close("ComplicationSlot")


# --------------------------------------------------------------------------------------
# User configuration
# --------------------------------------------------------------------------------------
FLAVORS = [
    ("default", "flavor_default", DEFAULT_LAYOUT),
    ("mirrored", "flavor_mirrored", {"tl": "steps", "tr": "battery", "bl": "heart", "br": "stress"}),
    ("health_top", "flavor_health_top", {"tl": "heart", "tr": "steps", "bl": "stress", "br": "battery"}),
]


def draw_user_configurations(x: Xml) -> None:
    x.open("UserConfigurations")
    for corner in CORNERS:
        x.open("ListConfiguration", id=f"arc_{corner.id}", displayName=f"cfg_arc_{corner.id}",
               screenReaderText=f"cfg_arc_{corner.id}", defaultValue=DEFAULT_LAYOUT[corner.id])
        for metric in METRICS.values():
            x.leaf("ListOption", id=metric.id, displayName=f"metric_{metric.id}",
                   screenReaderText=f"metric_{metric.id}")
        x.close("ListConfiguration")
    x.open("ListConfiguration", id="color_mode", displayName="cfg_color_mode",
           screenReaderText="cfg_color_mode", defaultValue="multi")
    x.leaf("ListOption", id="multi", displayName="color_mode_multi", screenReaderText="color_mode_multi")
    x.leaf("ListOption", id="single", displayName="color_mode_single", screenReaderText="color_mode_single")
    x.close("ListConfiguration")
    x.open("ColorConfiguration", id="accent", displayName="cfg_accent",
           screenReaderText="cfg_accent", defaultValue="cyan")
    for cid, _label, bright, dim in ACCENTS:
        x.leaf("ColorOption", id=cid, displayName=f"accent_{cid}", screenReaderText=f"accent_{cid}",
               colors=f"{bright} {dim}")
    x.close("ColorConfiguration")
    x.leaf("BooleanConfiguration", id="show_weather", displayName="cfg_show_weather",
           screenReaderText="cfg_show_weather", defaultValue="TRUE")
    x.open("ListConfiguration", id="meeting_rows", displayName="cfg_meeting_rows",
           screenReaderText="cfg_meeting_rows", defaultValue="two")
    x.leaf("ListOption", id="one", displayName="meeting_rows_one", screenReaderText="meeting_rows_one")
    x.leaf("ListOption", id="two", displayName="meeting_rows_two", screenReaderText="meeting_rows_two")
    x.close("ListConfiguration")
    x.open("Flavors", defaultValue="default")
    for fid, name, layout in FLAVORS:
        x.open("Flavor", id=fid, displayName=name, screenReaderText=name)
        for corner in CORNERS:
            x.leaf("Configuration", id=f"arc_{corner.id}", optionId=layout[corner.id])
        x.close("Flavor")
    x.close("Flavors")
    x.close("UserConfigurations")


def draw_bitmap_fonts(x: Xml) -> None:
    x.open("BitmapFonts")
    for family in ("weather_day", "weather_night"):
        night = family == "weather_night"
        x.open("BitmapFont", name=family)
        for code in range(16):
            res = "ic_wx_" + WEATHER_ICON_MAP[code].removeprefix("ic_")
            if night and code == 14:
                res = "ic_wx_partly_cloudy_night"
            if night and code in (1, 8):  # clear / sunny at night -> moon
                res = "ic_wx_clear_night"
            # Single characters use <Character>, multi-character codes use <Word>.
            tag = "Character" if code < 10 else "Word"
            x.leaf(tag, name=str(code), resource=res, width=WEATHER_PX, height=WEATHER_PX)
        x.close("BitmapFont")
    x.close("BitmapFonts")


# WEATHER.CONDITION codes (see WFF weather docs) -> source icon in third_party/weather-icons
WEATHER_ICON_MAP = {
    0: "ic_unknown", 1: "ic_clear", 2: "ic_cloudy", 3: "ic_fog", 4: "ic_heavy_rain",
    5: "ic_heavy_snow", 6: "ic_rain", 7: "ic_snow", 8: "ic_sunny", 9: "ic_thunderstorm",
    10: "ic_sleet", 11: "ic_snow", 12: "ic_rain", 13: "ic_fog", 14: "ic_partly_cloudy_day",
    15: "ic_windy",
}
WEATHER_PX = 48


def build_xml() -> str:
    x = Xml()
    x.raw('<?xml version="1.0" encoding="UTF-8"?>')
    x.raw("<!-- GENERATED by tools/generate_watchface.py. Do not edit by hand. -->")
    x.open("WatchFace", width=SIZE, height=SIZE, clipShape="CIRCLE")
    x.leaf("Metadata", key="CLOCK_TYPE", value="DIGITAL")
    x.leaf("Metadata", key="PREVIEW_TIME", value="10:08:32")
    x.leaf("Metadata", key="STEP_GOAL", value="10000")
    draw_user_configurations(x)
    draw_bitmap_fonts(x)
    x.open("Scene", backgroundColor="#FF000000")
    for corner in CORNERS:
        draw_corner_native(x, corner)
    for corner in CORNERS:
        draw_corner_slot(x, corner)
    draw_weather(x)
    draw_date(x)
    draw_time(x)
    draw_meeting_slot(x, 10, MEET1_Y, second=False)
    draw_meeting_slot(x, 11, MEET2_Y, second=True)
    draw_thermometer_slot(x)
    draw_ambient_battery(x)
    x.close("Scene")
    x.close("WatchFace")
    return x.text()


# --------------------------------------------------------------------------------------
# Raster assets (tiny, white, tinted at runtime)
# --------------------------------------------------------------------------------------
def make_icons() -> None:
    from PIL import Image, ImageDraw

    out = RES / "drawable-nodpi"
    out.mkdir(parents=True, exist_ok=True)
    s = 4  # supersampling factor
    n = 24 * s

    def canvas():
        img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        return img, ImageDraw.Draw(img)

    def save(img, name):
        img.resize((24, 24), Image.LANCZOS).save(out / f"{name}.png", optimize=True)

    w = (255, 255, 255, 255)
    # Battery
    img, d = canvas()
    d.rounded_rectangle([7 * s, 4 * s, 17 * s, 22 * s], radius=2 * s, outline=w, width=2 * s)
    d.rectangle([10 * s, 2 * s, 14 * s, 4 * s], fill=w)
    d.rectangle([9.5 * s, 10 * s, 14.5 * s, 19.5 * s], fill=w)
    save(img, "ic_metric_battery")
    # Steps (two footprints)
    img, d = canvas()
    d.ellipse([4 * s, 3 * s, 10 * s, 13 * s], fill=w)
    d.ellipse([5 * s, 14 * s, 9.5 * s, 18 * s], fill=w)
    d.ellipse([14 * s, 7 * s, 20 * s, 17 * s], fill=w)
    d.ellipse([14.5 * s, 18 * s, 19 * s, 22 * s], fill=w)
    save(img, "ic_metric_steps")
    # One footprint (toes up) for the steps trail, plus its mirror for the other foot.
    img, d = canvas()
    d.ellipse([6.5 * s, 1 * s, 16.5 * s, 14.5 * s], fill=w)
    d.ellipse([8 * s, 15.5 * s, 14.5 * s, 23 * s], fill=w)
    save(img, "ic_step_left")
    img.transpose(Image.FLIP_LEFT_RIGHT).resize((24, 24), Image.LANCZOS).save(
        out / "ic_step_right.png", optimize=True)
    make_trail_icons(out)
    # Heart
    img, d = canvas()
    d.ellipse([2.5 * s, 4 * s, 12.5 * s, 14 * s], fill=w)
    d.ellipse([11.5 * s, 4 * s, 21.5 * s, 14 * s], fill=w)
    d.polygon([(3 * s, 11 * s), (21 * s, 11 * s), (12 * s, 21.5 * s)], fill=w)
    save(img, "ic_metric_heart")
    # Stress (pulse wave)
    img, d = canvas()
    pts = [(2, 13), (7, 13), (9.5, 6), (13, 20), (15.5, 10), (17, 13), (22, 13)]
    d.line([(px * s, py * s) for px, py in pts], fill=w, width=int(2.4 * s), joint="curve")
    save(img, "ic_metric_stress")

    # Weather icons: downscale the Apache-2.0 sample set to 48 px to keep memory low.
    for src in sorted(WEATHER_SRC.glob("ic_*.png")):
        im = Image.open(src).convert("RGBA").resize((WEATHER_PX, WEATHER_PX), Image.LANCZOS)
        im.save(out / src.name.replace("ic_", "ic_wx_", 1), optimize=True)
    # Clear night: a crescent moon.
    img = Image.new("RGBA", (WEATHER_PX * s, WEATHER_PX * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = WEATHER_PX * s
    d.ellipse([m * 0.18, m * 0.14, m * 0.82, m * 0.78], fill=(255, 236, 179, 255))
    d.ellipse([m * 0.36, m * 0.04, m * 1.0, m * 0.68], fill=(0, 0, 0, 0))
    img.resize((WEATHER_PX, WEATHER_PX), Image.LANCZOS).save(out / "ic_wx_clear_night.png", optimize=True)


def make_trail_icons(out: Path) -> None:
    """White trail images (tinted at runtime): heart-rate beats and stress weather."""
    from PIL import Image, ImageDraw

    s = 4
    w = (255, 255, 255, 255)
    clear = (0, 0, 0, 0)

    # Heart-rate beats: a symmetric P-QRS-T blip on a baseline, taller for later pieces, so the
    # same image reads the same whichever way the arc runs.
    for k in range(ECG_PIECES):
        img = Image.new("RGBA", (ECG_W * s, ECG_H * s), clear)
        d = ImageDraw.Draw(img)
        amp = 3.5 + 6.0 * k / (ECG_PIECES - 1)
        base = ECG_H / 2 + 2  # same baseline in every piece; room above for the spikes

        def y(u: float) -> float:
            m = min(u, 1 - u)  # mirror around the middle
            if 0.14 < m < 0.30:
                return 0.25 * amp * math.sin((m - 0.14) / 0.16 * math.pi)
            if 0.38 < m < 0.43:
                return -0.3 * amp * (m - 0.38) / 0.05
            if 0.43 <= m <= 0.5:
                return -0.3 * amp + 1.3 * amp * (m - 0.43) / 0.07
            return 0.0

        pts = [(u / 200 * ECG_W * s, (base - y(u / 200)) * s) for u in range(201)]
        d.line(pts, fill=w, width=int(2.6 * s), joint="curve")
        img.resize((ECG_W, ECG_H), Image.LANCZOS).save(out / f"ic_ecg_{k}.png", optimize=True)

    # Stress weather, calm to stormy. Shapes in a 24 px box; a 1 px gap separates overlaps.
    def canvas():
        img = Image.new("RGBA", (24 * s, 24 * s), clear)
        return img, ImageDraw.Draw(img)

    def circle(d, cx, cy, r, fill):
        d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], fill=fill)

    def cloud(d, cx, cy, fill, grow=0.0):
        for ox, oy, r in ((-4, 1, 3.8), (1, -1.8, 5), (5.5, 1.6, 3.3)):
            circle(d, cx + ox, cy + oy, r + grow, fill)
        d.rounded_rectangle([(cx - 7.8 - grow) * s, (cy + 1 - grow) * s, (cx + 8.8 + grow) * s,
                             (cy + 5 + grow) * s], radius=(2 + grow) * s, fill=fill)

    def save(img, name):
        img.resize((24, 24), Image.LANCZOS).save(out / f"{name}.png", optimize=True)

    img, d = canvas()  # 0: sun
    circle(d, 12, 12, 5, w)
    for j in range(8):
        a = j * math.pi / 4
        d.line([((12 + 7.2 * math.cos(a)) * s, (12 + 7.2 * math.sin(a)) * s),
                ((12 + 10.2 * math.cos(a)) * s, (12 + 10.2 * math.sin(a)) * s)], fill=w, width=2 * s)
    save(img, "ic_stress_0")
    img, d = canvas()  # 1: sun behind a cloud
    circle(d, 9, 8, 5.5, w)
    cloud(d, 13.5, 13, clear, grow=1.2)
    cloud(d, 13.5, 13, w)
    save(img, "ic_stress_1")
    img, d = canvas()  # 2: cloud
    cloud(d, 12, 11, w)
    save(img, "ic_stress_2")
    img, d = canvas()  # 3: rain
    cloud(d, 12, 7.5, w)
    for dx in (-4.5, 0, 4.5):
        d.line([((12 + dx) * s, 15.5 * s), ((10.5 + dx) * s, 20.5 * s)], fill=w, width=2 * s)
    save(img, "ic_stress_3")
    img, d = canvas()  # 4: thunderstorm
    cloud(d, 12, 7.5, w)
    bolt = [(13.5, 11), (8.5, 17), (12, 17), (10, 23), (16.5, 15), (13, 15), (15, 11)]
    d.polygon([(px * s, py * s) for px, py in bolt], fill=w)
    save(img, "ic_stress_4")


# --------------------------------------------------------------------------------------
# Preview SVGs (approximate rendering of the same geometry with sample data)
# --------------------------------------------------------------------------------------
def polar(angle: float, r: float) -> tuple[float, float]:
    a = math.radians(angle)
    return C + r * math.sin(a), C - r * math.cos(a)


def svg_arc(a0: float, a1: float, r: float) -> str:
    x0, y0 = polar(a0, r)
    x1, y1 = polar(a1, r)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M {x0:.2f} {y0:.2f} A {r} {r} 0 {large} 1 {x1:.2f} {y1:.2f}"


def hex6(color: str) -> str:
    """#AARRGGBB (WFF) -> #RRGGBB (SVG)."""
    return "#" + color[-6:]


def lerp_color(colors: tuple[str, ...], t: float) -> str:
    rgb = [tuple(int(c[i:i + 2], 16) for i in (3, 5, 7)) for c in colors]
    seg = min(int(t * (len(rgb) - 1)), len(rgb) - 2)
    lt = t * (len(rgb) - 1) - seg
    a, b = rgb[seg], rgb[seg + 1]
    return "#%02X%02X%02X" % tuple(round(a[i] + (b[i] - a[i]) * lt) for i in range(3))


def preview_continuous(corner: Corner, metric: Metric, v: float, track: str, tip_col: str | None,
                       fill_opacity: float, single_accent: str | None) -> list[str]:
    parts = [f'<path d="{svg_arc(corner.start, corner.end, ARC_R)}" stroke="{track}" '
             f'stroke-opacity="{0.2 if not single_accent else 1}" stroke-width="{STROKE}" '
             f'fill="none" stroke-linecap="round"/>']
    tip = corner.anchor - SPAN * v if corner.anchor_at_end else corner.anchor + SPAN * v
    # Approximate the sweep gradient with short segments (one path in single color mode).
    steps = 1 if single_accent else max(2, int(SPAN * v / 2))
    for i in range(steps):
        t0, t1 = i / steps, (i + 1) / steps
        a0 = corner.anchor + (tip - corner.anchor) * t0
        a1 = corner.anchor + (tip - corner.anchor) * t1
        frac = (abs(a0 - corner.anchor) / SPAN)
        col = tip_col or lerp_color(metric.colors, frac)
        lo, hi = min(a0, a1), max(a0, a1)
        cap = "round" if (i in (0, steps - 1)) else "butt"
        parts.append(f'<path d="{svg_arc(lo, hi + 0.3, ARC_R)}" stroke="{col}" '
                     f'stroke-opacity="{fill_opacity:.2f}" stroke-width="{STROKE}" fill="none" '
                     f'stroke-linecap="{cap}"/>')
    kx, ky = polar(tip, ARC_R)
    parts.append(f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="5" fill="#fff"/>')
    return parts


def build_preview_svg(layout: dict[str, str], single_accent: str | None = None,
                      ambient: bool = False, meetings: tuple[tuple[str, str], ...] | None = None,
                      icons_dir: str = "") -> str:
    meetings = meetings or (("10:30", "Team standup"), ("13:00", "Design review"))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             f'width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">',
             f'<rect width="{SIZE}" height="{SIZE}" fill="#000"/>',
             '<style>text{font-family:"Google Sans","Product Sans",Roboto,"DejaVu Sans",sans-serif}</style>']
    accent = next(a for a in ACCENTS if a[0] == (single_accent or "cyan"))
    if not ambient:
        for corner in CORNERS:
            metric = METRICS[layout[corner.id]]
            v = metric.preview_value
            if single_accent:
                track, tip_col = "rgba(255,255,255,0.15)", hex6(accent[2])
                fill_opacity = (90 + 165 * v) / 255
            else:
                track = hex6(metric.colors[-1])
                tip_col = None
                fill_opacity = 1
            if metric.segments:
                n = metric.segments
                for k in range(n):
                    a0, a1 = segment_angles(corner, k, n)
                    dim = ("#FFFFFF", 0.15) if single_accent else (hex6(metric.colors[0]), 0.18)
                    parts.append(f'<path d="{svg_arc(a0, a1, ARC_R)}" stroke="{dim[0]}" stroke-opacity="{dim[1]}" '
                                 f'stroke-width="{STROKE}" fill="none"/>')
                    if v > k / n:
                        col = tip_col or hex6(segment_color(metric, k))
                        parts.append(f'<path d="{svg_arc(a0, a1, ARC_R)}" stroke="{col}" '
                                     f'stroke-opacity="{fill_opacity:.2f}" stroke-width="{STROKE}" fill="none"/>')
            elif metric.trail:
                n = len(metric.trail)
                w, h = metric.trail_size
                for k, (ix, iy, rot, image) in enumerate(trail_spots(corner, metric)):
                    col = tip_col or hex6(segment_color(metric, k))
                    op = (fill_opacity if v > k / n else TRAIL_DIM_ALPHA / 255)
                    parts.append(
                        f'<image x="{ix}" y="{iy}" width="{w}" height="{h}" opacity="{op:.2f}" '
                        f'transform="rotate({rot:.2f} {ix + w / 2} {iy + h / 2})" '
                        f'href="{icons_dir}{image}_{col[1:]}.png"/>')
            else:
                parts.extend(preview_continuous(corner, metric, v, track, tip_col, fill_opacity, single_accent))
            bx, by = badge_origin(corner)
            icol = hex6(accent[2]) if single_accent else lerp_color(metric.colors, min(v, 0.999))
            parts.append(
                f'<image x="{bx + (BADGE_W - 20) / 2}" y="{by}" width="20" height="20" '
                f'href="{icons_dir}{metric.icon}_{icol[1:]}.png"/>')
            parts.append(f'<text x="{bx + BADGE_W / 2}" y="{by + 38}" fill="#fff" font-size="16" '
                         f'font-weight="600" text-anchor="middle">{metric.preview_text}</text>')
        # Weather
        for i, (pid, label, *_r, night) in enumerate(PERIODS):
            gx = 105 + i * 80
            icon = ("ic_wx_partly_cloudy_day", "ic_wx_sunny", "ic_wx_clear_night")[i]
            temp = ("14°", "19°", "11°")[i]
            parts.append(f'<image x="{gx + 8}" y="60" width="28" height="28" href="{icons_dir}{icon}.png"/>')
            parts.append(f'<text x="{gx + 38}" y="81" fill="#fff" font-size="17" font-weight="500">{temp}</text>')
            parts.append(f'<text x="{gx + 40}" y="102" fill="#9E9E9E" font-size="11" font-weight="500" '
                         f'text-anchor="middle">{label}</text>')
    acc = hex6(accent[2])
    op = 190 / 255 if ambient else 1
    parts.append(f'<g opacity="{op:.2f}"><text x="221" y="{DATE_Y + 31}" fill="{acc}" font-size="32" font-weight="700" '
                 f'text-anchor="end">THU</text>'
                 f'<text x="231" y="{DATE_Y + 31}" fill="#fff" font-size="32" font-weight="700">12</text></g>')
    op = 215 / 255 if ambient else 1
    parts.append(f'<g opacity="{op:.2f}"><text x="210" y="{TIME_Y + 92}" fill="#fff" font-size="96" font-weight="700" '
                 f'text-anchor="end" letter-spacing="-3">10</text>'
                 f'<text x="225" y="{TIME_Y + 84}" fill="#BDBDBD" font-size="88" font-weight="700" text-anchor="middle">:</text>'
                 f'<text x="240" y="{TIME_Y + 92}" fill="#fff" font-size="96" font-weight="700" letter-spacing="-3">08</text></g>')
    if ambient:
        parts.append(preview_ambient_battery(icons_dir))
    rows = () if ambient else meetings
    for i, (t, title) in enumerate(rows):
        y = (MEET1_Y if i == 0 else MEET2_Y) + 22
        size = 22 if i == 0 else 19
        alpha = 1 if i == 0 else 0.6
        if not t:  # no title: centered, dimmed (matches the WFF "text only" branch)
            parts.append(f'<text x="{MEET_X + MEET_W / 2}" y="{y}" fill="#9E9E9E" font-size="{size - 2}" '
                         f'text-anchor="middle">{escape(title)}</text>')
            continue
        parts.append(f'<text x="{MEET_X + MEET_TITLE_W}" y="{y}" fill="{acc}" font-size="{size}" font-weight="600" '
                     f'text-anchor="end">{escape(t)}</text>'
                     f'<text x="{MEET_X + MEET_TEXT_X}" y="{y}" fill="#fff" fill-opacity="{alpha}" '
                     f'font-size="{size}">{escape(title)}</text>')
    if not ambient:
        parts.append(preview_thermometer(single_accent and acc))
    parts.append("</svg>")
    return "\n".join(parts)


def preview_ambient_battery(icons_dir: str) -> str:
    battery = METRICS["battery"]
    n, v = battery.segments or 10, battery.preview_value
    ox, oy = MEET_X, MEET1_Y
    out = [f'<g opacity="{AMB_BATT_ALPHA / 255:.2f}">',
           f'<image x="{ox}" y="{oy + (MEET_H - AMB_BATT_ICON) / 2}" width="{AMB_BATT_ICON}" '
           f'height="{AMB_BATT_ICON}" href="{icons_dir}{battery.icon}_BDBDBD.png"/>']
    for i in range(n):
        sx = ox + AMB_BATT_SEG_X + i * (AMB_BATT_SEG_W + AMB_BATT_SEG_GAP)
        lit = v > i / n
        col = hex6(segment_color(battery, i)) if lit else "#FFFFFF"
        op = 1 if lit else 0.2
        out.append(f'<rect x="{sx}" y="{oy + (MEET_H - AMB_BATT_SEG_H) / 2}" width="{AMB_BATT_SEG_W}" '
                   f'height="{AMB_BATT_SEG_H}" rx="2" fill="{col}" fill-opacity="{op}"/>')
    out.append(f'<text x="{ox + AMB_BATT_TEXT_X}" y="{oy + 22}" fill="#fff" font-size="20" '
               f'font-weight="600">{battery.preview_text}</text></g>')
    return "".join(out)


def preview_thermometer(single: str | None) -> str:
    celsius, label = THERMO_PREVIEW
    v = (celsius - THERMO_MIN_C) / (THERMO_MAX_C - THERMO_MIN_C)
    ox, oy = THERMO_X, THERMO_Y
    r = TUBE_H / 2
    color = single or hex6(thermo_band_color(celsius))
    track = "rgba(255,255,255,0.15)" if single else color
    track_op = 1 if single else 0.2
    fill_w = TUBE_H + (TUBE_W - TUBE_H) * v
    liquid = bulb = color
    return (
        f'<rect x="{ox + TUBE_X}" y="{oy + TUBE_Y}" width="{TUBE_W}" height="{TUBE_H}" rx="{r}" '
        f'fill="{track}" fill-opacity="{track_op}"/>'
        f'<rect x="{ox + TUBE_X}" y="{oy + TUBE_Y}" width="{fill_w:.1f}" height="{TUBE_H}" rx="{r}" fill="{liquid}"/>'
        f'<circle cx="{ox + BULB_D / 2}" cy="{oy + THERMO_H / 2}" r="{BULB_D / 2}" fill="{bulb}"/>'
        f'<text x="{ox + THERMO_TEXT_X}" y="{oy + 21}" fill="#fff" font-size="18" font-weight="600">{label}</text>'
    )


def write_previews() -> None:
    from PIL import Image

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    icons = PREVIEW_DIR / "icons"
    icons.mkdir(exist_ok=True)
    drawables = RES / "drawable-nodpi"
    # Pre-tinted copies of metric icons for the SVG preview.
    for metric in METRICS.values():
        base = Image.open(drawables / f"{metric.icon}.png").convert("RGBA")
        cols = ({lerp_color(metric.colors, min(metric.preview_value, 0.999))} | {hex6(a[2]) for a in ACCENTS}
                | {"#BDBDBD"})
        for col in cols:
            r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
            tinted = Image.new("RGBA", base.size, (r, g, b, 255))
            tinted.putalpha(base.getchannel("A"))
            tinted.save(icons / f"{metric.icon}_{col[1:]}.png")
    # Pre-tinted trail images: one per trail color and accent.
    for metric in METRICS.values():
        if not metric.trail:
            continue
        cols = ({hex6(segment_color(metric, k)) for k in range(len(metric.trail))}
                | {hex6(a[2]) for a in ACCENTS})
        for image in set(metric.trail):
            base = Image.open(drawables / f"{image}.png").convert("RGBA")
            for col in cols:
                r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
                tinted = Image.new("RGBA", base.size, (r, g, b, 255))
                tinted.putalpha(base.getchannel("A"))
                tinted.save(icons / f"{image}_{col[1:]}.png")
    for png in drawables.glob("ic_wx_*.png"):
        (icons / png.name).write_bytes(png.read_bytes())

    variants = {
        "preview": dict(layout=DEFAULT_LAYOUT),
        "preview_mirrored": dict(layout=FLAVORS[1][2]),
        "preview_health_top": dict(layout=FLAVORS[2][2]),
        "preview_single_cyan": dict(layout=DEFAULT_LAYOUT, single_accent="cyan"),
        "preview_single_amber": dict(layout=DEFAULT_LAYOUT, single_accent="amber"),
        "preview_ambient": dict(layout=DEFAULT_LAYOUT, ambient=True),
        "preview_no_meetings": dict(layout=DEFAULT_LAYOUT,
                                    meetings=(("", "No more meetings today"),)),
    }
    for name, kw in variants.items():
        (PREVIEW_DIR / f"{name}.svg").write_text(build_preview_svg(icons_dir="icons/", **kw))


def main() -> int:
    make_icons()
    xml = build_xml()
    raw = RES / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "watchface.xml").write_text(xml)
    write_previews()
    print(f"watchface.xml: {len(xml) / 1024:.1f} KiB, {xml.count(chr(10))} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
