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

PROVIDER_PKG = "com.neteinstein.dashface.provider"


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
        ("#FF1E4E6B", "#FF29B6F6"),
        "clamp([BATTERY_PERCENT], 0, 100) / 100",
        "[BATTERY_PERCENT]", "%s%%", 0.98, "98%",
    ),
    "steps": Metric(
        "steps", "Steps", "ic_metric_steps",
        ("#FFE53935", "#FFFDD835", "#FF43A047"),
        "clamp([STEP_PERCENT], 0, 100) / 100",
        "[STEP_COUNT]", "%s", 0.48, "4821",
    ),
    "stress": Metric(
        "stress", "Stress", "ic_metric_stress",
        ("#FF43A047", "#FFFDD835", "#FFE53935"),
        COMP_NORM,
        "round([COMPLICATION.RANGED_VALUE_VALUE])", "%s", 0.27, "27",
    ),
    "heart": Metric(
        "heart", "Heart rate", "ic_metric_heart",
        ("#FFC2575A", "#FFFF1744"),
        "clamp(([HEART_RATE] - 40) / 140, 0, 1)",
        "[HEART_RATE] > 0 ? [HEART_RATE] : \"--\"", "%s", 0.16, "62",
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
    if second:
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
# Skin temperature thermometer (under the meetings)
# --------------------------------------------------------------------------------------
THERMO_SLOT = 12
THERMO_X, THERMO_Y, THERMO_W, THERMO_H = 135, 342, 180, 28
BULB_D = 20
TUBE_X, TUBE_Y, TUBE_W, TUBE_H = 12, 9, 96, 10
THERMO_TEXT_X = TUBE_X + TUBE_W + 8
# Cool -> neutral -> warm, ordered empty -> full like the metric gradients.
THERMO_COLORS = ("#FF29B6F6", "#FF66BB6A", "#FFFFA726")
THERMO_PREVIEW = (0.56, "33.6°")


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

    def ranged(single: bool) -> None:
        x.open("PartDraw", x=0, y=0, width=THERMO_W, height=THERMO_H)
        tube("#26FFFFFF" if single else with_alpha(THERMO_COLORS[-1], 0x33))
        # Liquid: the same rounded tube, its width following the value. It starts under the
        # bulb, so even an empty reading looks attached.
        x.open("RoundRectangle", x=TUBE_X, y=TUBE_Y, width=TUBE_W, height=TUBE_H,
               cornerRadiusX=tube_r, cornerRadiusY=tube_r)
        if single:
            x.leaf("Fill", color="[CONFIGURATION.accent.0]")
        else:
            x.open("Fill", color="#FFFFFFFF")
            x.leaf("LinearGradient", startX=TUBE_X, startY=0, endX=TUBE_X + TUBE_W, endY=0,
                   colors=" ".join(THERMO_COLORS), positions="0 0.5 1")
            x.close("Fill")
        x.leaf("Transform", target="width", value=f"{tube_r * 2:g} + {TUBE_W - tube_r * 2:g} * ({COMP_NORM})")
        x.close("RoundRectangle")
        x.close("PartDraw")
        if single:
            bulb("[CONFIGURATION.accent.0]")()
        else:
            condition(x, [
                (f"({COMP_NORM}) < 0.34", bulb(THERMO_COLORS[0])),
                (f"({COMP_NORM}) < 0.67", bulb(THERMO_COLORS[1])),
            ], bulb(THERMO_COLORS[2]))
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
            parts.append(f'<path d="{svg_arc(corner.start, corner.end, ARC_R)}" stroke="{track}" '
                         f'stroke-opacity="{0.2 if not single_accent else 1}" stroke-width="{STROKE}" '
                         f'fill="none" stroke-linecap="round"/>')
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
    rows = meetings[:1] if ambient else meetings
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


def preview_thermometer(single: str | None) -> str:
    v, label = THERMO_PREVIEW
    ox, oy = THERMO_X, THERMO_Y
    r = TUBE_H / 2
    track = "rgba(255,255,255,0.15)" if single else hex6(THERMO_COLORS[-1])
    track_op = 1 if single else 0.2
    fill_w = TUBE_H + (TUBE_W - TUBE_H) * v
    if single:
        liquid, bulb = single, single
    else:
        liquid = "url(#thermo)"
        bulb = hex6(THERMO_COLORS[0 if v < 0.34 else 1 if v < 0.67 else 2])
    stops = "".join(f'<stop offset="{i / 2:g}" stop-color="{hex6(c)}"/>' for i, c in enumerate(THERMO_COLORS))
    return (
        f'<defs><linearGradient id="thermo" gradientUnits="userSpaceOnUse" x1="{ox + TUBE_X}" y1="0" '
        f'x2="{ox + TUBE_X + TUBE_W}" y2="0">{stops}</linearGradient></defs>'
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
        cols = {lerp_color(metric.colors, min(metric.preview_value, 0.999))} | {hex6(a[2]) for a in ACCENTS}
        for col in cols:
            r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
            tinted = Image.new("RGBA", base.size, (r, g, b, 255))
            tinted.putalpha(base.getchannel("A"))
            tinted.save(icons / f"{metric.icon}_{col[1:]}.png")
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
