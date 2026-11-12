# Publishing Dashface on Google Play

A step-by-step guide to getting Dashface into the Play Store, and to every release after that.

Dashface is **two apps**, so it needs **two Play listings**:

| | Package | What it is |
|---|---|---|
| **Dashface** | `org.neteinstein.dashface` | The watch face (Watch Face Format, no code) |
| **Dashface data** | `org.neteinstein.dashface.provider` | Companion that provides meetings, stress and skin temperature |

A Watch Face Format bundle can't contain code, and Play rejects a bundle that mixes a watch face
with app code. So the two can't be merged into one listing.

## What's in this folder

```
store-listing/
├── SUBMISSION_GUIDE.md          ← this guide
├── play-console-answers.md      ← answers for every Play Console form
├── watchface/en-US/             ← Dashface listing
│   ├── title.txt, short_description.txt, full_description.txt
│   ├── changelogs/default.txt   ← "What's new" text
│   └── images/
│       ├── icon.png             ← 512×512, circular face (WO-G4)
│       ├── featureGraphic.png   ← 1024×500
│       ├── wearScreenshots/     ← 7 × 900×900, 1:1
│       └── phoneScreenshots/    ← 4 × 1080×1920, only if Play asks
├── dataprovider/en-US/          ← Dashface data listing (same layout)
└── tools/render_store_assets.js ← regenerates every image above
```

