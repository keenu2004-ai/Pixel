"""PIXEL — Change Proposal Manager.

Provides persistent SQLite-backed storage for autonomous change proposals,
state transitions (PROPOSED -> ANALYZED -> TESTING -> VERIFIED -> CANARY -> APPROVED -> PROMOTED),
and automatic rollback tracking.
"""

import sqlite3

from packages.contracts.evolution import ChangeProposal, ChangeProposalState, ChangeType


class ChangeProposalManager:
    """Manages change proposal state machine and audit persistence."""

    def __init__(self, db_path: str = "pixel_proposals.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS change_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        originating_agent_id TEXT NOT NULL,
                        swarm_id TEXT NOT NULL,
                        change_type TEXT NOT NULL,
                        state TEXT NOT NULL,
                        title TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        diff_content TEXT,
                        regression_test_code TEXT,
                        expected_outcome TEXT,
                        rollback_plan TEXT,
                        canary_percentage INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
        finally:
            conn.close()

    def create_proposal(self, proposal: ChangeProposal) -> None:
        """Stores a new change proposal."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO change_proposals (
                        proposal_id, originating_agent_id, swarm_id, change_type,
                        state, title, reason, diff_content, regression_test_code,
                        expected_outcome, rollback_plan, canary_percentage,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proposal.proposal_id,
                        proposal.originating_agent_id,
                        proposal.swarm_id,
                        proposal.change_type.value,
                        proposal.state.value,
                        proposal.title,
                        proposal.reason,
                        proposal.diff_content,
                        proposal.regression_test_code,
                        proposal.expected_outcome,
                        proposal.rollback_plan,
                        proposal.canary_percentage,
                        proposal.created_at,
                        proposal.updated_at,
                    ),
                )
        finally:
            conn.close()

    def get_proposal(self, proposal_id: str) -> ChangeProposal | None:
        """Retrieves a proposal by its unique ID."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM change_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_proposal(row)
        finally:
            conn.close()

    def list_proposals(self, state: ChangeProposalState | None = None) -> list[ChangeProposal]:
        """Lists all proposals, optionally filtered by state."""
        conn = self._get_connection()
        try:
            if state:
                rows = conn.execute(
                    "SELECT * FROM change_proposals WHERE state = ? ORDER BY created_at DESC",
                    (state.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM change_proposals ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_proposal(r) for r in rows]
        finally:
            conn.close()

    def update_state(
        self,
        proposal_id: str,
        new_state: ChangeProposalState,
        canary_percentage: int | None = None,
    ) -> bool:
        """Transitions proposal to a new lifecycle state."""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return False

        proposal.state = new_state
        if canary_percentage is not None:
            proposal.canary_percentage = canary_percentage

        self.create_proposal(proposal)
        return True

    def _row_to_proposal(self, row: sqlite3.Row) -> ChangeProposal:
        return ChangeProposal(
            proposal_id=row["proposal_id"],
            originating_agent_id=row["originating_agent_id"],
            swarm_id=row["swarm_id"],
            change_type=ChangeType(row["change_type"]),
            state=ChangeProposalState(row["state"]),
            title=row["title"],
            reason=row["reason"],
            diff_content=row["diff_content"] or "",
            regression_test_code=row["regression_test_code"] or "",
            expected_outcome=row["expected_outcome"] or "",
            rollback_plan=row["rollback_plan"] or "",
            canary_percentage=row["canary_percentage"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def close(self) -> None:
        """Explicitly closes resources if necessary."""
        pass
