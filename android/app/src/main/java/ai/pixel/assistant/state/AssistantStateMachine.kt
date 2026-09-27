package ai.pixel.assistant.state

enum class AssistantState {
    UNINITIALIZED,
    INITIALIZING,
    PERMISSION_REQUIRED,
    READY,
    LISTENING,
    WAKE_DETECTED,
    PROCESSING,
    SPEAKING,
    INTERRUPTED,
    AWAITING_APPROVAL,
    DISCONNECTED,
    RECONNECTING,
    ERROR,
    STOPPED
}

class AssistantStateMachine(initialState: AssistantState = AssistantState.UNINITIALIZED) {

    var currentState: AssistantState = initialState
        private set

    private val validTransitions: Map<AssistantState, Set<AssistantState>> = mapOf(
        AssistantState.UNINITIALIZED to setOf(AssistantState.INITIALIZING, AssistantState.ERROR),
        AssistantState.INITIALIZING to setOf(AssistantState.PERMISSION_REQUIRED, AssistantState.READY, AssistantState.ERROR),
        AssistantState.PERMISSION_REQUIRED to setOf(AssistantState.READY, AssistantState.STOPPED),
        AssistantState.READY to setOf(AssistantState.LISTENING, AssistantState.DISCONNECTED, AssistantState.STOPPED),
        AssistantState.LISTENING to setOf(AssistantState.WAKE_DETECTED, AssistantState.READY, AssistantState.DISCONNECTED, AssistantState.STOPPED),
        AssistantState.WAKE_DETECTED to setOf(AssistantState.PROCESSING, AssistantState.LISTENING, AssistantState.ERROR),
        AssistantState.PROCESSING to setOf(AssistantState.SPEAKING, AssistantState.AWAITING_APPROVAL, AssistantState.READY, AssistantState.ERROR),
        AssistantState.SPEAKING to setOf(AssistantState.INTERRUPTED, AssistantState.READY, AssistantState.ERROR),
        AssistantState.INTERRUPTED to setOf(AssistantState.LISTENING, AssistantState.READY),
        AssistantState.AWAITING_APPROVAL to setOf(AssistantState.PROCESSING, AssistantState.READY, AssistantState.ERROR),
        AssistantState.DISCONNECTED to setOf(AssistantState.RECONNECTING, AssistantState.READY, AssistantState.STOPPED),
        AssistantState.RECONNECTING to setOf(AssistantState.READY, AssistantState.DISCONNECTED, AssistantState.ERROR),
        AssistantState.ERROR to setOf(AssistantState.INITIALIZING, AssistantState.STOPPED),
        AssistantState.STOPPED to setOf(AssistantState.INITIALIZING, AssistantState.UNINITIALIZED)
    )

    fun transitionTo(newState: AssistantState): Boolean {
        val allowed = validTransitions[currentState] ?: emptySet()
        return if (newState in allowed) {
            currentState = newState
            true
        } else {
            false
        }
    }
}
