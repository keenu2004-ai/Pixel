# ADR 0006: Android Native Assistant Architecture (VoiceInteractionService & RoleManager)

## Status
Accepted (Source of Truth)

## Context
PIXEL aims to provide a system-level personal assistant experience on Android devices.
Modern Android versions (Android 12 to Android 15+) enforce strict security, privacy, and background execution boundaries:
1. **VoiceInteractionService**: Standard system entrypoint for Android assistants. Declared with `android.permission.BIND_VOICE_INTERACTION` and configured with `android.voice_interaction` XML metadata.
2. **RoleManager**: Starting in Android 10 (API 29) and strictly enforced in Android 12+, default assistant selection must be requested via `RoleManager.createRequestRoleIntent(RoleManager.ROLE_ASSISTANT)`. Apps cannot silently set themselves as default assistants.
3. **Microphone Permissions & Foreground Services**: Android 14+ requires `android:foregroundServiceType="microphone"` in `<service>` declarations when capturing audio from a background/foreground service. Background recording without a visible foreground service or an active `VoiceInteractionSession` is rejected by the Android OS.
4. **Screen-Off Operation**: Requires a dedicated foreground service with `FOREGROUND_SERVICE_TYPE_MICROPHONE` and an active ongoing notification (`POST_NOTIFICATIONS` permission in Android 13+).
5. **No Local Intelligence Duplication**: The Android client acts as a native runtime client (audio capture, wake detection, session UI overlay, audio playback, biometric approval) and communicates with the PIXEL Voice Gateway over authenticated WebSocket/TLS.

## Decision
1. Implement `PixelVoiceInteractionService` and `PixelVoiceInteractionSessionService` matching standard Android OS assistant contracts.
2. Integrate with `RoleManager` for explicit, user-granted assistant role activation.
3. Implement `AssistantForegroundService` with `microphone` foreground service type and ongoing notification for background/screen-off wake word listening.
4. Provide a provider-agnostic `HotwordManager` interface for wake-word engines (OpenWakeWord / Porcupine / platform detection).
5. Implement `VoiceGatewayClient` with TLS, token-based session authentication, binary PCM streaming, and immediate cancellation on barge-in.
6. Enforce L6 security policy: Mobile UI displays `ApprovalCard` for high-impact actions, requiring user confirmation before returning HMAC-signed authorization.
7. Provide a deterministic mock mobile runtime (`MockAndroidDeviceRuntime`) in Python to allow complete CI test coverage without requiring physical Android hardware or emulators.

## Consequences
- **Positive**: Native Android integration with lock-screen, hardware key/gesture invocation, and default assistant role eligibility; robust security adhering to Android 12-15+ platform rules; zero token bloat by streaming to backend.
- **Trade-offs**: Background always-on listening requires a persistent notification channel per Android OS rules.
