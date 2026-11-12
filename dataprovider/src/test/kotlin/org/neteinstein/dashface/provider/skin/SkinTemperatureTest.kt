package org.neteinstein.dashface.provider.skin

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SkinTemperatureTest {

    @Test
    fun matchesVendorSkinTemperatureSensors() {
        assertTrue(SkinTemperature.isSkinTemperatureSensor("Skin Temperature Sensor", null))
        assertTrue(SkinTemperature.isSkinTemperatureSensor("x", "com.vendor.sensor.skin_temp"))
        assertFalse(SkinTemperature.isSkinTemperatureSensor("Ambient Temperature", "android.sensor.ambient_temperature"))
        assertFalse(SkinTemperature.isSkinTemperatureSensor("Skin contact detector", null))
        assertFalse(SkinTemperature.isSkinTemperatureSensor(null, null))
    }

    @Test
    fun labelsInCelsiusAndFahrenheit() {
        assertEquals("33.6°", SkinTemperature.label(33.6f, fahrenheit = false))
        assertEquals("92.5°", SkinTemperature.label(33.6f, fahrenheit = true))
        assertEquals("30.0°", SkinTemperature.label(29.96f, fahrenheit = false))
    }

    @Test
    fun clampsToThermometerRange() {
        assertEquals(SkinTemperature.MIN_C, SkinTemperature.rangedValue(22f))
        assertEquals(SkinTemperature.MAX_C, SkinTemperature.rangedValue(41f))
        assertEquals(33f, SkinTemperature.rangedValue(33f))
    }

    @Test
    fun rejectsImplausibleReadings() {
        assertFalse(SkinTemperature.isPlausible(Float.NaN))
        assertFalse(SkinTemperature.isPlausible(0f))
        assertFalse(SkinTemperature.isPlausible(92f)) // Fahrenheit or garbage
        assertTrue(SkinTemperature.isPlausible(33f))
    }

    @Test
    fun readingsExpireAfterTwoHours() {
        val hour = 3_600_000L
        assertTrue(SkinTemperature.isFresh(10 * hour, 11 * hour))
        assertFalse(SkinTemperature.isFresh(10 * hour, 13 * hour))
        assertFalse(SkinTemperature.isFresh(0L, hour))
    }
}
