package ai.pixel.assistant.hotword

import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class HotwordManagerTest {

    private lateinit var hotwordManager: HotwordManager

    @Before
    fun setUp() {
        hotwordManager = HotwordManager()
    }

    @Test
    fun testDefaultEnrollment() {
        assertTrue(hotwordManager.isHotwordEnrolled("hey pixel"))
        assertTrue(hotwordManager.isHotwordEnrolled("oye pixel"))
        assertFalse(hotwordManager.isHotwordEnrolled("alexa"))
    }

    @Test
    fun testEnrollNewPhrase() {
        assertTrue(hotwordManager.enrollPhrase("namaste pixel"))
        assertTrue(hotwordManager.isHotwordEnrolled("namaste pixel"))
    }

    @Test
    fun testShortPhraseRejected() {
        assertFalse(hotwordManager.enrollPhrase("hi"))
    }

    @Test
    fun testRemovePhrase() {
        assertTrue(hotwordManager.removePhrase("oye pixel"))
        assertFalse(hotwordManager.isHotwordEnrolled("oye pixel"))
    }

    @Test
    fun testDetectorActivation() {
        assertTrue(hotwordManager.activateDetector())
        assertTrue(hotwordManager.isListening())
        hotwordManager.deactivateDetector()
        assertFalse(hotwordManager.isListening())
    }
}
