plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.play.publisher)
}

android {
    namespace = "com.neteinstein.dashface"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.neteinstein.dashface"
        // Weather data sources need Watch Face Format v2 => Wear OS 5 (API 34)+.
        minSdk = 34
        targetSdk = 36
        // Overridden by the release workflow (GitHub Actions run number) so every release gets a
        // new, increasing versionCode without editing this file. Keep in step with the other app.
        versionCode = System.getenv("APP_VERSION_CODE")?.toIntOrNull() ?: 1
        versionName = System.getenv("APP_VERSION_NAME") ?: "1.0.0"
    }

    // Release signing comes from env vars set by .github/workflows/release.yml (KEYSTORE_BASE64
    // decoded to a file + KEYSTORE_PASSWORD / KEY_ALIAS / KEY_PASSWORD). Export the same four
    // variables to sign a release locally. Without them the release build falls back to the debug
    // key so `./gradlew assembleRelease` keeps working; the Play Console rejects debug-signed
    // uploads. The watch face and the data provider must be signed with the same key.
    signingConfigs {
        create("release") {
            System.getenv("KEYSTORE_FILE")?.let { path ->
                storeFile = file(path)
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            // Never shrink resources: the WFF runtime references them by name from XML.
            isShrinkResources = false
            signingConfig =
                if (System.getenv("KEYSTORE_FILE") != null) {
                    signingConfigs.getByName("release")
                } else {
                    signingConfigs.getByName("debug")
                }
        }
    }
}

// Uploads the release App Bundle to the Play Console (`./gradlew :watchface:publishReleaseBundle`,
// run by .github/workflows/release.yml). Authenticates with the ANDROID_PUBLISHER_CREDENTIALS env
// var: the raw JSON of a Play Console service account key. Goes to the "internal" track unless
// PLAY_TRACK says otherwise, so nothing reaches production without a promotion in the Console.
// The listing text and graphics live in store-listing/ and are not uploaded by this plugin.
play {
    track.set(System.getenv("PLAY_TRACK")?.takeIf { it.isNotBlank() } ?: "internal")
    defaultToAppBundles.set(true)
}

// ---------------------------------------------------------------------------------------
// WFF validation: `./gradlew :watchface:validateWatchFace` (also runs as part of `check`).
// ---------------------------------------------------------------------------------------
val validatorRuntime by configurations.creating

dependencies {
    validatorRuntime(project(":wff-validator"))
}

val validateWatchFace by tasks.registering(JavaExec::class) {
    group = "verification"
    description = "Validates res/raw/watchface.xml against the Watch Face Format v2 XSD."
    val xsd = rootProject.layout.projectDirectory.file("third_party/wff-xsd/2/watchface.xsd")
    val xml = layout.projectDirectory.file("src/main/res/raw/watchface.xml")
    inputs.file(xsd)
    inputs.file(xml)
    classpath = validatorRuntime
    mainClass.set("com.neteinstein.dashface.validator.MainKt")
    args(xsd.asFile.absolutePath, xml.asFile.absolutePath)
}

tasks.named("check") { dependsOn(validateWatchFace) }
