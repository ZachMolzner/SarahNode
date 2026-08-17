from __future__ import annotations

import ctypes
import platform


def enable_per_monitor_dpi_awareness() -> bool:
    """Best-effort process DPI awareness for screenshot/pointer coordinate parity.

    Windows may otherwise expose monitor/window coordinates in logical pixels while
    ImageGrab uses physical pixels, which can offset visual click targets on scaled
    displays. Calling this before screen capture keeps both coordinate systems aligned.
    The call is intentionally best-effort because Windows returns access-denied when
    awareness was already established by the host process.
    """
    if platform.system() != "Windows":
        return False

    try:
        shcore = ctypes.windll.shcore
        # PROCESS_PER_MONITOR_DPI_AWARE = 2. A non-zero HRESULT can simply mean the
        # process already has a DPI-awareness context, so fall through to verification.
        shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            return False

    return True
