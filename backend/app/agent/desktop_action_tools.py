from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import psutil

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition


_APP_EXECUTABLES: dict[str, str] = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "opera": "opera.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "code": "Code.exe",
    "vs code": "Code.exe",
    "visual studio code": "Code.exe",
    "steam": "steam.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
}

# Files that can execute code or commonly trigger active content are deliberately
# excluded from the low-risk "open file" layer. Later phases can expose these
# behind a stronger permission/confirmation path if needed.
_BLOCKED_OPEN_SUFFIXES = {
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


def _normalize_app_name(value: str) -> str:
    normalized = " ".join(value.strip().lower().replace("_", " ").split())
    if normalized.endswith(".exe"):
        normalized = normalized[:-4].strip()
    return normalized


def _supported_app_names() -> list[str]:
    canonical = {
        "chrome",
        "opera",
        "edge",
        "visual studio code",
        "steam",
        "calculator",
        "notepad",
        "file explorer",
        "windows terminal",
    }
    return sorted(canonical)


def _app_executable(app_name: str) -> str:
    normalized = _normalize_app_name(app_name)
    executable = _APP_EXECUTABLES.get(normalized)
    if not executable:
        supported = ", ".join(_supported_app_names())
        raise ValueError(f"Unsupported app '{app_name}'. Supported apps: {supported}")
    return executable


def _registry_app_path(executable: str) -> Path | None:
    if platform.system() != "Windows":
        return None

    try:
        import winreg
    except ImportError:
        return None

    key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _kind = winreg.QueryValueEx(key, None)
            candidate = Path(str(value).strip('"'))
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def _common_app_candidates(executable: str) -> list[Path]:
    local_raw = os.environ.get("LOCALAPPDATA")
    program_files_raw = os.environ.get("ProgramFiles")
    program_files_x86_raw = os.environ.get("ProgramFiles(x86)")
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))

    local = Path(local_raw) if local_raw else None
    program_files = Path(program_files_raw) if program_files_raw else None
    program_files_x86 = Path(program_files_x86_raw) if program_files_x86_raw else None

    candidates: list[Path] = []
    if executable == "chrome.exe":
        if local:
            candidates.append(local / "Google" / "Chrome" / "Application" / executable)
        if program_files:
            candidates.append(program_files / "Google" / "Chrome" / "Application" / executable)
        if program_files_x86:
            candidates.append(program_files_x86 / "Google" / "Chrome" / "Application" / executable)
    elif executable == "opera.exe":
        if local:
            candidates.append(local / "Programs" / "Opera" / executable)
        if program_files:
            candidates.append(program_files / "Opera" / executable)
        if program_files_x86:
            candidates.append(program_files_x86 / "Opera" / executable)
    elif executable == "msedge.exe":
        if program_files_x86:
            candidates.append(program_files_x86 / "Microsoft" / "Edge" / "Application" / executable)
        if program_files:
            candidates.append(program_files / "Microsoft" / "Edge" / "Application" / executable)
    elif executable == "Code.exe":
        if local:
            candidates.append(local / "Programs" / "Microsoft VS Code" / executable)
        if program_files:
            candidates.append(program_files / "Microsoft VS Code" / executable)
    elif executable == "steam.exe":
        if program_files_x86:
            candidates.append(program_files_x86 / "Steam" / executable)
        if program_files:
            candidates.append(program_files / "Steam" / executable)
    elif executable == "calc.exe":
        candidates.append(system_root / "System32" / executable)
    elif executable == "notepad.exe":
        candidates.append(system_root / "System32" / executable)
    elif executable == "explorer.exe":
        candidates.append(system_root / executable)

    return candidates


def _resolve_executable(app_name: str) -> tuple[str, Path | None]:
    executable = _app_executable(app_name)

    registry_path = _registry_app_path(executable)
    if registry_path:
        return executable, registry_path

    which_path = shutil.which(executable)
    if which_path:
        return executable, Path(which_path)

    for candidate in _common_app_candidates(executable):
        if candidate.exists():
            return executable, candidate

    return executable, None


