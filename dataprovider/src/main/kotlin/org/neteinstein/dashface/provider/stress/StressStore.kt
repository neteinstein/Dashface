package org.neteinstein.dashface.provider.stress

import android.content.Context
import androidx.core.content.edit

/** Tiny persistent store (SharedPreferences) for the estimator state and active slots. */
class StressStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("stress", Context.MODE_PRIVATE)

    fun load() = StressState(
        baselineBpm = prefs.getFloat(KEY_BASELINE, Float.NaN).toDouble(),
        score = prefs.getFloat(KEY_SCORE, Float.NaN).toDouble(),
        lastSampleMillis = prefs.getLong(KEY_LAST, 0L),
    )

    fun save(state: StressState) = prefs.edit {
        putFloat(KEY_BASELINE, state.baselineBpm.toFloat())
        putFloat(KEY_SCORE, state.score.toFloat())
        putLong(KEY_LAST, state.lastSampleMillis)
    }

    /** Last score pushed to the watch face; used to skip redundant complication updates. */
    var lastPublished: Int
        get() = prefs.getInt(KEY_PUBLISHED, -1)
        set(value) = prefs.edit { putInt(KEY_PUBLISHED, value) }

    /** Complication instances currently showing stress; monitoring runs only while non-empty. */
    var activeComplications: Set<Int>
        get() = prefs.getStringSet(KEY_ACTIVE, emptySet())!!.mapNotNull(String::toIntOrNull).toSet()
        set(value) = prefs.edit { putStringSet(KEY_ACTIVE, value.map(Int::toString).toSet()) }

    private companion object {
        const val KEY_BASELINE = "baseline"
        const val KEY_SCORE = "score"
        const val KEY_LAST = "last"
        const val KEY_PUBLISHED = "published"
        const val KEY_ACTIVE = "active"
    }
}
