"""Authorized Voice Enrollment and Speaker Profile Registry.

Enforces explicit user consent tokens, manages verified speaker identity
profiles, and guarantees zero retention of unneeded raw biometric audio data.
"""

import threading
from datetime import UTC, datetime
from typing import Any

from packages.contracts.models import (
    SpeakerEnrollmentRequest,
    SpeakerProfile,
    SpeakerVerificationResult,
)
from services.voice_gateway.voice_clone.speaker_encoder import ECAPASpeakerEncoder


class VoiceEnrollmentManager:
    """Canonical registry and enrollment authority for authorized voice profiles."""

    def __init__(self, speaker_encoder: ECAPASpeakerEncoder | None = None) -> None:
        self.encoder = speaker_encoder or ECAPASpeakerEncoder()
        self._profiles_by_id: dict[str, SpeakerProfile] = {}
        self._profiles_by_user: dict[str, list[str]] = {}
        self._revocation_log: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    def enroll_voice(self, request: SpeakerEnrollmentRequest) -> SpeakerProfile:
        """Enroll a new voice profile with validated user consent and sample quality checks."""
        with self._lock:
            profile = self.encoder.enroll_speaker(request)

            self._profiles_by_id[profile.speaker_id] = profile
            if profile.user_id not in self._profiles_by_user:
                self._profiles_by_user[profile.user_id] = []
            self._profiles_by_user[profile.user_id].append(profile.speaker_id)

            return profile

    def get_profile(self, speaker_id: str) -> SpeakerProfile | None:
        """Retrieve enrolled speaker profile by ID."""
        with self._lock:
            return self._profiles_by_id.get(speaker_id)

    def list_user_profiles(self, user_id: str) -> list[SpeakerProfile]:
        """List all active enrolled speaker profiles for a user."""
        with self._lock:
            profile_ids = self._profiles_by_user.get(user_id, [])
            return [self._profiles_by_id[pid] for pid in profile_ids if pid in self._profiles_by_id]

    def verify_speaker(
        self,
        audio_sample: bytes,
        speaker_id: str,
        threshold: float = 0.75,
        sample_rate: int = 16000,
    ) -> SpeakerVerificationResult:
        """Verify if an incoming audio frame matches an enrolled speaker profile."""
        with self._lock:
            profile = self.get_profile(speaker_id)
            if not profile:
                return SpeakerVerificationResult(
                    is_match=False,
                    similarity_score=-1.0,
                    threshold=threshold,
                    speaker_id=speaker_id,
                    confidence=0.0,
                )

            return self.encoder.verify_speaker(
                sample=audio_sample,
                profile=profile,
                threshold=threshold,
                sample_rate=sample_rate,
            )

    def delete_profile(
        self, speaker_id: str, user_id: str, reason: str = "User requested deletion"
    ) -> bool:
        """Permanently delete and purge an enrolled voice profile and embedding vector."""
        with self._lock:
            profile = self._profiles_by_id.get(speaker_id)
            if not profile:
                return False

            if profile.user_id != user_id:
                raise PermissionError("Cannot delete a voice profile belonging to another user.")

            del self._profiles_by_id[speaker_id]
            if user_id in self._profiles_by_user:
                self._profiles_by_user[user_id] = [
                    pid for pid in self._profiles_by_user[user_id] if pid != speaker_id
                ]

            self._revocation_log.append(
                {
                    "speaker_id": speaker_id,
                    "user_id": user_id,
                    "reason": reason,
                    "purged_at": datetime.now(UTC).isoformat(),
                }
            )
            return True

    def reset_user_voices(self, user_id: str) -> int:
        """Purge all voice profiles for a user."""
        with self._lock:
            user_pids = list(self._profiles_by_user.get(user_id, []))
            count = 0
            for pid in user_pids:
                if self.delete_profile(pid, user_id, reason="Full user voice reset"):
                    count += 1
            return count