The layout is fastlane's `supply` metadata format, so it can also be uploaded with fastlane (see
[Optional: upload the listing with fastlane](#optional-upload-the-listing-with-fastlane)). The
privacy policy is [`PRIVACY_POLICY.md`](../PRIVACY_POLICY.md) at the repo root.

## How releases work

Every push to `main` runs [`.github/workflows/release.yml`](../.github/workflows/release.yml), which:

1. Validates the watch face, runs the unit tests and lint.
2. Builds both apps, signed with your release key. The version is `1.0.<run number>` and the
   versionCode is the run number.
3. Publishes a **GitHub Release** `v1.0.<n>` containing:
   - `Dashface_1.0.<n>-watchface.apk` and `Dashface_1.0.<n>-data.apk`: the local version, to
     install on a watch with `adb`
   - `Dashface_1.0.<n>-watchface.aab` and `Dashface_1.0.<n>-data.aab`: the files for the Play
     Console
   - `Dashface_1.0.<n>-data-mapping.txt` and `SHA256SUMS.txt`
4. **If** the `ANDROID_PUBLISHER_CREDENTIALS` secret is set, uploads both `.aab` files to the
   Play Console's **internal** track, or the track in the `PLAY_TRACK` repo variable. Without the
   secret this step is skipped and the run still succeeds.

`.github/workflows/build.yml` keeps checking every pull request.

---

## 1. One-time setup

### 1.1 Google Play developer account

1. Sign up at [play.google.com/console/signup](https://play.google.com/console/signup). There's a
   one-time fee of US$25.
2. Complete identity verification. This can take a few days.
3. **Personal accounts created after 13 Nov 2023** must run a **closed test with at least 12
   testers for 14 days in a row** before they can publish to production. Plan for this (step 7).
   Organization accounts are exempt.

### 1.2 Create the release (upload) key

Both apps must be signed with the **same key**. The watch face can only use the companion's
complications by default when they share it.

```bash
keytool -genkeypair -v -keystore dashface-release.jks -alias dashface \
  -keyalg RSA -keysize 4096 -validity 10000
```

- Keep `dashface-release.jks` and its passwords **outside the repo**, in a password manager plus
  an offline backup. If you lose it you can request an upload-key reset from Play, but it's slow.
- `*.jks` and `*.keystore` are git-ignored, so the key can't be committed by accident.

### 1.3 Add the GitHub secrets

In GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**, or use
`gh`:

```bash
base64 -w0 dashface-release.jks | gh secret set KEYSTORE_BASE64 --repo neteinstein/Dashface
```

```bash
gh secret set KEYSTORE_PASSWORD --repo neteinstein/Dashface
```

```bash
gh secret set KEY_ALIAS --repo neteinstein/Dashface --body dashface
```

```bash
gh secret set KEY_PASSWORD --repo neteinstein/Dashface
```

On macOS, use `base64 -i dashface-release.jks` instead of `base64 -w0 dashface-release.jks`.

The release workflow stops with a clear error if any of these four are missing.

### 1.4 Produce the first release

Merge to `main`, or run **Actions → Release → Run workflow**. When it finishes, open the new
release under **Releases** and download the two `.aab` files.

Use the CI-built `.aab` files for your first Play upload, not a local build. Local builds default
to versionCode 1, which can clash with the run numbers CI uses later.

To build a signed release on your own machine anyway:

```bash
export KEYSTORE_FILE=$PWD/../dashface-release.jks KEYSTORE_PASSWORD=… KEY_ALIAS=dashface KEY_PASSWORD=…
export APP_VERSION_CODE=1000 APP_VERSION_NAME=1.0.1000
./gradlew assembleRelease :watchface:bundleRelease :dataprovider:bundleRelease
```

Without `KEYSTORE_FILE`, release builds are signed with the **debug** key. They install with
`adb` but are rejected by Play.

### 1.5 Check the watch face before uploading (recommended)

Play checks the memory footprint of watch faces on upload. To catch a failure earlier, run
Google's tool locally (see [Development.md → Memory footprint](../Development.md#memory-footprint-play-requirement)):

```bash
java -jar memory-footprint.jar --watch-face Dashface_1.0.<n>-watchface.apk \
  --schema-version 2 --ambient-limit-mb 10 --active-limit-mb 100 --apply-v1-offload-limitations --estimate-optimization
```

Also go through the "still to check on a device" list in [Development.md](../Development.md) on a
real watch or emulator. Play reviewers test that the face installs, can be set and can be
customized without crashing (WO-P3).

---

## 2. Create the two apps in the Play Console

Do this twice, once per app: **Home → Create app**.

| | Dashface | Dashface data |
|---|---|---|
| App name | Dashface Watch Face | Dashface Data – Complications |
| Default language | English (United States) | English (United States) |
| App or game / Free or paid | App / Free | App / Free |

Accept the declarations. The package name is fixed by the first `.aab` you upload.

## 3. Store listing

In each app, go to **Grow users → Store presence → Main store listing**. Copy the text and upload
the images from that app's folder:

| Console field | File |
|---|---|
| App name | `<app>/en-US/title.txt` |
| Short description | `<app>/en-US/short_description.txt` |
| Full description | `<app>/en-US/full_description.txt` |
| App icon | `<app>/en-US/images/icon.png` |
| Feature graphic | `<app>/en-US/images/featureGraphic.png` |
| Wear OS screenshots | `<app>/en-US/images/wearScreenshots/*.png` |
| Phone screenshots | only if the Console won't save without them: `watchface/en-US/images/phoneScreenshots/*.png` |

Then fill in **Store settings** (category, tags, contact email, website) from
[`play-console-answers.md`](play-console-answers.md#store-settings).

### Screenshots: check them against the real face

The images here are rendered from the watch face's own design source with sample data. Play
rejects listings whose screenshots don't match the app ("Basic functionality is broken / screenshots
inaccurate"). Before you submit, compare them with the face on a watch or emulator. If anything
looks different, replace them with real captures:

1. In Android Studio, open **Device Manager → Create device → Wear OS → Wear OS Large Round**,
   with an API 34 or 35 image.
2. Install both apps from the GitHub Release with `adb install -r …`, and set Dashface as the
   watch face.
3. Grant calendar and sensor access. Add a couple of calendar events so the meeting rows show.
4. Open **Running Devices → Take screenshot** and choose **Play Store Compatible**. This gives a
   square image with no frame and no mask.
5. Capture a few permutations, as WO-G6 asks: Classic, Mirrored, Health on top, a single accent
   color, and ambient. Use the same file names in `wearScreenshots/`.

**Dashface data** must also have one screenshot of its own screen. Open the app from the watch's
app list and capture it the same way, then add it as
`dataprovider/en-US/images/wearScreenshots/4_app_screen.png`.

### Regenerating the images

After a design change:

```bash
python3 tools/generate_watchface.py
node store-listing/tools/render_store_assets.js
```

## 4. App content (policy forms)

In each app, go to **Policy → App content** and complete every item. All the answers, including
justifications you can paste, are in [`play-console-answers.md`](play-console-answers.md#app-content-policy--app-content):

- [ ] Privacy policy: `https://github.com/neteinstein/Dashface/blob/main/PRIVACY_POLICY.md`
- [ ] App access: no restrictions
- [ ] Ads: none
- [ ] Content rating: IARC questionnaire, "All Other App Types", everything No
- [ ] Target audience: 18+ (or 13+), not for children
- [ ] Data safety: **No data collected or shared**
- [ ] Health apps declaration
- [ ] Health permissions declaration (if shown), with the justifications from the answers file
- [ ] News app / Government app / Financial features: No

## 5. Add the Wear OS form factor

In each app, go to **Test and release → Advanced settings → Form factors → Add form factor →
Wear OS**. Upload the Wear OS screenshots there if you haven't already.

## 6. First upload and app signing

The Play API can't create an app's first release, so each app's first `.aab` is uploaded by hand.

1. In **Dashface data**, go to **Test and release → Testing → Internal testing → Create new
   release**.
2. Under **App signing**, keep **Play App Signing**. Google holds the app-signing key; your
   `.jks` becomes the upload key.
3. Upload `Dashface_1.0.<n>-data.aab`, paste `dataprovider/en-US/changelogs/default.txt` as the
   release notes, save, and roll out to internal testing.
4. Do the same in **Dashface** with `Dashface_1.0.<n>-watchface.aab`. In the app-signing options,
   choose **Use the same app signing key as another app in this developer account** and pick
   Dashface data. Both apps then share one signing key, which the complications need (see 1.2).
   If the option isn't offered, use **Export and upload a key from Java keystore** with the same
   `.jks` in both apps instead.
5. Add yourself as a tester (**Internal testing → Testers**), open the opt-in link on your phone,
   and install both apps on your watch from the Play Store to check them.

When you upload, Play runs the watch face's memory-footprint validation. A failure there shows up
on the release page.

## 7. Closed testing (personal accounts)

1. Go to **Testing → Closed testing → Create track**, or use the default "Alpha".
2. Promote the internal release, or upload the same `.aab`, for **both** apps.
3. Add **at least 12 testers** in an email list or Google Group. They have to opt in and keep
   the apps installed.
4. After **14 consecutive days**, go to **Dashboard → Apply for production** and answer the
   questions about your test.

## 8. Wear OS review and production

1. In each app, go to **Test and release → Advanced settings → Form factors → Wear OS → Manage**.
   Opt in and accept the Wear OS review policy.
2. Go to **Production → Create new release**, pick the tested bundle and roll out. Publish
   **Dashface data first**, or both together, because the face uses its complications.
3. Check the Wear OS review under **Advanced settings → Form factors**. It's *Pending*, then
   *Approved* or *Not approved*. A rejection email lists what to fix. Fix it, then opt in and
   publish again.

Common Wear OS rejections, and how Dashface handles them:

| Rejection | Covered by |
|---|---|
| No Wear screenshot | `wearScreenshots/` |
| Screenshots don't match the app | Check them in step 3 |
| Watch face icon not a centered circle | `watchface/en-US/images/icon.png` |
| Listing doesn't mention complications | Both descriptions do |
| Crashes while setting or customizing the face | Test on a device (1.5) |

## 9. Automate Play uploads (optional, after step 6)

Once each app has its first manual release, CI can upload every new release by itself.

1. **Google Cloud:** create or pick a project, enable the **Google Play Android Developer API**,
   then go to **IAM → Service accounts → Create**. Open the new account, go to **Keys → Add key →
   JSON**, and download the file.
2. **Play Console → Users and permissions → Invite new users:** enter the service account's
   `client_email`. Give it access to **both** apps with at least **Release apps to testing
   tracks**. Add **Release to production…** if you'll set `PLAY_TRACK=production`.
3. Add the JSON's contents as a secret:

   ```bash
   gh secret set ANDROID_PUBLISHER_CREDENTIALS --repo neteinstein/Dashface < play-service-account.json
   ```

4. Optional: choose the track (`internal` by default; also `alpha`, `beta` or `production`):

   ```bash
   gh variable set PLAY_TRACK --repo neteinstein/Dashface --body internal
   ```

From then on, every push to `main` creates the GitHub Release and uploads both bundles to that
track. You then promote them in the Console. New permissions can take a few hours to start
working on Google's side.

## 10. Every release after the first

1. Update `store-listing/*/en-US/changelogs/default.txt`, and the listing text if features
   changed.
2. If the face changed, regenerate the images and screenshots (step 3).
3. Merge to `main`. CI builds, tags `v1.0.<n>`, publishes the APKs and AABs, and uploads to Play
   if step 9 is set up.
4. Without step 9, upload both `.aab` files from the GitHub Release by hand.
5. In the Console, paste the release notes, then promote internal → closed → production.

### Optional: upload the listing with fastlane

The listing text and images can be pushed without clicking through the Console:

```bash
fastlane supply --json_key play-service-account.json --package_name org.neteinstein.dashface \
  --metadata_path store-listing/watchface --skip_upload_apk true --skip_upload_aab true --skip_upload_changelogs true
```

```bash
fastlane supply --json_key play-service-account.json --package_name org.neteinstein.dashface.provider \
  --metadata_path store-listing/dataprovider --skip_upload_apk true --skip_upload_aab true --skip_upload_changelogs true
```

## Troubleshooting

**Release workflow fails at "Validate required secrets".** One of the four signing secrets is
missing (step 1.3).

**Play upload fails with `403 PERMISSION_DENIED`.** The cause is almost always on the Play side.
Check, in order:

1. The service account is invited to **that app** with release permission.
2. That app already has a manual first release (step 6).
3. The Play Android Developer API is enabled in the key's Cloud project.
4. The permission is new: wait a few hours and re-run.

**"Version code N has already been used".** Each upload needs a higher versionCode. Re-run the
workflow, which gets a new run number, rather than re-uploading an old `.aab`.

**"Your app bundle is signed with the wrong key".** The `.aab` wasn't signed with the upload key
Play registered. Check the `KEYSTORE_*` secrets match the `.jks` from step 1.2.

**"You uploaded a debuggable / debug-signed bundle".** It was built without `KEYSTORE_FILE`. Use
the CI artifacts.

**Watch face upload rejected for memory.** Run the memory-footprint tool (1.5). Large images or
too many layers in ambient mode are the usual cause.

**The face doesn't pick up the companion's complications by default.** The two apps are signed
with different app-signing keys. Use **Use the same app signing key as another app** (step 6).
Otherwise, users can pick the sources once in the face's editor.

## Final checklist

- [ ] Developer account verified; closed test (12 testers × 14 days) done if it's a personal account
- [ ] Release key created and backed up; 4 signing secrets set
- [ ] GitHub Release produced; both `.aab` files downloaded
- [ ] Memory footprint checked; face tested on a device or emulator
- [ ] Both apps created; listings filled from `store-listing/`
- [ ] Screenshots compared with the real face; companion app-screen screenshot added
- [ ] App content forms done for both apps (see `play-console-answers.md`)
- [ ] Privacy policy URL is live (PRIVACY_POLICY.md merged to `main`)
- [ ] Wear OS form factor added and opted in for both apps
- [ ] Both apps share one app-signing key
- [ ] Production rollout: Dashface data first, then Dashface
- [ ] Optional: service account set up for automated uploads
