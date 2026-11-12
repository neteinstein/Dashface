package com.neteinstein.dashface.provider.skin

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

/**
 * One-shot reads from the watch's skin temperature sensor, when it has one.
 *
 * The sensor is only listened to for the moment it takes to get one sample (at most
 * [TIMEOUT_MILLIS]) and is released right after, so it never stays on.
 */
object SkinTemperatureSensor {
    private const val TIMEOUT_MILLIS = 5_000L

    fun find(context: Context): Sensor? {
        val manager = context.getSystemService(SensorManager::class.java) ?: return null
        return manager.getSensorList(Sensor.TYPE_ALL).firstOrNull {
            it.type != Sensor.TYPE_AMBIENT_TEMPERATURE &&
                SkinTemperature.isSkinTemperatureSensor(it.name, it.stringType)
        }
    }

    /** Returns one plausible reading in °C, or null if none arrives in time. */
    suspend fun readOnce(context: Context, sensor: Sensor): Float? {
        val manager = context.getSystemService(SensorManager::class.java) ?: return null
        return withTimeoutOrNull(TIMEOUT_MILLIS) {
            suspendCancellableCoroutine { cont ->
                val listener = object : SensorEventListener {
                    override fun onSensorChanged(event: SensorEvent) {
                        val celsius = event.values.firstOrNull() ?: return
                        if (!SkinTemperature.isPlausible(celsius)) return
                        manager.unregisterListener(this)
                        if (cont.isActive) cont.resume(celsius)
                    }

                    override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) = Unit
                }
                cont.invokeOnCancellation { manager.unregisterListener(listener) }
                // Registration fails (returns false) without permission or on a broken sensor.
                if (!manager.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_NORMAL)) {
                    cont.resume(null)
                }
            }
        }
    }
}
