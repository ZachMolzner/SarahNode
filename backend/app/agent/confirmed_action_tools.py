from __future__ import annotations

import asyncio
import ctypes
import os
import platform
import shutil
from pathlib import Path
from typing import Any, Mapping

import psutil
from send2trash import send2trash

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition
from app.agent.desktop_action_tools import _app_executable, _normalize_app_name


_BLOCKED_CREATE_SUFFIXES = {
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".hta",
    ".js",
    ".jse",
    ".lnk",
    ".msi",
    ".msp",
    ".ps1",
    ".reg",
    ".scr",
    ".url",
    ".vbe",
    ".vbs",
    ".wsf",
    ".wsh",
    ".docm",
    ".dotm",
    ".xlsm",
    ".xltm",
    ".xlam",
    ".pptm",
    ".potm",
    ".ppam",
    ".ppsm",
}

_SEARCH_SKIP_DIRS = {
    "$recycle.bin",
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "appdata",
    "node_modules",
    "target",
}

# Launch aliases and running process names are not always the same on modern
# Windows. Calculator is the clearest example: calc.exe is a launcher/alias while
# the visible app commonly runs as CalculatorApp.exe. Keeping this mapping separate
# makes close/terminate behavior reliable without changing the safe app launcher.
_APP_PROCESS_NAMES: dict[str, tuple[str, ...]] = {
    "chrome": ("chrome.exe",),
    "google chrome": ("chrome.exe",),
    "opera": ("opera.exe",),
    "edge": ("msedge.exe",),
    "microsoft edge": ("msedge.exe",),
    "code": ("code.exe",),
    "vs code": ("code.exe",),
    "visual studio code": ("code.exe",),
    "steam": ("steam.exe",),
    "calculator": ("calculatorapp.exe", "calc.exe"),
    "calc": ("calculatorapp.exe", "calc.exe"),
    "notepad": ("notepad.exe",),
    "explorer": ("explorer.exe",),
    "file explorer": ("explorer.exe",),
    "terminal": ("windowsterminal.exe", "wt.exe"),
    "windows terminal": ("windowsterminal.exe", "wt.exe"),
}

_FORCE_TERMINATE_BLOCKED_APPS = {"explorer", "file explorer"}


def _home() -> Path:
    return Path.home().resolve()


def _protected_roots() -> tuple[Path, ...]:
    home = _home()
    return (
        home,
        (home / "SarahNode").resolve(),
        (home / "AppData").resolve(),
        (home / ".ssh").resolve(),
    )


def _protected_profile_roots() -> tuple[Path, ...]:
    home = _home()
    return tuple(
        (home / name).resolve()
        for name in ("Desktop", "Downloads", "Documents", "Pictures", "Music", "Videos")
    )


def _known_folder(raw: str) -> Path | None:
    normalized = " ".join(raw.strip().lower().replace("_", " ").split())
    normalized = normalized.removeprefix("my ").removesuffix(" folder").strip()
    home = _home()
    mapping = {
        "desktop": home / "Desktop",
        "downloads": home / "Downloads",
        "documents": home / "Documents",
        "pictures": home / "Pictures",
        "music": home / "Music",
        "videos": home / "Videos",
    }
    return mapping.get(normalized)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_candidate(raw: str) -> Path:
    known = _known_folder(raw)
    if known is not None:
        return known.resolve()
    expanded = os.path.expandvars(os.path.expanduser(raw.strip().strip('"').strip("'")))
    if not expanded:
        raise ValueError("A path is required")
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = _home() / candidate
    return candidate.resolve()


def _find_unique_existing_name(raw: str) -> Path | None:
    name = raw.strip().strip('"').strip("'")
    if not name or any(separator in name for separator in ("\\", "/")):
        return None

    target = name.lower()
    root = _home()
    root_depth = len(root.parts)
    visited = 0
    matches: list[Path] = []

    for current_dir, dirnames, filenames in os.walk(root):
        current = Path(current_dir)
        depth = len(current.parts) - root_depth
        if depth >= 6:
            dirnames[:] = []

        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not dirname.startswith(".") and dirname.lower() not in _SEARCH_SKIP_DIRS
        ]

        for entry in [*dirnames, *filenames]:
            visited += 1
            if visited > 30000:
                break
            if entry.lower() != target:
                continue
            matches.append((current / entry).resolve())
            if len(matches) >= 4:
                break

        if visited > 30000 or len(matches) >= 4:
            break

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    rendered = "; ".join(str(path) for path in matches[:3])
    raise ValueError(f"Multiple items named '{name}' were found. Use an exact path. Matches: {rendered}")


def resolve_existing_mutation_path(raw: str) -> Path:
    candidate = _resolve_candidate(raw)
    if not candidate.exists():
        found = _find_unique_existing_name(raw)
        if found is not None:
            candidate = found
    if not candidate.exists():
        raise ValueError(f"Path does not exist: {raw}")
    if candidate.resolve() in _protected_profile_roots():
        raise ValueError(f"Phase 4C protects the top-level profile folder {candidate}")
    _assert_mutation_allowed(candidate)
    return candidate


