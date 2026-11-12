package com.neteinstein.dashface.provider.permissions

import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import com.neteinstein.dashface.provider.R

/** Launcher screen: what this companion does, privacy note, and shortcuts to grant access. */
class HomeActivity : ComponentActivity() {

    private lateinit var calendarButton: Button
    private lateinit var stressButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pad = (resources.displayMetrics.widthPixels * 0.12f).toInt()
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(pad, pad, pad, pad)
        }
        column.addView(TextView(this).apply {
            setText(R.string.home_body)
            textSize = 14f
            gravity = Gravity.CENTER
        })
        calendarButton = Button(this).apply {
            setOnClickListener { startActivity(Feature.CALENDAR.requestIntent(this@HomeActivity)) }
        }
        stressButton = Button(this).apply {
            setOnClickListener { startActivity(Feature.STRESS.requestIntent(this@HomeActivity)) }
        }
        column.addView(calendarButton)
        column.addView(stressButton)
        column.addView(TextView(this).apply {
            setText(R.string.privacy_note)
            textSize = 12f
            gravity = Gravity.CENTER
            alpha = 0.7f
        })
        setContentView(ScrollView(this).apply { addView(column) })
    }

    override fun onResume() {
        super.onResume()
        calendarButton.setText(
            if (Feature.CALENDAR.hasForeground(this)) R.string.home_calendar_on else R.string.home_calendar_off,
        )
        stressButton.setText(
            if (Feature.STRESS.hasForeground(this)) R.string.home_stress_on else R.string.home_stress_off,
        )
    }
}
