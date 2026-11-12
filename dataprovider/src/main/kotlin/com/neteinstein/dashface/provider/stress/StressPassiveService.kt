package com.neteinstein.dashface.provider.stress

import androidx.health.services.client.PassiveListenerService
import androidx.health.services.client.data.DataPointContainer
import androidx.health.services.client.data.DataType
import kotlin.math.abs

/**
 * Receives batched heart-rate samples from Health Services.
 *
 * Work per batch is a few arithmetic operations and one SharedPreferences write; the
 * watch face is only asked to redraw when the rounded score moved by [MIN_CHANGE] or more.
 */
class StressPassiveService : PassiveListenerService() {

    override fun onNewDataPointsReceived(dataPoints: DataPointContainer) {
        val samples = dataPoints.getData(DataType.HEART_RATE_BPM)
        if (samples.isEmpty()) return

        val store = StressStore(this)
        val bootInstant = java.time.Instant.ofEpochMilli(
            System.currentTimeMillis() - android.os.SystemClock.elapsedRealtime(),
        )
        var state = store.load()
        for (sample in samples.sortedBy { it.timeDurationFromBoot }) {
            state = StressEstimator.update(state, sample.value, sample.getTimeInstant(bootInstant).toEpochMilli())
        }
        store.save(state)

        val rounded = state.roundedScore()
        if (rounded >= 0 && abs(rounded - store.lastPublished) >= MIN_CHANGE) {
            store.lastPublished = rounded
            StressMonitoring.requestComplicationUpdate(this)
        }
    }

    private companion object {
        const val MIN_CHANGE = 3
    }
}