def resolve_new_mutation_path(raw: str) -> Path:
    candidate = _resolve_candidate(raw)
    _assert_mutation_allowed(candidate)
    if candidate.exists():
        raise ValueError(f"Path already exists: {candidate}")
    parent = candidate.parent
    if not parent.exists() or not parent.is_dir():
        raise ValueError(f"Parent folder does not exist: {parent}")
    _assert_mutation_allowed(parent)
    return candidate


def _assert_mutation_allowed(path: Path) -> None:
    resolved = path.resolve()
    home = _home()
    if not _is_within(resolved, home):
        raise ValueError("Phase 4C file changes are restricted to your user profile")

    for protected in _protected_roots():
        if resolved == protected or _is_within(resolved, protected):
            if protected == home and resolved != home:
                continue
            label = "your home directory" if protected == home else str(protected)
            raise ValueError(f"Phase 4C protects {label} from file mutations")


def preview_move(source_raw: str, destination_raw: str) -> tuple[Path, Path]:
    source = resolve_existing_mutation_path(source_raw)
    destination_candidate = _resolve_candidate(destination_raw)

    if destination_candidate.exists() and destination_candidate.is_dir():
        destination = (destination_candidate / source.name).resolve()
    else:
        destination = destination_candidate.resolve()

    _assert_mutation_allowed(destination)
    _assert_mutation_allowed(destination.parent)
    if not destination.parent.exists() or not destination.parent.is_dir():
        raise ValueError(f"Destination folder does not exist: {destination.parent}")
    if destination.exists():
        raise ValueError(f"Destination already exists: {destination}")
    if source == destination:
        raise ValueError("Source and destination are the same")
    return source, destination


async def create_folder_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    path = resolve_new_mutation_path(str(arguments.get("path", "")))
    path.mkdir()
    return {"action": "created_folder", "path": str(path)}


async def create_file_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    path = resolve_new_mutation_path(str(arguments.get("path", "")))
    if path.suffix.lower() in _BLOCKED_CREATE_SUFFIXES:
        raise ValueError(f"Creating '{path.suffix}' files is blocked in Phase 4C")

    content = str(arguments.get("content", ""))
    if len(content.encode("utf-8")) > 100_000:
        raise ValueError("Phase 4C file creation is limited to 100 KB of text")

    path.write_text(content, encoding="utf-8")
    return {"action": "created_file", "path": str(path), "bytes": len(content.encode("utf-8"))}


async def move_path_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    source, destination = preview_move(
        str(arguments.get("source", "")),
        str(arguments.get("destination", "")),
    )
    shutil.move(str(source), str(destination))
    return {
        "action": "moved",
        "source": str(source),
        "destination": str(destination),
    }


async def recycle_path_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    path = resolve_existing_mutation_path(str(arguments.get("path", "")))
    send2trash(str(path))
    return {"action": "recycled", "path": str(path)}


def _process_names_for_app(app: str) -> tuple[str, ...]:
    # Validate against the same app allowlist used for launching/focusing first.
    executable = _app_executable(app)
    normalized = _normalize_app_name(app)
    names = _APP_PROCESS_NAMES.get(normalized)
    if names:
        return names
    return (executable.lower(),)


