# Play Console answers

Ready-made answers for every form in the Play Console, for both apps. Fill in the same answers for
**Dashface** (`org.neteinstein.dashface`) and **Dashface data**
(`org.neteinstein.dashface.provider`) unless a section says otherwise.

They are based on what the code does:

- No `INTERNET` permission in either merged manifest.
- No analytics, ads, accounts or in-app purchases.
- All data stays on the watch.

If the code changes, update these answers.

---

## Create app

| Field | Dashface | Dashface data |
|---|---|---|
| App name | Dashface Watch Face | Dashface Data – Complications |
| Default language | English (United States) – en-US | English (United States) – en-US |
| App or game | App | App |
| Free or paid | Free | Free |

## Store settings

| Field | Dashface | Dashface data |
|---|---|---|
| App category | **Personalization** | **Tools** |
| Tags | Watch face, Personalization, Wear OS | Watch face, Wear OS, Productivity |
| Email address | *your public support email (required)* | same |
| Website | https://github.com/neteinstein/Dashface | same |
| Phone | leave empty | leave empty |

### Watch face self-tags (WO-G9, Dashface only)

Under **Store presence → Store settings → Tags**, or in the watch face tag picker, pick the tags
that describe the face. Suggested: **Digital**, **Informational / Data rich**, **Health &
Fitness**, **Weather**, **Colorful**. Pick only tags that are true for the face.

## Main store listing

Copy from these files:

| Field | Dashface | Dashface data |
|---|---|---|
| App name (≤ 30) | `watchface/en-US/title.txt` | `dataprovider/en-US/title.txt` |
| Short description (≤ 80) | `watchface/en-US/short_description.txt` | `dataprovider/en-US/short_description.txt` |
| Full description (≤ 4000) | `watchface/en-US/full_description.txt` | `dataprovider/en-US/full_description.txt` |
| App icon 512 × 512 | `watchface/en-US/images/icon.png` | `dataprovider/en-US/images/icon.png` |
| Feature graphic 1024 × 500 | `watchface/en-US/images/featureGraphic.png` | `dataprovider/en-US/images/featureGraphic.png` |
| Wear OS screenshots (1:1) | `watchface/en-US/images/wearScreenshots/` (7) | `dataprovider/en-US/images/wearScreenshots/` (3) + one real capture of the app screen |
| Phone screenshots | only if the Console requires them: `watchface/en-US/images/phoneScreenshots/` (4) | only if required: reuse the watch face's |
| Video | optional: upload `docs/video/dashface.mp4` to YouTube and paste the link | optional |
| Release notes | `*/en-US/changelogs/default.txt` | same |

## App content (Policy → App content)

### Privacy policy

```
https://github.com/neteinstein/Dashface/blob/main/PRIVACY_POLICY.md
```

Use the same URL for both apps. It works once `PRIVACY_POLICY.md` is on `main`. GitHub Pages or
your own site also works, as long as the page is public, isn't a PDF and isn't geo-blocked.

### App access

**All functionality is available without special access.** There's no login and nothing behind
a paywall.

### Ads

**No, my app does not contain ads.**

### Content rating (IARC questionnaire)

- Email: your contact email
- Category: **All Other App Types** (not a game, not social, not a reference/news app)
- Answer **No** to every question:
  - Violence, fear, sexuality, language, drugs, alcohol, tobacco, gambling: No
  - Interaction between users or user-generated content: No
  - Shares the user's current physical location with other users: No
  - Allows users to purchase digital goods: No
  - Is it a web browser or search engine: No
- Expected result: **Everyone / PEGI 3 / USK 0**

### Target audience and content

- Target age groups: **18 and over**. You can add 13–15 and 16–17; nothing changes for those
  groups. Do **not** select anything under 13, which would bring in the Families policy.
- Could the app unintentionally appeal to children: **No**

### News app

**No.**

### Data safety

**Data collection and security:**

- Does your app collect or share any of the required user data types? **No.**

  Why: Google's definition of "collect" means transmitting data off the device. Data that is only
  processed on the device is not collected. Both apps read calendar, heart rate, steps and skin
  temperature only on the watch, and they have no internet permission.
- After you answer **No**, the form skips the encryption and deletion questions.
- The store listing will show **No data collected** and **No data shared**.

