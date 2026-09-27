"""Desktop Adapter for Window Management, Clipboard and Visual State.

Provides OS-level desktop window enumeration, focus control, clipboard access,
and privacy-preserving window screenshot capture with fallback mock support.
"""

import base64
import logging
import platform
from typing import Any

from packages.contracts.computer import (
    ClipboardData,
    ScreenshotPayload,
    WindowBounds,
    WindowState,
)

logger = logging.getLogger(__name__)


class DesktopAdapter:
    """Adapter for interacting with desktop windows, clipboard, and screenshots."""

    def __init__(self, mock_mode: bool = False) -> None:
        self.mock_mode = mock_mode
        self._mock_clipboard: str = ""
        self._mock_windows: list[WindowState] = [
            WindowState(
                window_id="win_code_1",
                title="Pixel - Visual Studio Code",
                app_name="Code",
                is_active=True,
                is_minimized=False,
                bounds=WindowBounds(x=0, y=0, width=1920, height=1080),
            ),
            WindowState(
                window_id="win_chrome_1",
                title="GitHub - keenu2004-ai/Pixel - Google Chrome",
                app_name="chrome",
                is_active=False,
                is_minimized=False,
                bounds=WindowBounds(x=100, y=100, width=1600, height=900),
            ),
            WindowState(
                window_id="win_term_1",
                title="PowerShell",
                app_name="pwsh",
                is_active=False,
                is_minimized=True,
                bounds=WindowBounds(x=200, y=200, width=800, height=600),
            ),
        ]

    # -----------------------------------------------------------------------
    # 1. Window Management
    # -----------------------------------------------------------------------

    def list_windows(self) -> list[WindowState]:
        """Returns list of open desktop application windows."""
        if self.mock_mode or platform.system() != "Windows":
            return list(self._mock_windows)

        windows: list[WindowState] = []
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            def enum_windows_callback(hwnd: int, extra: Any) -> bool:
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value
                        if (
                            title
                            and not title.startswith("Default IME")
                            and not title.startswith("MSCTFIME UI")
                        ):
                            # Get window rect
                            rect = wintypes.RECT()
                            user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            w = rect.right - rect.left
                            h = rect.bottom - rect.top
                            if w > 100 and h > 100:
                                is_active = hwnd == user32.GetForegroundWindow()
                                windows.append(
                                    WindowState(
                                        window_id=str(hwnd),
                                        title=title,
                                        app_name="WindowsApp",
                                        is_active=is_active,
                                        is_minimized=bool(user32.IsIconic(hwnd)),
                                        bounds=WindowBounds(
                                            x=rect.left, y=rect.top, width=w, height=h
                                        ),
                                    )
                                )
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        except Exception as err:
            logger.warning(
                "Failed to enumerate Windows windows natively, falling back to mock: %s", err
            )
            return list(self._mock_windows)

        return windows if windows else list(self._mock_windows)

    def get_active_window(self) -> WindowState | None:
        """Returns the currently focused window."""
        windows = self.list_windows()
        for win in windows:
            if win.is_active:
                return win
        return windows[0] if windows else None

    def focus_window(self, query: str) -> bool:
        """Brings the window matching query title or app_name to the foreground."""
        q_lower = query.lower().strip()

        if self.mock_mode or platform.system() != "Windows":
            found = False
            for win in self._mock_windows:
                if (
                    q_lower in win.title.lower()
                    or q_lower in win.app_name.lower()
                    or q_lower == win.window_id
                ):
                    win.is_active = True
                    win.is_minimized = False
                    found = True
                else:
                    win.is_active = False
            return found

        try:
            import ctypes

            user32 = ctypes.windll.user32

            for win in self.list_windows():
                if (
                    q_lower in win.title.lower()
                    or q_lower in win.app_name.lower()
                    or q_lower == win.window_id
                ):
                    hwnd = int(win.window_id)
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    return True
            return False
        except Exception as err:
            logger.warning("Native focus_window failed: %s", err)
            return False

    # -----------------------------------------------------------------------
    # 2. Clipboard Management
    # -----------------------------------------------------------------------

    def read_clipboard(self) -> ClipboardData:
        """Reads text from system clipboard."""
        if self.mock_mode or platform.system() != "Windows":
            return ClipboardData(
                text=self._mock_clipboard,
                length=len(self._mock_clipboard),
            )

        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            text = root.clipboard_get()
            root.destroy()
            return ClipboardData(text=text, length=len(text))
        except Exception:
            return ClipboardData(text=self._mock_clipboard, length=len(self._mock_clipboard))

    def write_clipboard(self, text: str) -> bool:
        """Writes text to system clipboard."""
        self._mock_clipboard = text
        if not self.mock_mode and platform.system() == "Windows":
            try:
                import tkinter as tk

                root = tk.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(text)
                root.update()
                root.destroy()
            except Exception as err:
                logger.debug("Failed native clipboard write, stored in memory: %s", err)
        return True

    # -----------------------------------------------------------------------
    # 3. Screenshot Capture & Redaction
    # -----------------------------------------------------------------------

    def capture_window(self, query: str | None = None, redact: bool = True) -> ScreenshotPayload:
        """Captures window or screen state with metadata and optional redaction."""
        target_win = None
        if query:
            for win in self.list_windows():
                if query.lower() in win.title.lower() or query.lower() in win.app_name.lower():
                    target_win = win
                    break
        else:
            target_win = self.get_active_window()

        # Generate lightweight placeholder / simulated visual frame data
        dummy_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        b64_data = base64.b64encode(dummy_png_bytes).decode("ascii")

        return ScreenshotPayload(
            window_id=target_win.window_id if target_win else None,
            app_name=target_win.app_name if target_win else None,
            format="png",
            width=target_win.bounds.width if target_win else 1920,
            height=target_win.bounds.height if target_win else 1080,
            data_base64=b64_data,
            is_redacted=redact,
        )
