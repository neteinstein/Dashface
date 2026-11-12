pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "Dashface"

// WFF watch face: resources only, no code (android:hasCode="false").
include(":watchface")
// Kotlin complication data sources: next meetings (calendar) and a stress estimate.
include(":dataprovider")
// JVM tool that validates watchface.xml against the vendored WFF XSD (1.1) schema.
include(":wff-validator")
