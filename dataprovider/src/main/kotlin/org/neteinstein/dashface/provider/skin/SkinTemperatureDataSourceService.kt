package org.neteinstein.dashface.provider.skin

import android.app.PendingIntent
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import androidx.core.content.edit
import androidx.core.text.util.LocalePreferences
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.NoDataComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.RangedValueComplicationData
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import androidx.wear.watchface.complications.datasource.SuspendingComplicationDataSourceService
import org.neteinstein.dashface.provider.R
import org.neteinstein.dashface.provider.permissions.Feature

/**
 * Skin temperature as a RANGED_VALUE (28–38 °C) complication, drawn as a thermometer.
 *
 * Only watches with a skin temperature sensor get data. Everywhere else this returns
 * NO_DATA and the watch face draws nothing. Each request takes one sample (see
 * [SkinTemperatureSensor]); the system asks every 15 min at most, and only while the face
 * is visible.
 */
class SkinTemperatureDataSourceService : SuspendingComplicationDataSourceService() {

    override suspend fun onComplicationRequest(request: ComplicationRequest): ComplicationData {
        val sensor = SkinTemperatureSensor.find(this) ?: return NoDataComplicationData()
        if (!Feature.SKIN_TEMPERATURE.hasForeground(this)) {
            val tap = PendingIntent.getActivity(
                this, 1,
                Feature.SKIN_TEMPERATURE.requestIntent(this).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            return build(request.complicationType, SkinTemperature.MIN_C, getString(R.string.tap_short),
                tap, getString(R.string.tap_to_allow_skin_temperature))
        }
        val prefs = getSharedPreferences("skin_temperature", Context.MODE_PRIVATE)
        val now = System.currentTimeMillis()
        val fresh = SkinTemperatureSensor.readOnce(this, sensor)
        if (fresh != null) prefs.edit { putFloat(KEY_VALUE, fresh); putLong(KEY_AT, now) }
        val celsius = fresh ?: prefs.getFloat(KEY_VALUE, Float.NaN).takeIf {
            SkinTemperature.isFresh(prefs.getLong(KEY_AT, 0L), now)
        }
        // No reading (sensor asleep, watch off-wrist): show nothing rather than a stale value.
        if (celsius == null || !SkinTemperature.isPlausible(celsius)) return NoDataComplicationData()
        return data(request.complicationType, celsius)
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData = data(type, 33.6f)

    private fun data(type: ComplicationType, celsius: Float): ComplicationData {
        val fahrenheit = LocalePreferences.getTemperatureUnit() == LocalePreferences.TemperatureUnit.FAHRENHEIT
        val label = SkinTemperature.label(celsius, fahrenheit)
        return build(type, SkinTemperature.rangedValue(celsius), label, tap = null,
            description = getString(R.string.skin_temperature_description, label))
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
        val title = PlainComplicationText.Builder(getString(R.string.skin_temperature_title)).build()
        return when (type) {
            ComplicationType.SHORT_TEXT -> ShortTextComplicationData.Builder(label, desc)
                .setTitle(title)
                .setTapAction(tap)
                .build()
            else -> RangedValueComplicationData.Builder(value, SkinTemperature.MIN_C, SkinTemperature.MAX_C, desc)
                .setText(label)
                .setTitle(title)
                .setTapAction(tap)
                .build()
        }
    }

    companion object {
        private const val KEY_VALUE = "celsius"
        private const val KEY_AT = "read_at"

        fun requestUpdate(context: Context) {
            ComplicationDataSourceUpdateRequester
                .create(context, ComponentName(context, SkinTemperatureDataSourceService::class.java))
                .requestUpdateAll()
        }
    }
}
