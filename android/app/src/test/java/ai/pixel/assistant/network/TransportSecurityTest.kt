package ai.pixel.assistant.network

import org.junit.Assert.*
import org.junit.Test

class TransportSecurityTest {

    private val testSecret = "pixel_secret_test_key_123"

    @Test
    fun testSha256Determinism() {
        val hash1 = TransportSecurity.computeSha256("hello pixel")
        val hash2 = TransportSecurity.computeSha256("hello pixel")
        assertEquals(hash1, hash2)
        assertEquals(64, hash1.length)
    }

    @Test
    fun testSignAndVerifyToken() {
        val taskId = "task_001"
        val sessionId = "session_001"
        val userId = "user_001"
        val toolName = "execute_action"
        val argsHash = TransportSecurity.computeSha256("{\"key\":\"value\"}")

        val token = TransportSecurity.signConfirmationToken(
            taskId, sessionId, userId, toolName, argsHash, testSecret
        )

        assertTrue(
            TransportSecurity.verifyToken(
                token, taskId, sessionId, userId, toolName, argsHash, testSecret
            )
        )
    }

    @Test
    fun testTamperedTokenRejected() {
        val taskId = "task_001"
        val sessionId = "session_001"
        val userId = "user_001"
        val toolName = "execute_action"
        val argsHash = TransportSecurity.computeSha256("{\"key\":\"value\"}")

        val token = TransportSecurity.signConfirmationToken(
            taskId, sessionId, userId, toolName, argsHash, testSecret
        )

        // Tampered taskId
        assertFalse(
            TransportSecurity.verifyToken(
                token, "task_ATTACKER", sessionId, userId, toolName, argsHash, testSecret
            )
        )

        // Tampered arguments hash
        assertFalse(
            TransportSecurity.verifyToken(
                token, taskId, sessionId, userId, toolName, "tampered_args_hash", testSecret
            )
        )
    }
}