def _matching_pids_for_app(app: str) -> set[int]:
    names = {name.lower() for name in _process_names_for_app(app)}
    matches: set[int] = set()
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = str(process.info.get("name") or "").lower()
            if name in names:
                matches.add(int(process.info["pid"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return matches


def _visible_windows_for_pids(pids: set[int]) -> list[tuple[int, str]]:
    if platform.system() != "Windows" or not pids:
        return []

    user32 = ctypes.windll.user32
    windows: list[tuple[int, str]] = []
    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_proc(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) not in pids:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if title:
            windows.append((int(hwnd), title))
        return True

    user32.EnumWindows(enum_proc_type(enum_proc), 0)
    return windows


def _calculator_window_fallback() -> list[tuple[int, str]]:
    """Find the Calculator frame when Windows hosts it outside CalculatorApp.exe."""
    if platform.system() != "Windows":
        return []

    user32 = ctypes.windll.user32
    windows: list[tuple[int, str]] = []
    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_proc(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if title.lower() == "calculator":
            windows.append((int(hwnd), title))
        return True

    user32.EnumWindows(enum_proc_type(enum_proc), 0)
    return windows


def _visible_windows_for_app(app: str, pids: set[int] | None = None) -> list[tuple[int, str]]:
    resolved_pids = pids if pids is not None else _matching_pids_for_app(app)
    windows = _visible_windows_for_pids(resolved_pids)
    if windows:
        return windows

    if _normalize_app_name(app) in {"calculator", "calc"}:
        return _calculator_window_fallback()
    return []


async def close_app_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    app = str(arguments.get("app", "")).strip()
    if not app:
        raise ValueError("app is required")
    if platform.system() != "Windows":
        raise ValueError("Phase 4C app closing is currently implemented for Windows")

    pids_before = _matching_pids_for_app(app)
    windows = _visible_windows_for_app(app, pids_before)
    if not pids_before and not windows:
        return {"action": "already_closed", "app": app, "process_count": 0, "windows_signaled": 0}

    if not windows:
        # Background/helper processes do not mean a user-visible app is still open.
        return {
            "action": "already_closed",
            "app": app,
            "process_count": len(pids_before),
            "windows_signaled": 0,
            "background_processes": len(pids_before),
        }

    user32 = ctypes.windll.user32
    wm_close = 0x0010
    signaled = 0
    for hwnd, _title in windows:
        if user32.PostMessageW(hwnd, wm_close, 0, 0):
            signaled += 1

    if signaled == 0:
        return {
            "action": "close_incomplete",
            "app": app,
            "process_count": len(pids_before),
            "windows_signaled": 0,
            "reason": "Windows did not accept a normal close request for the visible app window",
        }

    # Verify the visible windows actually disappear. Browser helper/background
    # processes may remain, which is fine; the user-visible application is closed.
    remaining_windows = windows
    for _ in range(15):
        await asyncio.sleep(0.2)
        current_pids = _matching_pids_for_app(app)
        remaining_windows = _visible_windows_for_app(app, current_pids)
        if not remaining_windows:
            return {
                "action": "closed",
                "app": app,
                "process_count_before": len(pids_before),
                "remaining_processes": len(current_pids),
                "windows_signaled": signaled,
            }

    return {
        "action": "close_incomplete",
        "app": app,
        "process_count": len(_matching_pids_for_app(app)),
        "windows_signaled": signaled,
        "remaining_windows": [title for _hwnd, title in remaining_windows[:5]],
        "reason": "The app ignored the normal close request. You can ask me to force close it if needed.",
    }


async def terminate_app_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    app = str(arguments.get("app", "")).strip()
    if not app:
        raise ValueError("app is required")
    if platform.system() != "Windows":
        raise ValueError("Confirmed force app termination is currently implemented for Windows")

    normalized = _normalize_app_name(app)
    _app_executable(app)  # validate allowlist
    if normalized in _FORCE_TERMINATE_BLOCKED_APPS:
        raise ValueError("Force-closing File Explorer is blocked because explorer.exe also hosts the Windows shell")

    pids = _matching_pids_for_app(app)
    if not pids:
        return {"action": "already_closed", "app": app, "terminated": 0, "remaining_processes": 0}

    processes: list[psutil.Process] = []
    failures: list[str] = []
    current_pid = os.getpid()
    for pid in sorted(pids):
        if pid == current_pid:
            failures.append(f"Skipped Sarah's own process PID {pid}")
            continue
        try:
            process = psutil.Process(pid)
            process.terminate()
            processes.append(process)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except (psutil.AccessDenied, OSError) as exc:
            failures.append(f"PID {pid}: {exc}")

    _gone, alive = psutil.wait_procs(processes, timeout=2.0)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except (psutil.AccessDenied, OSError) as exc:
            failures.append(f"PID {process.pid}: {exc}")

    if alive:
        psutil.wait_procs(alive, timeout=2.0)
    await asyncio.sleep(0.2)

    remaining = _matching_pids_for_app(app)
    action = "terminated" if not remaining else "terminate_incomplete"
    return {
        "action": action,
        "app": app,
        "requested_processes": len(pids),
        "terminated": max(0, len(pids) - len(remaining)),
        "remaining_processes": len(remaining),
        "failures": failures[:10],
        "reason": None if not remaining else "Some matching processes are still running",
    }


def confirmed_action_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="create_folder",
            description="Create one folder inside the user's profile. Requires explicit user confirmation before execution.",
            handler=create_folder_handler,
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.FILES_CREATE}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="create_file",
            description="Create one new non-executable UTF-8 text file inside the user's profile. Never overwrites an existing file. Requires explicit confirmation.",
            handler=create_file_handler,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.FILES_CREATE}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="move_path",
            description="Move or rename one existing file/folder inside the user's profile without overwriting. Requires explicit confirmation.",
            handler=move_path_handler,
            parameters={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                },
                "required": ["source", "destination"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.FILES_MOVE}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="recycle_path",
            description="Move one existing file/folder to the operating-system Recycle Bin instead of permanently deleting it. Requires explicit confirmation.",
            handler=recycle_path_handler,
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.FILES_RECYCLE}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="close_app",
            description=(
                "Close all visible windows of one supported app using the normal Windows close path and verify the windows disappear. "
                "Does not force-terminate processes. Requires explicit confirmation."
            ),
            handler=close_app_handler,
            parameters={
                "type": "object",
                "properties": {"app": {"type": "string"}},
                "required": ["app"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.APPS_CLOSE}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
        ),
        ToolDefinition(
            name="terminate_app",
            description=(
                "Force-close all matching processes for one supported app after an explicit user request such as kill, terminate, or force close. "
                "This can discard unsaved work. File Explorer is blocked. Requires explicit confirmation."
            ),
            handler=terminate_app_handler,
            parameters={
                "type": "object",
                "properties": {"app": {"type": "string"}},
                "required": ["app"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.APPS_TERMINATE}),
            risk=RiskLevel.HIGH,
            requires_confirmation=True,
        ),
    ]
