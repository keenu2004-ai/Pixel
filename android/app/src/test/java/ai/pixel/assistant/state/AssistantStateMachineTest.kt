package ai.pixel.assistant.state

import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class AssistantStateMachineTest {

    private lateinit var stateMachine: AssistantStateMachine

    @Before
    fun setUp() {
        stateMachine = AssistantStateMachine()
    }

    @Test
    fun testInitialStateIsUninitialized() {
        assertEquals(AssistantState.UNINITIALIZED, stateMachine.currentState)
    }

    @Test
    fun testValidLifecycleFlow() {
        assertTrue(stateMachine.transitionTo(AssistantState.INITIALIZING))
        assertTrue(stateMachine.transitionTo(AssistantState.READY))
        assertTrue(stateMachine.transitionTo(AssistantState.LISTENING))
        assertTrue(stateMachine.transitionTo(AssistantState.WAKE_DETECTED))
        assertTrue(stateMachine.transitionTo(AssistantState.PROCESSING))
        assertTrue(stateMachine.transitionTo(AssistantState.SPEAKING))
        assertTrue(stateMachine.transitionTo(AssistantState.READY))
    }

    @Test
    fun testBargeInInterruptionFlow() {
        stateMachine.transitionTo(AssistantState.INITIALIZING)
        stateMachine.transitionTo(AssistantState.READY)
        stateMachine.transitionTo(AssistantState.LISTENING)
        stateMachine.transitionTo(AssistantState.WAKE_DETECTED)
        stateMachine.transitionTo(AssistantState.PROCESSING)
        stateMachine.transitionTo(AssistantState.SPEAKING)

        // Interrupted by user
        assertTrue(stateMachine.transitionTo(AssistantState.INTERRUPTED))
        // Returns to listening
        assertTrue(stateMachine.transitionTo(AssistantState.LISTENING))
        assertEquals(AssistantState.LISTENING, stateMachine.currentState)
    }

    @Test
    fun testInvalidTransitionRejected() {
        // Cannot jump directly from UNINITIALIZED to SPEAKING
        assertFalse(stateMachine.transitionTo(AssistantState.SPEAKING))
        assertEquals(AssistantState.UNINITIALIZED, stateMachine.currentState)
    }
}
