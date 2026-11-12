# Role
You are a senior Wear OS engineer and watch-face designer. Build a production-ready,
battery-efficient Wear OS watch face called **Dashface** using **Watch Face Format (WFF)**,
plus a tiny Kotlin companion **data-provider app** for data WFF cannot read natively.
Before writing code, check the latest official docs (developer.android.com/training/wearables/wff)
for exact data-source names, WFF version features and permission names — do not guess APIs.

# 1. Architecture (non-negotiable)
Gradle multi-module project:
- `:watchface` — WFF only. `android:hasCode="false"`, no Kotlin, `res/raw/watchface.xml`,
  `res/xml/watch_face_info.xml`, vector drawables, one subsetted font. Min WFF version 2
  (needed for weather); gate newer features (v3/v4) behind version checks / fallbacks.
- `:dataprovider` — Kotlin, Jetpack Wear complications data source APIs, coroutines.
  Provides: **Next meetings** (LONG_TEXT + LIST-like multi-slot via 2 LONG_TEXT complications)
  and optionally **Stress** (RANGED_VALUE) when no OEM provider exists.
- `:shared` (optional) — constants, formatting, tests.
No phone app unless strictly needed. No network calls of our own — weather comes from the
platform WFF weather sources.

Data flow:
| Element | Source | Mechanism |
|---|---|---|
| Battery | `[BATTERY_PERCENT]` | WFF native |
| Steps | `[STEP_COUNT]`, `[STEP_GOAL]`/`[STEP_PERCENT]` | WFF native |
| Heart rate | `[HEART_RATE]` | WFF native |
| Stress | RANGED_VALUE complication slot (default: OEM provider e.g. Samsung Health; fallback: our provider) | Complication |
| Weather | `[WEATHER.*]` hourly/daily sources | WFF native |
| Calendar | our `:dataprovider` reading `WearableCalendarContract.Instances` | Timeline complication |

# 2. Battery & performance rules
- **Never wake the CPU on a timer.** Calendar provider must be a
  *timeline* complication data source: publish the whole day's entries with
  `validTimeRange`s so the system swaps "next meeting" at event boundaries without
  waking our process. Re-query on `ACTION_PROVIDER_CHANGED` for the calendar, time/zone
  changes, and at most an hourly safety refresh (`UPDATE_PERIOD_SECONDS` = 3600; the
  system batches it and skips it while the screen is off).
- No wakelocks, no foreground services, no polling, no AlarmManager exact alarms.
- Health data: rely on WFF native sources (system-batched). If we provide stress
  ourselves, use Health Services **passive** monitoring only — never active sensors.
- No seconds hand / seconds digits. Time updates once per minute.
- Vector assets only; no full-screen bitmaps; one font, subsetted to needed glyphs.
- Minimize layers/overdraw: draw arc "track" + "fill" only; avoid nested transforms,
  per-frame expressions and continuous animations. Max one tap animation, ≤300 ms.
- **Ambient (AOD) variant:** black background, time + date + next meeting only,
  arcs reduced to 1–2 px outlines or hidden, total lit pixels < 15%, no gradients,
  no weather icons. Use `<Variant mode="AMBIENT">`.
- Must pass Google's **WFF validator** and **memory footprint** tools
  (ambient and interactive budgets) — wire them into a Gradle check task.

# 3. Visual layout (450×450 canvas, round, pure black #000 background)
Reference: four thick rounded arcs hugging the bezel, separated by small gaps at
12, 3, 6, 9 o'clock with a small icon in each gap; content centered.

Top → bottom center column:
1. **Weather row** – 3 small icons with tiny labels: **Morning · Afternoon · Night**
   (current conditions while inside the period; otherwise the hourly forecast for
   ~09:00 / ~15:00 / ~21:00 when it is within the 8 hours WFF exposes
   (`WEATHER.HOURS.1..8`), else the daily day/night forecast). Optional temp next to each. If `[WEATHER.IS_AVAILABLE]`
   is false, hide the row (no placeholder clutter).
