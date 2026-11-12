plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.play.publisher)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.neteinstein.dashface.provider"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.neteinstein.dashface.provider"
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
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            signingConfig =
                if (System.getenv("KEYSTORE_FILE") != null) {
                    signingConfigs.getByName("release")
                } else {
                    signingConfigs.getByName("debug")
                }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions { unitTests.isReturnDefaultValues = true }
}

// Uploads the release App Bundle to the Play Console (`./gradlew :dataprovider:publishReleaseBundle`,
// run by .github/workflows/release.yml). Authenticates with the ANDROID_PUBLISHER_CREDENTIALS env
// var: the raw JSON of a Play Console service account key. Goes to the "internal" track unless
// PLAY_TRACK says otherwise, so nothing reaches production without a promotion in the Console.
// The listing text and graphics live in store-listing/ and are not uploaded by this plugin.
play {
    track.set(System.getenv("PLAY_TRACK")?.takeIf { it.isNotBlank() } ?: "internal")
    defaultToAppBundles.set(true)
}

kotlin {
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity)
    implementation(libs.wear.complications.data.source.ktx)
    implementation(libs.health.services.client)
    implementation(libs.guava)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.coroutines.guava)

    testImplementation(libs.junit)
}
