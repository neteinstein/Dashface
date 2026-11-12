package org.neteinstein.dashface.provider.permissions

import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import org.neteinstein.dashface.provider.R
import org.neteinstein.dashface.provider.skin.SkinTemperatureSensor

/** Launcher screen: what this companion does, privacy note, and shortcuts to grant access. */
class HomeActivity : ComponentActivity() {

    private lateinit var calendarButton: Button
    private lateinit var stressButton: Button
    private var skinButton: Button? = null

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
        // Only offered on watches that actually have a skin temperature sensor.
        if (SkinTemperatureSensor.find(this) != null) {
            skinButton = Button(this).apply {
                setOnClickListener { startActivity(Feature.SKIN_TEMPERATURE.requestIntent(this@HomeActivity)) }
            }.also(column::addView)
        }
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
        skinButton?.setText(
            if (Feature.SKIN_TEMPERATURE.hasForeground(this)) R.string.home_skin_on else R.string.home_skin_off,
        )
    }
}
