package org.neteinstein.dashface.provider.stress

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class StressEstimatorTest {

    private val minute = 60_000L

    private fun feed(vararg bpm: Double, start: StressState = StressState(), t0: Long = 0L): StressState =
        bpm.foldIndexed(start) { i, s, v -> StressEstimator.update(s, v, t0 + i * minute) }

    @Test
    fun restingHeartRateScoresLow() {
        val s = feed(*DoubleArray(30) { 60.0 })
        assertEquals(0, s.roundedScore())
    }

    @Test
    fun elevatedHeartRateRaisesTheScore() {
        val rest = feed(*DoubleArray(60) { 60.0 })
        val elevated = feed(*DoubleArray(10) { 85.0 }, start = rest, t0 = 60 * minute)
        assertTrue("score=${elevated.roundedScore()}", elevated.roundedScore() in 50..80)
    }

    @Test
    fun scoreIsClampedTo100() {
        val rest = feed(*DoubleArray(60) { 55.0 })
        val high = feed(*DoubleArray(20) { 180.0 }, start = rest, t0 = 60 * minute)
        assertEquals(100, high.roundedScore())
    }

    @Test
    fun baselineDropsQuicklyAndRisesSlowly() {
        val start = feed(70.0)
        val lower = StressEstimator.update(start, 50.0, minute)
        val higher = StressEstimator.update(start, 100.0, minute)
        assertTrue(70.0 - lower.baselineBpm > 5)
        assertTrue(higher.baselineBpm - 70.0 < 1)
    }

    @Test
    fun invalidAndOutOfOrderSamplesAreIgnored() {
        val s = feed(60.0, 61.0)
        assertEquals(s, StressEstimator.update(s, 0.0, 10 * minute))
        assertEquals(s, StressEstimator.update(s, Double.NaN, 10 * minute))
        assertEquals(s, StressEstimator.update(s, 300.0, 10 * minute))
        assertEquals(s, StressEstimator.update(s, 90.0, 0L))
    }

    @Test
    fun scoreGoesStaleWithoutSamples() {
        val s = feed(60.0, 60.0)
        assertTrue(StressEstimator.isFresh(s, s.lastSampleMillis + minute))
        assertFalse(StressEstimator.isFresh(s, s.lastSampleMillis + StressEstimator.STALE_AFTER_MILLIS + 1))
        assertFalse(StressEstimator.isFresh(StressState(), 0L))
    }
}
