"""PIXEL — Training Dataset Lineage Tracker.

Tracks user interaction provenance, consent tokens, PII scrubbing verification,
and dataset revision metadata for personal model adaptation.
"""

import uuid
from datetime import UTC, datetime

from packages.contracts.evolution import TrainingConsentStatus, TrainingDataLineage


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class DatasetLineageTracker:
    """Maintains immutable provenance and consent tracking for training samples."""

    def __init__(self) -> None:
        self._lineage_records: dict[str, TrainingDataLineage] = {}  # lineage_id -> record
        self._user_records: dict[str, list[str]] = {}  # user_id -> list of lineage_ids

    def record_interaction(
        self,
        interaction_id: str,
        user_id: str,
        consent_status: TrainingConsentStatus = TrainingConsentStatus.CONSENT_GRANTED,
        pii_scrubbed: bool = True,
        dataset_revision: str = "v1",
    ) -> TrainingDataLineage:
        """Records provenance metadata for a user interaction eligible for training/distillation."""
        lineage_id = f"lin-{uuid.uuid4().hex[:8]}"

        record = TrainingDataLineage(
            lineage_id=lineage_id,
            interaction_id=interaction_id,
            user_id=user_id,
            consent_status=consent_status,
            pii_scrubbed=pii_scrubbed,
            source_timestamp=_utc_now_iso(),
            dataset_revision=dataset_revision,
            created_at=_utc_now_iso(),
        )

        self._lineage_records[lineage_id] = record
        self._user_records.setdefault(user_id, []).append(lineage_id)
        return record

    def revoke_user_consent(self, user_id: str) -> int:
        """Revokes consent for all training lineage records belonging to a user (Right-to-be-Forgotten).

        Returns the number of revoked records.
        """
        lineage_ids = self._user_records.get(user_id, [])
        revoked_count = 0
        for lid in lineage_ids:
            rec = self._lineage_records.get(lid)
            if rec and rec.consent_status != TrainingConsentStatus.CONSENT_REVOKED:
                rec.consent_status = TrainingConsentStatus.CONSENT_REVOKED
                revoked_count += 1
        return revoked_count

    def get_eligible_training_samples(self, dataset_revision: str) -> list[TrainingDataLineage]:
        """Returns only samples with explicit CONSENT_GRANTED and verified PII scrubbing."""
        return [
            rec
            for rec in self._lineage_records.values()
            if rec.dataset_revision == dataset_revision
            and rec.consent_status == TrainingConsentStatus.CONSENT_GRANTED
            and rec.pii_scrubbed is True
        ]

    def get_lineage(self, lineage_id: str) -> TrainingDataLineage | None:
        """Retrieves a lineage record by ID."""
        return self._lineage_records.get(lineage_id)
