package ai.pixel.assistant.network

import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

object TransportSecurity {

    fun computeSha256(input: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hashBytes = digest.digest(input.toByteArray(Charsets.UTF_8))
        return hashBytes.joinToString("") { "%02x".format(it) }
    }

    fun signConfirmationToken(
        taskId: String,
        sessionId: String,
        userId: String,
        toolName: String,
        argumentsHash: String,
        secretKey: String
    ): String {
        val payload = "$taskId:$sessionId:$userId:$toolName:$argumentsHash"
        val mac = Mac.getInstance("HmacSHA256")
        val keySpec = SecretKeySpec(secretKey.toByteArray(Charsets.UTF_8), "HmacSHA256")
        mac.init(keySpec)
        val signedBytes = mac.doFinal(payload.toByteArray(Charsets.UTF_8))
        return signedBytes.joinToString("") { "%02x".format(it) }
    }

    fun verifyToken(
        token: String,
        taskId: String,
        sessionId: String,
        userId: String,
        toolName: String,
        argumentsHash: String,
        secretKey: String
    ): Boolean {
        val expected = signConfirmationToken(taskId, sessionId, userId, toolName, argumentsHash, secretKey)
        return MessageDigest.isEqual(token.toByteArray(Charsets.UTF_8), expected.toByteArray(Charsets.UTF_8))
    }
}