Optional security practices you can mention in the listing text: no internet access, no
analytics.

### Government apps

**No.**

### Financial features

**My app doesn't provide any financial features.**

### Health apps declaration

Both apps read health data (heart rate, steps, skin temperature), so declare health features:

| | Dashface | Dashface data |
|---|---|---|
| Does the app have health features? | Yes | Yes |
| Features | Activity and fitness (steps, heart rate) | Activity and fitness (heart rate); wellness / stress management (stress estimate); health data display (skin temperature) |
| Medical device / regulated? | No | No |

The Console's category names change over time. Pick the closest **non-medical** fitness and
wellness options. Both listings already carry the disclaimer that the apps are not medical
devices.

### Health permissions declaration

The Console shows this when an app requests the granular `android.permission.health.*`
permissions (Wear OS 6 / API 36). For each permission, select **Wellness / fitness** as the
use, then paste the matching justification:

| Permission | App | Justification to paste |
|---|---|---|
| `health.READ_HEART_RATE` | Dashface | The watch face draws the wearer's current heart rate as a bar on the watch face. The value is read by the Wear OS watch face renderer, shown on screen only, and never stored or sent anywhere. |
| `health.READ_HEART_RATE` | Dashface data | Computes an on-watch stress estimate: how far the current heart rate is above the user's resting baseline. It is shown as a complication on the watch face. It reuses readings the watch already takes, keeps only the baseline and latest score on the device, and never sends data off the watch. |
| `health.READ_SKIN_TEMPERATURE` | Dashface data | Shows the wearer's wrist skin temperature as a thermometer complication on the watch face, on watches with a skin temperature sensor. One reading every 15 minutes at most, only while the face is visible. The latest reading stays on the device only. |
| `health.READ_HEALTH_DATA_IN_BACKGROUND` | Dashface data | Optional and requested in a separate step. It keeps the stress estimate and thermometer current while the screen is off, using passive heart-rate data the watch already collects. Nothing leaves the device. The core features work without it. |

### Body sensors / background body sensors (Wear OS 5 and older)

`BODY_SENSORS` and `BODY_SENSORS_BACKGROUND` are capped at API 35 (`maxSdkVersion="35"`). If the
Console asks about them, use the same justifications as the heart-rate and background rows above.

### Other permissions

- `READ_CALENDAR` (Dashface data): not a restricted permission and no declaration form. It shows
  the user's next meetings on the watch face, read from the calendar synced to the watch.
- `ACTIVITY_RECOGNITION` (Dashface): the steps bar.
- `RECEIVE_BOOT_COMPLETED` (Dashface data): no declaration.
- No SMS, call log, location, all-files access, accessibility, exact alarm or foreground service
  permissions, so none of those declarations apply.

### Advertising ID

**No.** Neither app uses the advertising ID, and the AD_ID permission is not in either merged
manifest.

## Pricing and distribution

- Price: **Free**
- Countries: all, or your choice
- Form factors: **Wear OS** (Test and release → Advanced settings → Form factors → Add form factor → Wear OS)
- Contains ads: No
- Content guidelines and US export laws: accept

## Pre-review checks (Wear OS quality)

| ID | Requirement | Status |
|---|---|---|
| WO-V12 | Shows the time clearly | Yes |
| WO-P3 | Install, set and customize without crashing | Check on a real watch or emulator |
| WO-P7 | Ambient mode lights ≤ 15 % of pixels | Ambient shows only the date, time and a small battery bar |
| WO-P8 | Memory ≤ 10 MB ambient, ≤ 100 MB interactive | Run the memory-footprint tool (Development.md) |
| WO-P10 | ≤ 8 complication slots | 7 (4 stress, 2 meetings, 1 skin temperature) |
| WO-G2 | Description lists features, mentions complications, no "Android Wear" | Yes |
| WO-G4 | Icon: centered circular face touching the edges, no extra text | `watchface/en-US/images/icon.png` |
| WO-G6 | Screenshots 1:1, several permutations, no frames or extra text | `wearScreenshots/` |
| WO-G9 | Watch face self-tagged | See "Watch face self-tags" |
| WO-G11 | `watchface.xml` ≤ 10 MB | ~213 KB |
| 64-bit | Required for Wear OS apps from 15 Sep 2026 | No native code in either app |
