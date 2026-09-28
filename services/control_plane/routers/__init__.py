"""Control Plane API Routers."""

from services.control_plane.routers.audit_router import router as audit_router
from services.control_plane.routers.auth_router import router as auth_router
from services.control_plane.routers.backups_router import router as backups_router
from services.control_plane.routers.connectors_router import (
    router as connectors_router,
)
from services.control_plane.routers.conversations_router import (
    router as conversations_router,
)
from services.control_plane.routers.devices_router import router as devices_router
from services.control_plane.routers.diagnostics_router import (
    router as diagnostics_router,
)
from services.control_plane.routers.evolution_models_router import (
    router as evolution_models_router,
)
from services.control_plane.routers.fleet_router import router as fleet_router
from services.control_plane.routers.killswitches_router import (
    router as killswitches_router,
)
from services.control_plane.routers.marketplace_router import (
    router as marketplace_router,
)
from services.control_plane.routers.memory_router import router as memory_router
from services.control_plane.routers.multimodal_router import (
    router as multimodal_router,
)
from services.control_plane.routers.overview_router import router as overview_router
from services.control_plane.routers.personalization_router import (
    router as personalization_router,
)
from services.control_plane.routers.plugins_router import router as plugins_router
from services.control_plane.routers.proposals_router import (
    router as proposals_router,
)
from services.control_plane.routers.scheduler_router import (
    router as scheduler_router,
)
from services.control_plane.routers.swarms_router import router as swarms_router
from services.control_plane.routers.tasks_router import router as tasks_router
from services.control_plane.routers.ws_router import router as ws_router

__all__ = [
    "auth_router",
    "overview_router",
    "conversations_router",
    "tasks_router",
    "scheduler_router",
    "memory_router",
    "personalization_router",
    "multimodal_router",
    "devices_router",
    "audit_router",
    "ws_router",
    "plugins_router",
    "marketplace_router",
    "backups_router",
    "connectors_router",
    "swarms_router",
    "fleet_router",
    "diagnostics_router",
    "proposals_router",
    "evolution_models_router",
    "killswitches_router",
]
