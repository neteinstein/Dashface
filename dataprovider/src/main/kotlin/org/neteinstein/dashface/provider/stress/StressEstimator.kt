package org.neteinstein.dashface.provider.stress

import kotlin.math.max
import kotlin.math.roundToInt

/**
 * A deliberately simple, *estimated* stress score (0-100) from passive heart-rate samples.
 *
 * Wear OS has no public stress data type, so this tracks a slowly adapting resting baseline
 * and scores how far the current heart rate sits above it. It is a wellness hint, not a
 * medical measurement: exercise raises it too. Devices with an OEM stress complication
 * (e.g. Samsung Health) should use that instead; the watch face accepts any RANGED_VALUE
 * provider in the stress slot.
 *
 * Pure Kotlin so it can be unit tested without Android.
 */
data class StressState(
    val baselineBpm: Double = Double.NaN,
    val score: Double = Double.NaN,
    val lastSampleMillis: Long = 0L,
) {
    val hasScore get() = !score.isNaN()
    fun roundedScore(): Int = if (hasScore) score.roundToInt().coerceIn(0, 100) else -1
}

object StressEstimator {
    /** Baseline falls quickly toward lower heart rates ... */
    private const val BASELINE_DOWN = 0.30
    /** ... and creeps up slowly, so a stressful hour does not become the new normal. */
    private const val BASELINE_UP = 0.004
    /** Heart rate this far above baseline (bpm) maps to a score of 100. */
    private const val FULL_SCALE_BPM = 35.0
    /** Smoothing of the published score. */
    private const val SCORE_SMOOTHING = 0.35
    /** Samples older than this make the score stale (shown as "--"). */
    const val STALE_AFTER_MILLIS = 30 * 60 * 1000L

    private const val MIN_VALID_BPM = 30.0
    private const val MAX_VALID_BPM = 230.0

    fun update(state: StressState, bpm: Double, timeMillis: Long): StressState {
        if (bpm.isNaN() || bpm < MIN_VALID_BPM || bpm > MAX_VALID_BPM) return state
        if (timeMillis < state.lastSampleMillis) return state // out-of-order sample

        val stale = timeMillis - state.lastSampleMillis > STALE_AFTER_MILLIS
        val baseline = when {
            state.baselineBpm.isNaN() -> bpm
            bpm < state.baselineBpm -> state.baselineBpm + (bpm - state.baselineBpm) * BASELINE_DOWN
            else -> state.baselineBpm + (bpm - state.baselineBpm) * BASELINE_UP
        }.coerceIn(40.0, 110.0)

        val raw = (max(0.0, bpm - baseline) / FULL_SCALE_BPM * 100.0).coerceIn(0.0, 100.0)
        val score = if (!state.hasScore || stale) raw else state.score + (raw - state.score) * SCORE_SMOOTHING
        return StressState(baseline, score, timeMillis)
    }

    fun isFresh(state: StressState, nowMillis: Long) =
        state.hasScore && nowMillis - state.lastSampleMillis <= STALE_AFTER_MILLIS
}
