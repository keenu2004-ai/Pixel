package ai.pixel.assistant.service

import android.content.Context
import android.os.Bundle
import android.service.voice.VoiceInteractionSession
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import ai.pixel.assistant.state.AssistantState
import ai.pixel.assistant.state.AssistantStateMachine

class PixelVoiceInteractionSession(context: Context) : VoiceInteractionSession(context) {

    private val stateMachine = AssistantStateMachine(AssistantState.READY)
    private var overlayTextView: TextView? = null

    override fun onCreate() {
        super.onCreate()
        stateMachine.transitionTo(AssistantState.LISTENING)
    }

    override fun onCreateContentView(): View {
        val root = FrameLayout(context)
        overlayTextView = TextView(context).apply {
            text = "PIXEL Assistant Listening..."
            textSize = 18f
        }
        root.addView(overlayTextView)
        return root
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        stateMachine.transitionTo(AssistantState.PROCESSING)
        overlayTextView?.text = "PIXEL Assistant Active"
    }

    override fun onHide() {
        stateMachine.transitionTo(AssistantState.READY)
        super.onHide()
    }

    fun getSessionState(): AssistantState = stateMachine.currentState
}
