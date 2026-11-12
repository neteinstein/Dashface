package com.neteinstein.dashface.provider.stress

import android.app.PendingIntent
import android.content.Intent
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.NoDataComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.RangedValueComplicationData
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import androidx.wear.watchface.complications.datasource.SuspendingComplicationDataSourceService
import com.neteinstein.dashface.provider.R
import com.neteinstein.dashface.provider.permissions.Feature
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Stress estimate as a RANGED_VALUE (0-100) complication.
 *
 * Push-only (UPDATE_PERIOD_SECONDS = 0): [StressPassiveService] requests an update when the
 * score changes. Monitoring is started when the complication is added to a watch face and
 * stopped when the last one is removed, so nothing runs when stress is not displayed.
 */
class StressDataSourceService : SuspendingComplicationDataSourceService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onComplicationActivated(complicationInstanceId: Int, type: ComplicationType) {
        val store = StressStore(this)
        store.activeComplications = store.activeComplications + complicationInstanceId
        scope.launch { StressMonitoring.sync(applicationContext) }
    }

    override fun onComplicationDeactivated(complicationInstanceId: Int) {
        val store = StressStore(this)
        store.activeComplications = store.activeComplications - complicationInstanceId
        scope.launch { StressMonitoring.sync(applicationContext) }
    }

    override suspend fun onComplicationRequest(request: ComplicationRequest): ComplicationData {
        if (!Feature.STRESS.hasForeground(this)) {
            val tap = PendingIntent.getActivity(
                this, 0, Feature.STRESS.requestIntent(this).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            return build(request.complicationType, value = 0f, text = getString(R.string.tap_short), tap = tap,
                description = getString(R.string.tap_to_allow_stress))
        }
        val state = StressStore(this).load()
        if (!StressEstimator.isFresh(state, System.currentTimeMillis())) {
            // The watch face shows its empty track and "--" instead of a stale number.
            return NoDataComplicationData()
        }
        val score = state.roundedScore()
        return build(request.complicationType, score.toFloat(), score.toString(), tap = null,
            description = getString(R.string.stress_description, score))
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData =
        build(type, 27f, "27", tap = null, description = getString(R.string.stress_description, 27))

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private fun build(
        type: ComplicationType,
        value: Float,
        text: String,
        tap: PendingIntent?,
        description: String,
    ): ComplicationData {
        val desc = PlainComplicationText.Builder(description).build()
        val label = PlainComplicationText.Builder(text).build()
        return when (type) {
            ComplicationType.SHORT_TEXT -> ShortTextComplicationData.Builder(label, desc)
                .setTitle(PlainComplicationText.Builder(getString(R.string.stress_title)).build())
                .setTapAction(tap)
                .build()
            else -> RangedValueComplicationData.Builder(value, 0f, 100f, desc)
                .setText(label)
                .setTitle(PlainComplicationText.Builder(getString(R.string.stress_title)).build())
                .setTapAction(tap)
                .build()
        }
    }
}
