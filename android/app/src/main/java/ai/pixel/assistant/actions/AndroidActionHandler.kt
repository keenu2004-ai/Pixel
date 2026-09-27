package ai.pixel.assistant.actions

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.provider.AlarmClock
import android.provider.CalendarContract
import android.telephony.SmsManager
import java.util.TimeZone

/**
 * Native Android Action Handler for PIXEL Assistant.
 * Dispatches platform intents and calls Android system services for
 * calls, messages, alarms, timers, media control, calendar events, and app launching.
 */
class AndroidActionHandler(private val context: Context) {

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager

    /**
     * Initiates a phone call or opens the dialer.
     */
    fun initiateCall(phoneNumber: String, useDirectCall: Boolean = false): Boolean {
        return try {
            val action = if (useDirectCall) Intent.ACTION_CALL else Intent.ACTION_DIAL
            val intent = Intent(action, Uri.parse("tel:$phoneNumber")).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Sends an SMS message to the specified recipient.
     */
    fun sendSms(recipientPhone: String, messageBody: String): Boolean {
        return try {
            val smsManager = context.getSystemService(SmsManager::class.java) ?: SmsManager.getDefault()
            smsManager.sendTextMessage(recipientPhone, null, messageBody, null, null)
            true
        } catch (e: Exception) {
            // Fallback to SMS Intent
            try {
                val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:$recipientPhone")).apply {
                    putExtra("sms_body", messageBody)
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
                true
            } catch (ex: Exception) {
                false
            }
        }
    }

    /**
     * Sets an Android alarm.
     */
    fun setAlarm(hour: Int, minutes: Int, message: String, skipUi: Boolean = true): Boolean {
        return try {
            val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
                putExtra(AlarmClock.EXTRA_HOUR, hour)
                putExtra(AlarmClock.EXTRA_MINUTES, minutes)
                putExtra(AlarmClock.EXTRA_MESSAGE, message)
                putExtra(AlarmClock.EXTRA_SKIP_UI, skipUi)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Sets a countdown timer.
     */
    fun setTimer(durationSeconds: Int, label: String, skipUi: Boolean = true): Boolean {
        return try {
            val intent = Intent(AlarmClock.ACTION_SET_TIMER).apply {
                putExtra(AlarmClock.EXTRA_LENGTH, durationSeconds)
                putExtra(AlarmClock.EXTRA_MESSAGE, label)
                putExtra(AlarmClock.EXTRA_SKIP_UI, skipUi)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Adjusts or queries media volume.
     */
    fun adjustVolume(direction: Int): Boolean {
        return try {
            audioManager?.adjustStreamVolume(
                AudioManager.STREAM_MUSIC,
                direction,
                AudioManager.FLAG_SHOW_UI
            )
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Creates a Calendar event via CalendarProvider Intent.
     */
    fun insertCalendarEvent(
        title: String,
        startTimeMillis: Long,
        endTimeMillis: Long,
        location: String = ""
    ): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_INSERT).apply {
                data = CalendarContract.Events.CONTENT_URI
                putExtra(CalendarContract.Events.TITLE, title)
                putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, startTimeMillis)
                putExtra(CalendarContract.EXTRA_EVENT_END_TIME, endTimeMillis)
                putExtra(CalendarContract.Events.EVENT_LOCATION, location)
                putExtra(CalendarContract.Events.EVENT_TIMEZONE, TimeZone.getDefault().id)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Launches an installed application by package name.
     */
    fun launchApp(packageName: String): Boolean {
        return try {
            val launchIntent = context.packageManager.getLaunchIntentForPackage(packageName)
            if (launchIntent != null) {
                launchIntent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                context.startActivity(launchIntent)
                true
            } else {
                false
            }
        } catch (e: Exception) {
            false
        }
    }
}
