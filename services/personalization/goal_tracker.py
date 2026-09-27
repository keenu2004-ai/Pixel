"""PIXEL — Goal & Task Continuity Tracker.

Maintains overarching long-term objectives across multi-day sessions, supporting
conversational references like "Continue the project we were working on" without starting from zero.
"""

import logging
from datetime import UTC, datetime

from packages.contracts.personalization import GoalStatus, PersonalGoal
from services.personalization.user_model_store import UserModelStore

logger = logging.getLogger(__name__)


class GoalTracker:
    """Tracks active user goals, milestones, and task continuity."""

    def __init__(self, user_model_store: UserModelStore) -> None:
        self.store = user_model_store

    async def create_or_update_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 1,
        active_project_path: str | None = None,
        tags: list[str] | None = None,
        user_id: str = "default_user",
    ) -> PersonalGoal:
        """Registers or updates a personal goal."""
        user_model = await self.store.get_user_model(user_id=user_id)
        # Search for existing goal by title match
        existing = next(
            (g for g in user_model.active_goals if g.title.lower() == title.lower()),
            None,
        )

        now = datetime.now(UTC)
        if existing:
            existing.description = description or existing.description
            existing.priority = priority
            existing.active_project_path = active_project_path or existing.active_project_path
            existing.last_worked_on = now
            if tags:
                existing.tags = list(set(existing.tags + tags))
            await self.store.save_goal(existing)
            logger.info("Updated existing goal: '%s' for user %s", existing.title, user_id)
            return existing

        new_goal = PersonalGoal(
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            active_project_path=active_project_path,
            tags=tags or [],
            last_worked_on=now,
            created_at=now,
        )
        await self.store.save_goal(new_goal)
        logger.info("Created new goal: '%s' for user %s", new_goal.title, user_id)
        return new_goal

    async def get_active_goal(self, user_id: str = "default_user") -> PersonalGoal | None:
        """Retrieves the most recently worked on active goal for conversational continuity."""
        user_model = await self.store.get_user_model(user_id=user_id)
        active_goals = [g for g in user_model.active_goals if g.status == GoalStatus.ACTIVE]
        if not active_goals:
            return None
        # Sort by last_worked_on descending, then priority ascending
        active_goals.sort(key=lambda g: (g.last_worked_on, -g.priority), reverse=True)
        return active_goals[0]

    async def match_goal_by_query(
        self, query: str, user_id: str = "default_user"
    ) -> PersonalGoal | None:
        """Finds active goal matching query keywords (e.g. 'hrms', 'pixel', 'backend')."""
        user_model = await self.store.get_user_model(user_id=user_id)
        q_lower = query.lower()
        active = [g for g in user_model.active_goals if g.status == GoalStatus.ACTIVE]

        # 1. Exact title substring or keyword match
        for g in active:
            t_words = [w for w in g.title.lower().split() if len(w) >= 3]
            if (
                g.title.lower() in q_lower
                or any(w in q_lower for w in t_words)
                or any(tag.lower() in q_lower for tag in g.tags)
            ):
                g.last_worked_on = datetime.now(UTC)
                await self.store.save_goal(g)
                return g

        # 2. Project path match
        for g in active:
            if g.active_project_path and (
                g.active_project_path.lower() in q_lower
                or any(p in q_lower for p in g.active_project_path.lower().split("/"))
            ):
                g.last_worked_on = datetime.now(UTC)
                await self.store.save_goal(g)
                return g

        # 3. If query implies continuation ("continue", "our project", "work on that"), return recent active
        if any(
            w in q_lower
            for w in ["continue", "resume", "our project", "the project", "that project"]
        ):
            return await self.get_active_goal(user_id=user_id)

        return None

    async def update_goal_progress(
        self,
        goal_id: str,
        milestone_title: str,
        completed: bool = True,
        user_id: str = "default_user",
    ) -> PersonalGoal:
        """Adds or marks a milestone on an active goal."""
        user_model = await self.store.get_user_model(user_id=user_id)
        goal = next((g for g in user_model.active_goals if g.goal_id == goal_id), None)
        if not goal:
            raise ValueError(f"Goal '{goal_id}' not found.")

        goal.last_worked_on = datetime.now(UTC)
        goal.milestones.append(
            {
                "title": milestone_title,
                "completed": completed,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        await self.store.save_goal(goal)
        return goal