2. **Date** – `THU 12`: weekday in accent cyan (#29B6F6), day number white, bold, ~34 sp.
3. **Time** – `HH:mm` (respect 12/24h system setting), huge white rounded bold font
   (~110 sp), colon slightly dimmer.
4. **Next meetings** (replaces the hourly weather of the reference) – up to 2 rows:
   - `10:30  Standup with team` (time in accent, title white, ellipsize ~18 chars)
   - second row dimmer (60% opacity).
   - If a meeting is in progress: `Now · Design review` with a thin progress underline.
   - Empty state: `No more meetings today` in 50% gray.
   - Tap → opens the calendar app (complication tap action).

# 4. Corner arcs (default placement)
| Corner | Metric | Color behavior (value 0 → 100%) |
|---|---|---|
| Top-left | Battery | Blue: low = desaturated/dim blue (#1E4E6B) → full = vivid cyan (#29B6F6) |
| Top-right | Steps | Red → Yellow → Green as goal fills (#E53935 → #FDD835 → #43A047) |
| Bottom-left | Stress | Green → Yellow → Red (#43A047 → #FDD835 → #E53935) |
| Bottom-right | Heart rate | Calm red (#C2575A) → urgent saturated red (#FF1744); range 40–180 bpm |

Implementation of fading colors (cheap, no per-frame color math):
- Each arc = a dim **track** (same hue, 20% opacity) + a **fill** arc whose sweep is bound
  to the normalized value via an expression.
- Apply a `SweepGradient` (or `LinearGradient` along the arc) spanning the **whole** arc
  length to the fill, so the color at the fill's tip naturally reflects the value
  (empty = start color, full = end color). Gradient direction must follow fill direction.
- A small white knob/dot at the fill tip, and the numeric value (e.g. `98%`, `62`,
  `4 821`) set along the arc in the arc's tip color.
- Each gap icon (battery, shoe, brain/leaf, heart) tinted with the arc's current tip color.
- Stroke ~14 px, round caps, arcs inset 8 px from bezel.

# 5. Customization (WFF `UserConfigurations`)
- **Arc layout**: one `ListConfiguration` per corner (TL/TR/BL/BR) choosing
  Battery / Steps / Stress / Heart rate, plus presets: *Default*, *Mirrored*,
  *Health on top*. Each metric keeps its own color logic wherever it is placed;
  arc fill direction mirrors per side so bars always grow away from the 12/6 o'clock gap.
- **Color mode**: `ListConfiguration` → *Multicolor (default)* / *Single color*.
  Single color uses one `ColorConfiguration` accent (options: cyan, white, green, amber,
  purple) for all arcs, keeping the value→intensity fade (dim → full accent).
- **Show weather row** (Boolean), **Meetings rows: 1 / 2** (List),
  **Show values on arcs** (Boolean).
- Stress slot is a real complication slot, so the user can pick any RANGED_VALUE provider
  in the system editor. Note: `ComplicationSlot` is only allowed at the top level of the
  `Scene` (not inside a `ListConfiguration`), so to let Stress move between corners use one
  slot per corner and render it only when that corner is set to Stress.
- Ship sensible defaults; all options must also apply to the ambient variant.

# 6. Permissions (handle properly, least privilege)
- `:watchface`: declare only what WFF requires for the data sources used
  (heart rate → body-sensor permission; check per API level: `BODY_SENSORS` with
  `maxSdkVersion` for older, `android.permission.health.READ_HEART_RATE` on Wear OS 6+;
  steps → `ACTIVITY_RECOGNITION` if required). Verify the exact list in the WFF docs.
- `:dataprovider`: `READ_CALENDAR` (+ the Wear calendar permission if required),
  and health permissions only if the stress fallback is enabled.
- Runtime flow: a minimal permission Activity in `:dataprovider` launched from the
  complication tap when permission is missing; show a short rationale screen first;
  handle "denied" and "don't ask again" (deep-link to app settings).
- **Graceful degradation**: missing permission → complication shows a
  `NoPermissionComplicationData` / "Tap to allow" state; arcs show the track only with
  `--`; never crash or show stale data as current.
- No data leaves the device. No analytics. Document this in a privacy note.

# 7. Code quality
- Kotlin, coroutines, no blocking I/O on main; repository pattern for calendar queries
  (single query for today+tomorrow, projection limited to needed columns,
  exclude declined/all-day events, configurable).
- Unit tests: meeting selection/timeline building, time-zone & DST edges, all-day,
  overlapping meetings, empty calendar. Screenshot tests for the face in
  interactive/ambient, round/small screens, single-color mode, missing-permission states.
- Accessibility: content descriptions for complications; min contrast 4.5:1 for text.
- Localization-ready strings; weekday/date via locale formatting.

# 8. Deliverables
1. Full project tree with all files, buildable with `./gradlew assembleRelease`.
2. `README.md`: architecture diagram, data flow, how to install on emulator/device,
   how to run validator + memory footprint check, battery rationale.
3. Preview images (`watch_face_preview` for each preset) and a changelog.
4. A short list of any assumptions you made and anything you could not verify in docs.

# Acceptance checklist
- [ ] Zero background wakeups from our app over 1 h idle (`adb shell dumpsys batterystats`).
- [ ] Validator + memory footprint pass.
- [ ] Ambient < 15% lit pixels, no gradients.
- [ ] Colors fade correctly at 0%, 50%, 100% for every metric in every corner.
- [ ] Next meeting switches at event start/end without our process running.
- [ ] Every permission denial path shows a clear, tappable recovery state.
- [ ] Swapping arc positions and single-color mode work in interactive and ambient.
