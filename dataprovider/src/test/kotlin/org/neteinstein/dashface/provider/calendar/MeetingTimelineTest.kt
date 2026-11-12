package org.neteinstein.dashface.provider.calendar

import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MeetingTimelineTest {

    private val zone = ZoneId.of("Europe/Lisbon")

    private fun at(text: String): Instant = LocalDateTime.parse(text).atZone(zone).toInstant()

    private fun meeting(id: Long, begin: String, end: String, title: String = "M$id") =
        Meeting(id, title, at(begin), at(end))

    @Test
    fun emptyCalendarProducesOneEmptySlotPerDay() {
        val slots = MeetingTimeline.build(emptyList(), at("2026-11-12T08:00"), at("2026-11-12T20:00"), zone, 0)
        assertEquals(1, slots.size)
        assertNull(slots.single().meeting)
        assertEquals(at("2026-11-12T08:00"), slots.single().start)
        assertEquals(at("2026-11-12T20:00"), slots.single().end)
    }

    @Test
    fun slotsSwitchAtMeetingStartAndEnd() {
        val standup = meeting(1, "2026-11-12T09:00", "2026-11-12T09:15")
        val review = meeting(2, "2026-11-12T11:00", "2026-11-12T12:00")
        val slots = MeetingTimeline.build(
            listOf(review, standup), at("2026-11-12T08:00"), at("2026-11-12T13:00"), zone, 0,
        )

        assertEquals(
            listOf(
                Triple(at("2026-11-12T08:00"), standup, false),
                Triple(at("2026-11-12T09:00"), standup, true),
                Triple(at("2026-11-12T09:15"), review, false),
                Triple(at("2026-11-12T11:00"), review, true),
                Triple(at("2026-11-12T12:00"), null, false),
            ),
            slots.map { Triple(it.start, it.meeting, it.inProgress) },
        )
        // Contiguous, no gaps or overlaps.
        slots.zipWithNext().forEach { (a, b) -> assertEquals(a.end, b.start) }
    }

    @Test
    fun secondPositionShowsTheFollowingMeeting() {
        val a = meeting(1, "2026-11-12T09:00", "2026-11-12T10:00")
        val b = meeting(2, "2026-11-12T11:00", "2026-11-12T12:00")
        val slots = MeetingTimeline.build(listOf(a, b), at("2026-11-12T08:00"), at("2026-11-12T13:00"), zone, 1)

        assertEquals(b, slots.first().meeting)
        assertFalse(slots.first().inProgress)
        // After the first meeting ends, nothing follows the next one.
        assertNull(slots.first { it.start == at("2026-11-12T10:00") }.meeting)
    }

    @Test
    fun overlappingMeetingsAreOrderedByStartTime() {
        val long = meeting(1, "2026-11-12T09:00", "2026-11-12T12:00", "Workshop")
        val short = meeting(2, "2026-11-12T10:00", "2026-11-12T10:30", "1:1")
        val first = MeetingTimeline.build(listOf(short, long), at("2026-11-12T09:30"), at("2026-11-12T13:00"), zone, 0)
        val second = MeetingTimeline.build(listOf(short, long), at("2026-11-12T09:30"), at("2026-11-12T13:00"), zone, 1)

        assertEquals(long, first.first().meeting)
        assertTrue(first.first().inProgress)
        assertEquals(short, second.first().meeting)
        // Once the 1:1 ends only the workshop is left, so the second row empties.
        assertNull(second.first { it.start == at("2026-11-12T10:30") }.meeting)
    }

    @Test
    fun meetingAlreadyInProgressAtStartIsShownAsNow() {
        val m = meeting(1, "2026-11-12T07:30", "2026-11-12T08:30")
        val slots = MeetingTimeline.build(listOf(m), at("2026-11-12T08:00"), at("2026-11-12T09:00"), zone, 0)
        assertEquals(m, slots.first().meeting)
        assertTrue(slots.first().inProgress)
    }

    @Test
    fun endedAndZeroLengthMeetingsAreIgnored() {
        val ended = meeting(1, "2026-11-12T06:00", "2026-11-12T07:00")
        val zero = meeting(2, "2026-11-12T10:00", "2026-11-12T10:00")
        val slots = MeetingTimeline.build(listOf(ended, zero), at("2026-11-12T08:00"), at("2026-11-12T12:00"), zone, 0)
        assertTrue(slots.all { it.meeting == null })
    }

    @Test
    fun midnightSplitsSlotsSoDayLabelsUpdate() {
        val tomorrow = meeting(1, "2026-11-13T09:00", "2026-11-13T10:00")
        val slots = MeetingTimeline.build(listOf(tomorrow), at("2026-11-12T20:00"), at("2026-11-13T12:00"), zone, 0)
        assertEquals(at("2026-11-13T00:00"), slots[1].start)
        assertEquals(tomorrow, slots[0].meeting)
        assertEquals(tomorrow, slots[1].meeting)
    }

    @Test
    fun daylightSavingTransitionKeepsTimelineContiguous() {
        // Europe/Lisbon falls back from 02:00 to 01:00 on 2026-10-25.
        val m = meeting(1, "2026-10-25T09:00", "2026-10-25T10:00")
        val from = at("2026-10-24T22:00")
        val until = at("2026-10-25T12:00")
        val slots = MeetingTimeline.build(listOf(m), from, until, zone, 0)

        assertEquals(from, slots.first().start)
        assertEquals(until, slots.last().end)
        slots.zipWithNext().forEach { (a, b) -> assertEquals(a.end, b.start) }
        assertTrue(slots.any { it.start == at("2026-10-25T00:00") })
        assertTrue(slots.any { it.start == m.begin && it.inProgress })
    }

    @Test
    fun midnightsHandleZonesWithoutMidnight() {
        // America/Santiago skipped 00:00 -> 01:00 on 2026-09-06; start of day is 01:00.
        val santiago = ZoneId.of("America/Santiago")
        val from = LocalDateTime.parse("2026-09-05T12:00").atZone(santiago).toInstant()
        val until = LocalDateTime.parse("2026-09-06T12:00").atZone(santiago).toInstant()
        val midnights = MeetingTimeline.midnightsBetween(from, until, santiago)
        assertEquals(1, midnights.size)
        assertEquals(java.time.LocalDate.parse("2026-09-06"), midnights.single().atZone(santiago).toLocalDate())
    }
}
