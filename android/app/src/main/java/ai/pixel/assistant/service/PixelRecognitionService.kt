package ai.pixel.assistant.service

import android.content.Intent
import android.speech.RecognitionService

class PixelRecognitionService : RecognitionService() {

    override fun onStartListening(recognizerIntent: Intent?, listener: Callback?) {
        // Recognition callback forwarding to PIXEL Voice Gateway
    }

    override fun onCancel(listener: Callback?) {
        // Cancel speech recognition
    }

    override fun onStopListening(listener: Callback?) {
        // Stop audio capture
    }
}
