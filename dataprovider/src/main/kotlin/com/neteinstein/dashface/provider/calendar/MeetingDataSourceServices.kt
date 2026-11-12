package com.neteinstein.dashface.provider.calendar

import android.util.Log
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.datasource.ComplicationDataTimeline
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import androidx.wear.watchface.complications.datasource.SuspendingTimelineComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.TimeInterval
import androidx.wear.watchface.complications.datasource.TimelineEntry
import com.neteinstein.dashface.provider.permissions.Feature
import java.time.Duration
import java.time.Instant
import java.time.ZoneId

/**
 * Publishes the meeting at [position] as a complication *timeline*.
 *
 * One request returns every change for the next [HORIZON]: the system swaps entries when a
 * meeting starts or ends, so the process stays asleep instead of waking at each boundary.
 * It is only woken again by a calendar sync broadcast, a time zone change or the hourly
 * safety refresh declared in the manifest.
 */
abstract class MeetingDataSourceService(private val position: Int) :
    SuspendingTimelineComplicationDataSourceService() {

    override suspend fun onComplicationRequest(request: ComplicationRequest): ComplicationDataTimeline? {
        val complications = MeetingComplications(this)
        val type = request.complicationType
        if (!Feature.CALENDAR.hasForeground(this)) {
            return ComplicationDataTimeline(complications.permissionNeeded(type), emptyList())
        }

        val now = Instant.now()
        val until = now.plus(HORIZON)
        val zone = ZoneId.systemDefault()
        val meetings = try {
            CalendarRepository(this).meetingsBetween(now.minus(LOOKBACK), until)
        } catch (e: SecurityException) {
            return ComplicationDataTimeline(complications.permissionNeeded(type), emptyList())
        }

        val slots = MeetingTimeline.build(meetings, now, until, zone, position).take(MAX_ENTRIES)
        val entries = slots.map { slot ->
            TimelineEntry(
                TimeInterval(slot.start, slot.end),
                complications.forSlot(slot, type, zone, position),
            )
        }
        // Used outside every entry's interval, i.e. after the horizon until the next refresh.
        val fallback = complications.forSlot(
            slots.lastOrNull()?.copy(start = until, end = until.plusSeconds(1))
                ?: TimelineSlot(until, until.plusSeconds(1), null, false),
            type, zone, position,
        )
        Log.d(TAG, "position=$position meetings=${meetings.size} entries=${entries.size}")
        return ComplicationDataTimeline(fallback, entries)
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? =
        MeetingComplications(this).preview(type, position)

    private companion object {
        const val TAG = "MeetingDataSource"
        val HORIZON: Duration = Duration.ofHours(36)
        val LOOKBACK: Duration = Duration.ofHours(12) // catches meetings already in progress
        const val MAX_ENTRIES = 96
    }
}

/** "Next meeting" row. */
class NextMeetingDataSourceService : MeetingDataSourceService(position = 0)

/** "Following meeting" row. */
class SecondMeetingDataSourceService : MeetingDataSourceService(position = 1)
