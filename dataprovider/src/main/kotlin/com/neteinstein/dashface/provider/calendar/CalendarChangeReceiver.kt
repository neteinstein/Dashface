package com.neteinstein.dashface.provider.calendar

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Refreshes the meeting timelines when the synced calendar, the clock, the time zone or the
 * locale changes. Requesting an update is cheap: the system only calls us back for
 * complications that are actually on the active watch face.
 */
class CalendarChangeReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        MeetingComplications.requestUpdate(context)
    }
}
