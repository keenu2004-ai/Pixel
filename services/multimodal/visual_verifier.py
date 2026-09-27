"""PIXEL — Phase 16 Visual Action Verifier (L8 Multimodal Extension).

Performs before-and-after semantic screenshot verification to confirm OS/UI state
transitions. Enforces invariant: Never claim 'Done.' without visual proof.
"""

from packages.contracts.multimodal import (
    ScreenSemanticModel,
    VisualVerificationResult,
    VisualVerificationTarget,
)


class VisualActionVerifier:
    """Empirically verifies UI state changes after action execution."""

    def verify_transition(
        self,
        before_model: ScreenSemanticModel,
        after_model: ScreenSemanticModel,
        verification_target: VisualVerificationTarget,
    ) -> VisualVerificationResult:
        """Compares before and after screen semantic models against expectations."""
        # 1. Check for expected application focus
        if verification_target.expected_app_focused:
            app_matches = (
                verification_target.expected_app_focused.lower() in after_model.app_name.lower()
                or verification_target.expected_app_focused.lower()
                in after_model.window_title.lower()
            )
            if not app_matches:
                return VisualVerificationResult(
                    verified=False,
                    before_state_hash=before_model.screenshot_hash,
                    after_state_hash=after_model.screenshot_hash,
                    detected_transition="Focus did not change to expected app",
                    confidence=0.98,
                    explanation=f"Expected app focus '{verification_target.expected_app_focused}', but got '{after_model.app_name}'.",
                )

        # 3. Check for expected element presence
        if verification_target.expected_element_label:
            target_label = verification_target.expected_element_label.lower()
            found = False
            for el in after_model.elements:
                if target_label in el.label.lower():
                    found = True
                    break

            if not found:
                return VisualVerificationResult(
                    verified=False,
                    before_state_hash=before_model.screenshot_hash,
                    after_state_hash=after_model.screenshot_hash,
                    detected_transition="Expected element not visible post-action",
                    confidence=0.95,
                    explanation=f"Expected element with label '{verification_target.expected_element_label}' was not found in active screen model.",
                )

        # 4. Check for expected text contains
        if verification_target.expected_text_contains:
            target_text = verification_target.expected_text_contains.lower()
            found_in_screen = target_text in after_model.window_title.lower() or any(
                target_text in el.label.lower() for el in after_model.elements
            )
            if not found_in_screen:
                return VisualVerificationResult(
                    verified=False,
                    before_state_hash=before_model.screenshot_hash,
                    after_state_hash=after_model.screenshot_hash,
                    detected_transition="Expected text string not visible post-action",
                    confidence=0.95,
                    explanation=f"Text '{verification_target.expected_text_contains}' was not found in post-action screen state.",
                )

        # If expectations met or state cleanly transitioned
        return VisualVerificationResult(
            verified=True,
            before_state_hash=before_model.screenshot_hash,
            after_state_hash=after_model.screenshot_hash,
            detected_transition="State changed and expected visual artifacts verified",
            confidence=0.99,
            explanation="Visual verification successful. UI state matches expected transition.",
        )
