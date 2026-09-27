package ai.pixel.assistant.hotword

data class HotwordModelConfig(
    val modelName: String = "hey_pixel_v1",
    val activationThreshold: Float = 0.75f,
    val phrase: String = "hey pixel",
    val isEnabled: Boolean = true
)

interface HotwordDetector {
    fun startListening(): Boolean
    fun stopListening()
    fun isListening(): Boolean
}

class HotwordManager(
    var config: HotwordModelConfig = HotwordModelConfig()
) {
    private val enrolledPhrases: MutableSet<String> = mutableSetOf("hey pixel", "oye pixel")
    private var isDetectorActive = false

    fun isHotwordEnrolled(phrase: String): Boolean {
        return enrolledPhrases.contains(phrase.lowercase().trim())
    }

    fun enrollPhrase(phrase: String): Boolean {
        val clean = phrase.lowercase().trim()
        if (clean.length < 3) return false
        return enrolledPhrases.add(clean)
    }

    fun removePhrase(phrase: String): Boolean {
        return enrolledPhrases.remove(phrase.lowercase().trim())
    }

    fun getEnrolledPhrases(): Set<String> {
        return enrolledPhrases.toSet()
    }

    fun activateDetector(): Boolean {
        if (!config.isEnabled) return false
        isDetectorActive = true
        return true
    }

    fun deactivateDetector() {
        isDetectorActive = false
    }

    fun isListening(): Boolean = isDetectorActive
}
