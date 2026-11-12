package com.neteinstein.dashface.provider.stress

import android.content.ComponentName
import android.content.Context
import android.util.Log
import androidx.health.services.client.HealthServices
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.PassiveListenerConfig
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import com.neteinstein.dashface.provider.permissions.Feature
import kotlinx.coroutines.guava.await

/**
 * Starts/stops *passive* heart-rate monitoring through Health Services.
 *
 * Passive monitoring piggybacks on the sensor sampling the system already does and delivers
 * batched data, so it never turns sensors on by itself. It is only registered while at
 * least one stress complication is on the active watch face and permission is granted.
 */
object StressMonitoring {
    private const val TAG = "StressMonitoring"

    suspend fun sync(context: Context) {
        val wanted = StressStore(context).activeComplications.isNotEmpty() &&
            Feature.STRESS.hasForeground(context)
        if (wanted) enable(context) else disable(context)
    }

    private suspend fun enable(context: Context) {
        val client = HealthServices.getClient(context).passiveMonitoringClient
        try {
            val caps = client.getCapabilitiesAsync().await()
            if (DataType.HEART_RATE_BPM !in caps.supportedDataTypesPassiveMonitoring) {
                Log.w(TAG, "Passive heart rate not supported on this device")
                return
            }
            val config = PassiveListenerConfig.builder()
                .setDataTypes(setOf(DataType.HEART_RATE_BPM))
                .build()
            client.setPassiveListenerServiceAsync(StressPassiveService::class.java, config).await()
        } catch (e: Exception) {
            Log.w(TAG, "Could not register passive heart rate listener", e)
        }
    }

    private suspend fun disable(context: Context) {
        try {
            HealthServices.getClient(context).passiveMonitoringClient
                .clearPassiveListenerServiceAsync().await()
        } catch (e: Exception) {
            Log.w(TAG, "Could not clear passive listener", e)
        }
    }

    fun requestComplicationUpdate(context: Context) {
        ComplicationDataSourceUpdateRequester
            .create(context, ComponentName(context, StressDataSourceService::class.java))
            .requestUpdateAll()
    }
}
