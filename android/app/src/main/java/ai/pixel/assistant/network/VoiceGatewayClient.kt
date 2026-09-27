package ai.pixel.assistant.network

import android.util.Base64
import okhttp3.*
import java.util.concurrent.TimeUnit

interface GatewayEventListener {
    fun onConnected(sessionId: String)
    fun onTranscriptReceived(text: String, isFinal: Boolean)
    fun onAudioResponseChunk(pcmData: ByteArray)
    fun onApprovalRequested(approvalJson: String)
    fun onDisconnected(reason: String)
    fun onError(error: String)
}

class VoiceGatewayClient(
    private val serverUrl: String,
    private val authToken: String,
    private val listener: GatewayEventListener
) {
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .connectTimeout(10, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    var isConnected: Boolean = false
        private set

    fun connect() {
        val request = Request.Builder()
            .url(serverUrl)
            .addHeader("Authorization", "Bearer $authToken")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                isConnected = true
                listener.onConnected("session_active")
            }

            override fun onMessage(ws: WebSocket, text: String) {
                if (text.contains("\"event_type\":\"transcript\"")) {
                    listener.onTranscriptReceived(text, text.contains("\"is_final\":true"))
                } else if (text.contains("\"approval_id\"")) {
                    listener.onApprovalRequested(text)
                }
            }

            override fun onClosing(ws: WebSocket, code: Int, reason: String) {
                isConnected = false
                listener.onDisconnected(reason)
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                listener.onError(t.localizedMessage ?: "WebSocket Connection Failed")
            }
        })
    }

    fun sendAudioChunk(pcmBytes: ByteArray) {
        val b64 = Base64.encodeToString(pcmBytes, Base64.NO_WRAP)
        val payload = "{\"event_type\":\"audio_frame\",\"pcm_base64\":\"$b64\"}"
        webSocket?.send(payload)
    }

    fun sendBargeIn() {
        val payload = "{\"event_type\":\"barge_in\"}"
        webSocket?.send(payload)
    }

    fun disconnect() {
        webSocket?.close(1000, "Client Disconnect")
        isConnected = false
    }
}
