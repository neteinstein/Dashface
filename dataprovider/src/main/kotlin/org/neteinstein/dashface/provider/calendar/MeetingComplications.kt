package org.neteinstein.dashface.provider.calendar

import android.app.PendingIntent
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.text.format.DateFormat
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.LongTextComplicationData
import androidx.wear.watchface.complications.data.NoDataComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import org.neteinstein.dashface.provider.R
import org.neteinstein.dashface.provider.permissions.Feature
import java.time.ZoneId
import java.time.format.TextStyle
import java.util.Date
import java.util.Locale

/** Builds the complication payloads shown under the clock. */
class MeetingComplications(private val context: Context) {

    private val timeFormat = DateFormat.getTimeFormat(context) // respects the 12/24 h setting

    fun forSlot(slot: TimelineSlot, type: ComplicationType, zone: ZoneId, position: Int): ComplicationData {
        val meeting = slot.meeting
            ?: return if (position == 0) {
                text(type, title = null, body = context.getString(R.string.no_more_meetings),
                    description = context.getString(R.string.no_more_meetings))
            } else {
                // Nothing after the next meeting: render nothing in the second row.
                NoDataComplicationData()
            }

        val title = if (slot.inProgress) {
            context.getString(R.string.meeting_now)
        } else {
            timeFormat.format(Date.from(meeting.begin))
        }
        val name = meeting.title.ifBlank { context.getString(R.string.untitled_meeting) }
        val sameDay = meeting.begin.atZone(zone).toLocalDate() == slot.start.atZone(zone).toLocalDate()
        val body = if (slot.inProgress || sameDay) {
            name
        } else {
            val day = meeting.begin.atZone(zone).dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.getDefault())
            "$day · $name"
        }
        val description = context.getString(R.string.meeting_description, title, body)
        return text(type, title, body, description)
    }

    /** Shown when calendar access is missing: tapping opens the permission flow. */
    fun permissionNeeded(type: ComplicationType): ComplicationData {
        val label = context.getString(R.string.tap_to_allow_calendar)
        val tap = PendingIntent.getActivity(
            context, REQUEST_PERMISSION,
            Feature.CALENDAR.requestIntent(context).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return text(type, title = null, body = label, description = label, tap = tap)
    }

    fun preview(type: ComplicationType, position: Int): ComplicationData =
        if (position == 0) {
            text(type, "10:30", "Standup with team", "10:30 Standup with team")
        } else {
            text(type, "13:00", "Design review", "13:00 Design review")
        }

    private fun text(
        type: ComplicationType,
        title: String?,
        body: String,
        description: String,
        tap: PendingIntent? = openCalendar(),
    ): ComplicationData {
        val desc = PlainComplicationText.Builder(description).build()
        return when (type) {
            ComplicationType.SHORT_TEXT ->
                ShortTextComplicationData.Builder(PlainComplicationText.Builder(title ?: body).build(), desc)
                    .setTapAction(tap)
                    .build()
            else ->
                LongTextComplicationData.Builder(PlainComplicationText.Builder(body).build(), desc)
                    .apply { if (title != null) setTitle(PlainComplicationText.Builder(title).build()) }
                    .setTapAction(tap)
                    .build()
        }
    }

    private fun openCalendar(): PendingIntent? {
        val intent = Intent.makeMainSelectorActivity(Intent.ACTION_MAIN, Intent.CATEGORY_APP_CALENDAR)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) // started from the watch face, not an activity
        if (intent.resolveActivity(context.packageManager) == null) return null
        return PendingIntent.getActivity(
            context, REQUEST_OPEN_CALENDAR, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
    }

    companion object {
        private const val REQUEST_OPEN_CALENDAR = 1
        private const val REQUEST_PERMISSION = 2

        /** Asks the system to re-query both meeting complications (e.g. after a calendar sync). */
        fun requestUpdate(context: Context) {
            for (service in listOf(NextMeetingDataSourceService::class.java, SecondMeetingDataSourceService::class.java)) {
                ComplicationDataSourceUpdateRequester
                    .create(context, ComponentName(context, service))
                    .requestUpdateAll()
            }
        }
    }
}