def _matching_pids(executable: str) -> set[int]:
    target = executable.lower()
    matches: set[int] = set()
    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = str(process.info.get("name") or "").lower()
            if name == target:
                matches.add(int(process.info["pid"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return matches


def _focus_windows_process(executable: str) -> dict[str, Any]:
    if platform.system() != "Windows":
        return {"supported": False, "focused": False, "reason": "Windows-only focus support"}

    pids = _matching_pids(executable)
    if not pids:
        return {"supported": True, "focused": False, "reason": "App is not running"}

    user32 = ctypes.windll.user32
    target_hwnd: int | None = None
    target_title = ""

    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_proc(hwnd: int, _lparam: int) -> bool:
        nonlocal target_hwnd, target_title
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
        if not title:
            return True

        target_hwnd = int(hwnd)
        target_title = title
        return False

    user32.EnumWindows(enum_proc_type(enum_proc), 0)

    if not target_hwnd:
        return {
            "supported": True,
            "focused": False,
            "reason": "The app is running but no visible window was found",
            "process_count": len(pids),
        }

    user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
    focused = bool(user32.SetForegroundWindow(target_hwnd))
    return {
        "supported": True,
        "focused": focused,
        "title": target_title,
        "process_count": len(pids),
        "reason": None if focused else "Windows did not allow the foreground switch",
    }


def _known_folder(raw: str) -> Path | None:
    normalized = " ".join(raw.strip().lower().replace("_", " ").split())
    normalized = normalized.removeprefix("my ").removesuffix(" folder").strip()
    home = Path.home()
    folders = {
        "home": home,
        "user": home,
        "desktop": home / "Desktop",
        "downloads": home / "Downloads",
        "documents": home / "Documents",
        "pictures": home / "Pictures",
        "music": home / "Music",
        "videos": home / "Videos",
        "sarahnode": home / "SarahNode",
        "sarah node": home / "SarahNode",
        "sarahnode repo": home / "SarahNode",
        "sarah node repo": home / "SarahNode",
    }
    return folders.get(normalized)


def _resolve_open_path(raw_path: str) -> Path:
    known = _known_folder(raw_path)
    if known is not None:
        return known.resolve()

    expanded = os.path.expandvars(os.path.expanduser(raw_path.strip().strip('"')))
    if not expanded:
        raise ValueError("path is required")
    return Path(expanded).resolve()


def _find_unique_file_by_name(raw_name: str) -> Path | None:
    name = raw_name.strip().strip('"')
    if not name or any(sep in name for sep in ("\\", "/")):
        return None

    # Only treat names with an extension as file-name lookup requests. This avoids
    # accidentally turning an arbitrary phrase into an expensive home-folder scan.
    if not Path(name).suffix:
        return None

    target = name.lower()
    root = Path.home()
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

        for filename in filenames:
            visited += 1
            if visited > 30000:
                break
            if filename.lower() != target:
                continue
            matches.append(current / filename)
            if len(matches) >= 4:
                break

        if visited > 30000 or len(matches) >= 4:
            break

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0].resolve()

    rendered = "; ".join(str(path) for path in matches[:3])
    raise ValueError(f"Multiple files named '{name}' were found. Use an exact path. Matches: {rendered}")


def _normalize_http_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if not candidate:
        raise ValueError("url is required")

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are allowed in the safe launch layer")
    if not parsed.netloc:
        raise ValueError("URL must include a host name")
    return candidate


async def open_app_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    app = str(arguments.get("app", "")).strip()
    if not app:
        raise ValueError("app is required")
    if platform.system() != "Windows":
        raise ValueError("Safe app launching is currently implemented for Windows")

    executable, resolved = _resolve_executable(app)

    # Prefer focusing an already-visible instance instead of spawning duplicates.
    focus_result = _focus_windows_process(executable)
    if focus_result.get("focused"):
        return {
            "app": app,
            "executable": executable,
            "action": "focused_existing",
            "window_title": focus_result.get("title"),
        }

    if resolved is None:
        raise ValueError(f"{app} is supported, but its executable could not be found on this computer")

    subprocess.Popen([str(resolved)], close_fds=True)
    return {
        "app": app,
        "executable": executable,
        "path": str(resolved),
        "action": "launched",
    }


async def focus_app_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    app = str(arguments.get("app", "")).strip()
    if not app:
        raise ValueError("app is required")
    executable = _app_executable(app)
    result = _focus_windows_process(executable)
    return {"app": app, "executable": executable, **result}


async def open_path_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    raw_path = str(arguments.get("path", "")).strip()
    path = _resolve_open_path(raw_path)

    if not path.exists():
        by_name = _find_unique_file_by_name(raw_path)
        if by_name is not None:
            path = by_name

    if not path.exists():
        raise ValueError(f"Path does not exist: {raw_path}")

    if path.is_file() and path.suffix.lower() in _BLOCKED_OPEN_SUFFIXES:
        raise ValueError(
            f"Opening '{path.suffix}' files is blocked in the low-risk desktop layer because they can execute code or active content"
        )

    if platform.system() == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)], close_fds=True)
    else:
        subprocess.Popen(["xdg-open", str(path)], close_fds=True)

    return {
        "path": str(path),
        "kind": "folder" if path.is_dir() else "file",
        "action": "opened",
    }


async def open_url_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    raw_url = str(arguments.get("url", "")).strip()
    url = _normalize_http_url(raw_url)
    opened = bool(webbrowser.open(url, new=2, autoraise=True))
    if not opened:
        raise RuntimeError("The operating system did not accept the URL launch request")
    return {"url": url, "action": "opened"}


def desktop_action_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="open_app",
            description=(
                "Open a supported desktop app, or focus an existing visible instance instead of launching a duplicate. "
                "Supported apps include Chrome, Opera, Edge, Visual Studio Code, Steam, Calculator, Notepad, File Explorer, and Windows Terminal. "
                "This tool cannot execute arbitrary commands or arbitrary executable paths."
            ),
            handler=open_app_handler,
            parameters={
                "type": "object",
                "properties": {"app": {"type": "string"}},
                "required": ["app"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.APPS_LAUNCH}),
            risk=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="focus_app",
            description="Bring an already-running supported Windows app to the foreground without launching a new instance.",
            handler=focus_app_handler,
            parameters={
                "type": "object",
                "properties": {"app": {"type": "string"}},
                "required": ["app"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.APPS_FOCUS}),
            risk=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="open_path",
            description=(
                "Open an existing local folder or a non-executable file with its normal desktop application. "
                "Known folder names such as Downloads, Documents, Desktop, Pictures, and SarahNode are accepted. "
                "A unique file name such as budget.xlsx can also be resolved within the user's home folder. "
                "Executable, script, shortcut, installer, registry, and macro-enabled file types are blocked."
            ),
            handler=open_path_handler,
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Existing path, unique file name, or known folder name such as Downloads, Documents, Desktop, or SarahNode.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.FILES_OPEN}),
            risk=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="open_url",
            description="Open an http:// or https:// web address in the user's default browser. Other URL schemes are blocked.",
            handler=open_url_handler,
            parameters={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.WEB_LAUNCH}),
            risk=RiskLevel.LOW,
        ),
    ]
