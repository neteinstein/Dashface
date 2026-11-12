plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.neteinstein.dashface"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.neteinstein.dashface"
        // Weather data sources need Watch Face Format v2 => Wear OS 5 (API 34)+.
        minSdk = 34
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            // Never shrink resources: the WFF runtime references them by name from XML.
            isShrinkResources = false
            // Replace with your own signing config before publishing. The watch face and the
            // data provider must be signed with the same key.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
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
