package com.neteinstein.dashface.provider.skin

import java.util.Locale
import kotlin.math.roundToInt

/** Pure helpers for the skin temperature complication (unit-tested, no Android types). */
object SkinTemperature {
    /** Range of the thermometer, in °C. Wrist skin usually sits around 31–35 °C. */
    const val MIN_C = 28f
    const val MAX_C = 38f

    /** Readings outside this range are treated as sensor noise (or a different unit). */
    private const val PLAUSIBLE_MIN_C = 20f
    private const val PLAUSIBLE_MAX_C = 45f

    /** How long a reading may be shown when a fresh one can't be taken. */
    const val MAX_AGE_MILLIS = 2 * 60 * 60 * 1000L

    /**
     * Wear OS has no standard sensor type for skin temperature, so watches that have one expose
     * it as a vendor sensor. Match it by name / string type, e.g. "Skin Temperature Sensor" or
     * "com.vendor.sensor.skin_temperature".
     */
    fun isSkinTemperatureSensor(name: String?, stringType: String?): Boolean =
        listOfNotNull(name, stringType).any { s ->
            val t = s.lowercase(Locale.ROOT)
            "skin" in t && "temp" in t
        }

    fun isPlausible(celsius: Float): Boolean =
        !celsius.isNaN() && celsius in PLAUSIBLE_MIN_C..PLAUSIBLE_MAX_C

    fun isFresh(readAtMillis: Long, nowMillis: Long): Boolean =
        readAtMillis > 0 && nowMillis - readAtMillis in 0..MAX_AGE_MILLIS

    /** Value for the RANGED_VALUE complication, clamped to the thermometer's range. */
    fun rangedValue(celsius: Float): Float = celsius.coerceIn(MIN_C, MAX_C)

    /** Short label, one decimal, in the user's unit: "33.6°". */
    fun label(celsius: Float, fahrenheit: Boolean): String {
        val v = if (fahrenheit) celsius * 9f / 5f + 32f else celsius
        val tenths = (v * 10f).roundToInt()
        val sign = if (tenths < 0) "-" else ""
        val abs = kotlin.math.abs(tenths)
        return "$sign${abs / 10}.${abs % 10}°"
    }
}
