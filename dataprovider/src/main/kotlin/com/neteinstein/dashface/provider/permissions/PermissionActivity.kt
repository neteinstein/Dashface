package com.neteinstein.dashface.provider.permissions

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.lifecycleScope
import com.neteinstein.dashface.provider.R
import com.neteinstein.dashface.provider.calendar.MeetingComplications
import com.neteinstein.dashface.provider.skin.SkinTemperatureDataSourceService
import com.neteinstein.dashface.provider.stress.StressMonitoring
import kotlinx.coroutines.launch

/**
 * Rationale-first permission flow, launched from a "Tap to allow" complication.
 *
 * 1. Explain why access is needed and what stays on the watch.
 * 2. Ask for the foreground permission(s).
 * 3. For stress only: explain and ask for background access as a separate step (required by
 *    the platform, and it lets the estimate update while the screen is off).
 * 4. On "don't ask again", offer the app's system settings page instead of a dead button.
 * Finally refresh the complications so the watch face reflects the new state immediately.
 */
class PermissionActivity : ComponentActivity() {

    private lateinit var feature: Feature
    private lateinit var title: TextView
    private lateinit var body: TextView
    private lateinit var primary: Button
    private lateinit var secondary: Button
    private var step = Step.FOREGROUND

    private enum class Step { FOREGROUND, BACKGROUND, SETTINGS }

    private val request = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        onResult(granted = result.values.all { it })
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        feature = intent.getStringExtra(EXTRA_FEATURE)
            ?.let { runCatching { Feature.valueOf(it) }.getOrNull() } ?: Feature.CALENDAR
        setContentView(buildLayout())
        render()
    }

    override fun onResume() {
        super.onResume()
        // Returning from system settings: the user may have granted access there.
        if (step == Step.SETTINGS && feature.hasForeground(this)) finishWithRefresh()
    }

    private fun render() {
        when {
            feature.hasAll(this) -> finishWithRefresh()
            feature.hasForeground(this) -> showStep(Step.BACKGROUND)
            else -> showStep(Step.FOREGROUND)
        }
    }

    private fun showStep(next: Step) {
        step = next
        when (next) {
            Step.FOREGROUND -> {
                title.setText(
                    when (feature) {
                        Feature.CALENDAR -> R.string.perm_calendar_title
                        Feature.STRESS -> R.string.perm_stress_title
                        Feature.SKIN_TEMPERATURE -> R.string.perm_skin_title
                    },
                )
                body.setText(
                    when (feature) {
                        Feature.CALENDAR -> R.string.perm_calendar_body
                        Feature.STRESS -> R.string.perm_stress_body
                        Feature.SKIN_TEMPERATURE -> R.string.perm_skin_body
                    },
                )
                primary.setText(R.string.perm_allow)
            }
            Step.BACKGROUND -> {
                title.setText(R.string.perm_background_title)
                body.setText(
                    if (feature == Feature.SKIN_TEMPERATURE) R.string.perm_skin_background_body
                    else R.string.perm_background_body,
                )
                primary.setText(R.string.perm_allow)
            }
            Step.SETTINGS -> {
                title.setText(R.string.perm_denied_title)
                body.setText(R.string.perm_denied_body)
                primary.setText(R.string.perm_open_settings)
            }
        }
    }

    private fun onPrimary() {
        when (step) {
            Step.FOREGROUND -> request.launch(feature.foreground())
            Step.BACKGROUND -> request.launch(feature.background())
            Step.SETTINGS -> startActivity(
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", packageName, null)),
            )
        }
    }

    private fun onResult(granted: Boolean) {
        val asked = if (step == Step.BACKGROUND) feature.background() else feature.foreground()
        when {
            granted && step == Step.FOREGROUND && feature.background().isNotEmpty() -> showStep(Step.BACKGROUND)
            granted -> finishWithRefresh()
            // Background access is optional: the estimate then updates only while in use.
            step == Step.BACKGROUND -> finishWithRefresh()
            // No rationale after a denial means "don't ask again": only settings can help now.
            asked.none { shouldShowRequestPermissionRationale(it) } -> showStep(Step.SETTINGS)
            else -> showStep(Step.FOREGROUND)
        }
    }

    private fun finishWithRefresh() {
        lifecycleScope.launch {
            when (feature) {
                Feature.CALENDAR -> MeetingComplications.requestUpdate(applicationContext)
                Feature.STRESS -> {
                    StressMonitoring.sync(applicationContext)
                    StressMonitoring.requestComplicationUpdate(applicationContext)
                }
                Feature.SKIN_TEMPERATURE -> SkinTemperatureDataSourceService.requestUpdate(applicationContext)
            }
            finish()
        }
    }

    private fun buildLayout(): ScrollView {
        val pad = (resources.displayMetrics.widthPixels * 0.12f).toInt()
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(pad, pad, pad, pad)
        }
        title = TextView(this).apply {
            textSize = 17f
            gravity = Gravity.CENTER
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        body = TextView(this).apply {
            textSize = 14f
            gravity = Gravity.CENTER
            setPadding(0, pad / 4, 0, pad / 4)
        }
        primary = Button(this).apply { setOnClickListener { onPrimary() } }
        secondary = Button(this).apply {
            setText(R.string.perm_not_now)
            setOnClickListener { finish() }
        }
        listOf(title, body, primary, secondary).forEach(column::addView)
        return ScrollView(this).apply { addView(column) }
    }

    companion object {
        const val EXTRA_FEATURE = "feature"
    }
}
