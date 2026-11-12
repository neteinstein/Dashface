package org.neteinstein.dashface.provider.calendar

import java.time.Instant
import java.time.ZoneId

/** A calendar event instance that should be shown on the watch face. */
data class Meeting(
    val id: Long,
    val title: String,
    val begin: Instant,
    val end: Instant,
)

/**
 * One stretch of time during which the complication shows the same thing.
 *
 * @property meeting the meeting to show, or null when there is nothing (left) to show.
 * @property inProgress true when [meeting] has already started at [start].
 */
data class TimelineSlot(
    val start: Instant,
    val end: Instant,
    val meeting: Meeting?,
    val inProgress: Boolean,
)

/**
 * Pure logic that turns a list of meetings into a complication timeline.
 *
 * The output covers `[from, until)` with contiguous slots. A new slot starts whenever what is
 * shown could change: a meeting starts or ends, or the local date changes (so "tomorrow"
 * labels flip at midnight). The system swaps between slots on its own, which is what keeps the
 * data provider asleep for the whole day.
 */
object MeetingTimeline {

    /**
     * @param position 0 for the next meeting, 1 for the one after it.
     */
    fun build(
        meetings: List<Meeting>,
        from: Instant,
        until: Instant,
        zone: ZoneId,
        position: Int,
    ): List<TimelineSlot> {
        require(until.isAfter(from)) { "until must be after from" }
        require(position >= 0)

        val relevant = meetings
            .filter { it.end.isAfter(from) && it.begin.isBefore(until) && it.end.isAfter(it.begin) }
            .sortedWith(compareBy<Meeting>({ it.begin }, { it.end }, { it.title }, { it.id }))

        val boundaries = sortedSetOf(from, until)
        for (m in relevant) {
            if (m.begin.isAfter(from) && m.begin.isBefore(until)) boundaries += m.begin
            if (m.end.isAfter(from) && m.end.isBefore(until)) boundaries += m.end
        }
        val midnights = midnightsBetween(from, until, zone).toSet()
        boundaries += midnights

        val points = boundaries.toList()
        val slots = ArrayList<TimelineSlot>(points.size)
        for (i in 0 until points.lastIndex) {
            val start = points[i]
            val end = points[i + 1]
            val shown = relevant.filter { it.end.isAfter(start) }.getOrNull(position)
            val slot = TimelineSlot(
                start = start,
                end = end,
                meeting = shown,
                inProgress = shown != null && !shown.begin.isAfter(start),
            )
            val previous = slots.lastOrNull()
            if (previous != null && previous.sameContentAs(slot) && start !in midnights) {
                slots[slots.lastIndex] = previous.copy(end = end)
            } else {
                slots += slot
            }
        }
        return slots
    }

    private fun TimelineSlot.sameContentAs(other: TimelineSlot) =
        meeting == other.meeting && inProgress == other.inProgress

    internal fun midnightsBetween(from: Instant, until: Instant, zone: ZoneId): List<Instant> {
        val result = mutableListOf<Instant>()
        var day = from.atZone(zone).toLocalDate().plusDays(1)
        while (true) {
            // atStartOfDay handles DST gaps (e.g. zones where midnight does not exist).
            val midnight = day.atStartOfDay(zone).toInstant()
            if (!midnight.isBefore(until)) break
            if (midnight.isAfter(from)) result += midnight
            day = day.plusDays(1)
        }
        return result
    }
}
