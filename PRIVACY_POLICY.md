# Privacy Policy

**Effective date: 12 November 2026**

This policy covers two Wear OS apps published together:

- **Dashface** (`org.neteinstein.dashface`), the watch face
- **Dashface data** (`org.neteinstein.dashface.provider`), its companion app

In this policy, "we" means the Dashface developer.

## The short version

Dashface does not collect, send or share any personal data. Neither app has internet access, and
neither contains analytics, advertising or crash-reporting code. Everything the apps read stays on
your watch.

## What the apps read, and why

The apps read the data below only on your watch. They read it only to draw it on your watch face,
and only after you allow it.

| Data | App | Used for | Permission |
|---|---|---|---|
| Heart rate | Dashface | The heart-rate bar | Body sensors / Heart rate |
| Steps | Dashface | The steps bar | Physical activity |
| Battery level, weather, date and time | Dashface | Drawn on the face | None: supplied by the watch |
| Calendar events (title and times) | Dashface data | Your next meetings under the time | Calendar |
| Heart rate | Dashface data | The stress estimate | Body sensors / Heart rate |
| Skin temperature | Dashface data | The thermometer, on watches with the sensor | Body sensors / Skin temperature |
| Heart rate and skin temperature in the background | Dashface data | Optional: keeps the stress estimate and thermometer up to date while the screen is off | Background body sensors / Health data in the background |

Dashface data also uses **Run at startup**. After a restart it uses this to resume the stress
estimate, and only if you use the stress estimate. No data is involved.

## What is stored

- **Dashface** stores nothing.
- **Dashface data** stores a few numbers in its private app storage on the watch:
  - your resting heart-rate baseline
  - the latest stress score and when it was taken
  - the latest skin temperature reading and when it was taken
  - which complications are using it

  Other apps cannot read this storage. It is excluded from cloud backup and from device-to-device
  transfer, and it is deleted when you uninstall the app. Calendar events are read when needed
  and are not stored by the app.

## What is shared

Nothing. Neither app sends any data off your watch. They have no internet permission, so they
cannot. We never receive, sell or share your data, and we cannot see it.

The watch itself shows the data on your watch face. Other apps you install on the watch follow
their own privacy policies.

## Health information

The stress estimate and skin temperature are wellness information, not medical measurements.
Dashface is not a medical device. Do not use it to diagnose, treat or prevent any condition.

## Your choices

- You can allow or deny each permission, and change it at any time in the watch's
  **Settings → Apps → Dashface / Dashface data → Permissions**.
- If you turn a permission off, the matching part of the face shows a tap-to-allow state or
  `--`.
- To delete everything Dashface data has stored, clear its storage in the watch's app settings,
  or uninstall it.

## Children

Dashface is not directed at children under 13, and it collects no data from anyone.

## Changes

If this policy changes, we will publish the new version at this address and update the effective
date above.

## Contact

Questions about privacy: open an issue at
[github.com/neteinstein/Dashface/issues](https://github.com/neteinstein/Dashface/issues).
