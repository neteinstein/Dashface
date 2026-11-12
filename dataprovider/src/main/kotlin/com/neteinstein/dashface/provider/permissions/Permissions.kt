package com.neteinstein.dashface.provider.permissions

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build

/** The permission sets this app may ask for, resolved per Wear OS version (least privilege). */
enum class Feature {
    /** Next meetings: read the watch's synced calendar. */
    CALENDAR,

    /** Stress estimate: passive heart-rate samples, also while the screen is off. */
    STRESS,

    /** Skin temperature: one-shot reads of the watch's skin temperature sensor, if it has one. */
    SKIN_TEMPERATURE;

    /** Permissions needed while the app is in use. */
    fun foreground(): Array<String> = when (this) {
        CALENDAR -> arrayOf(Manifest.permission.READ_CALENDAR)
        STRESS -> if (isWearOs6OrLater()) {
            arrayOf(READ_HEART_RATE)
        } else {
            @Suppress("DEPRECATION")
            arrayOf(Manifest.permission.BODY_SENSORS)
        }
        SKIN_TEMPERATURE -> if (isWearOs6OrLater()) {
            arrayOf(READ_SKIN_TEMPERATURE)
        } else {
            @Suppress("DEPRECATION")
            arrayOf(Manifest.permission.BODY_SENSORS)
        }
    }

    /** Permissions that must be requested separately, after [foreground] is granted. */
    fun background(): Array<String> = when (this) {
        CALENDAR -> emptyArray()
        STRESS, SKIN_TEMPERATURE -> if (isWearOs6OrLater()) {
            arrayOf(READ_HEALTH_DATA_IN_BACKGROUND)
        } else {
            @Suppress("DEPRECATION")
            arrayOf(Manifest.permission.BODY_SENSORS_BACKGROUND)
        }
    }

    fun hasForeground(context: Context) = context.hasAll(foreground())
    fun hasAll(context: Context) = context.hasAll(foreground()) && context.hasAll(background())

    /** Intent that walks the user through granting this feature's permissions. */
    fun requestIntent(context: Context): Intent =
        Intent(context, PermissionActivity::class.java)
            .putExtra(PermissionActivity.EXTRA_FEATURE, name)

    companion object {
        // Literal names: the HealthPermissions constants only exist from API 36.
        const val READ_HEART_RATE = "android.permission.health.READ_HEART_RATE"
        const val READ_SKIN_TEMPERATURE = "android.permission.health.READ_SKIN_TEMPERATURE"
        const val READ_HEALTH_DATA_IN_BACKGROUND =
            "android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND"

        fun isWearOs6OrLater() = Build.VERSION.SDK_INT >= 36
    }
}

private fun Context.hasAll(permissions: Array<String>) = permissions.all {
    checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED
}
