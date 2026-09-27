package ai.pixel.assistant.service

import android.service.voice.VoiceInteractionService
import ai.pixel.assistant.hotword.HotwordManager
import ai.pixel.assistant.state.AssistantState
import ai.pixel.assistant.state.AssistantStateMachine

class PixelVoiceInteractionService : VoiceInteractionService() {

    private val stateMachine = AssistantStateMachine()
    private val hotwordManager = HotwordManager()

    override fun onReady() {
        super.onReady()
        stateMachine.transitionTo(AssistantState.INITIALIZING)
        hotwordManager.activateDetector()
        stateMachine.transitionTo(AssistantState.READY)
    }

    override fun onShutdown() {
        hotwordManager.deactivateDetector()
        stateMachine.transitionTo(AssistantState.STOPPED)
        super.onShutdown()
    }

    fun getAssistantState(): AssistantState = stateMachine.currentState
}
