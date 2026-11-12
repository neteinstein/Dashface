package com.neteinstein.dashface.provider.calendar

import android.content.ContentUris
import android.content.Context
import android.provider.CalendarContract
import android.net.Uri
import androidx.core.net.toUri
import android.util.Log
import java.time.Instant
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Reads upcoming meetings from the calendar the phone syncs to the watch.
 *
 * One query, a minimal projection, run on the IO dispatcher. All-day, cancelled and declined
 * events are skipped because they are not "meetings" you need to be reminded of.
 */
class CalendarRepository(private val context: Context) {

    suspend fun meetingsBetween(from: Instant, until: Instant): List<Meeting> =
        withContext(Dispatchers.IO) {
            val uri = INSTANCES_URI.buildUpon().also {
                ContentUris.appendId(it, from.toEpochMilli())
                ContentUris.appendId(it, until.toEpochMilli())
            }.build()

            val meetings = mutableListOf<Meeting>()
            try {
                context.contentResolver.query(uri, PROJECTION, null, null, null)?.use { c ->
                    val idCol = c.getColumnIndexOrThrow(CalendarContract.Instances.EVENT_ID)
                    val titleCol = c.getColumnIndexOrThrow(CalendarContract.Instances.TITLE)
                    val beginCol = c.getColumnIndexOrThrow(CalendarContract.Instances.BEGIN)
                    val endCol = c.getColumnIndexOrThrow(CalendarContract.Instances.END)
                    val allDayCol = c.getColumnIndexOrThrow(CalendarContract.Instances.ALL_DAY)
                    val statusCol = c.getColumnIndex(CalendarContract.Instances.STATUS)
                    val selfCol = c.getColumnIndex(CalendarContract.Instances.SELF_ATTENDEE_STATUS)
                    while (c.moveToNext()) {
                        if (c.getInt(allDayCol) == 1) continue
                        if (statusCol >= 0 && !c.isNull(statusCol) &&
                            c.getInt(statusCol) == CalendarContract.Events.STATUS_CANCELED
                        ) continue
                        if (selfCol >= 0 && !c.isNull(selfCol) &&
                            c.getInt(selfCol) == CalendarContract.Attendees.ATTENDEE_STATUS_DECLINED
                        ) continue
                        meetings += Meeting(
                            id = c.getLong(idCol),
                            title = c.getString(titleCol)?.trim().orEmpty(),
                            begin = Instant.ofEpochMilli(c.getLong(beginCol)),
                            end = Instant.ofEpochMilli(c.getLong(endCol)),
                        )
                    }
                }
            } catch (e: SecurityException) {
                // Permission revoked between the check and the query: show the permission state.
                Log.w(TAG, "Calendar permission missing", e)
                throw e
            } catch (e: IllegalArgumentException) {
                // Some devices expose a reduced column set; fall back to "no meetings".
                Log.w(TAG, "Unexpected calendar schema", e)
            }
            meetings
        }

    private companion object {
        const val TAG = "CalendarRepository"

        /**
         * WearableCalendarContract.Instances.CONTENT_URI: the calendar instances the phone syncs to
         * the watch (roughly the next 24 h). Declared here to avoid depending on the legacy
         * wearable support library for a single constant.
         */
        val INSTANCES_URI: Uri =
            "content://com.google.android.wearable.provider.calendar/instances/when".toUri()
        val PROJECTION = arrayOf(
            CalendarContract.Instances.EVENT_ID,
            CalendarContract.Instances.TITLE,
            CalendarContract.Instances.BEGIN,
            CalendarContract.Instances.END,
            CalendarContract.Instances.ALL_DAY,
            CalendarContract.Instances.STATUS,
            CalendarContract.Instances.SELF_ATTENDEE_STATUS,
        )
    }
}
