"""OS Control and Capabilities Package."""

from services.os_control.mock_adapter import MockOSAdapter
from services.os_control.windows_adapter import WindowsOSAdapter

__all__ = ["MockOSAdapter", "WindowsOSAdapter"]
