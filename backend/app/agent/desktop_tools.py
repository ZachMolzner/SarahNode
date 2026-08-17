from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path
from typing import Any, Mapping

import psutil

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


async def system_resources_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    memory = psutil.virtual_memory()
    disk_root = Path.home().anchor or os.sep
    disk = psutil.disk_usage(disk_root)
    boot_time = psutil.boot_time()

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.15),
        "cpu_logical_count": psutil.cpu_count(logical=True),
        "memory": {
            "total_gb": round(memory.total / (1024 ** 3), 2),
            "available_gb": round(memory.available / (1024 ** 3), 2),
            "used_percent": memory.percent,
        },
        "disk": {
            "root": disk_root,
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
            "used_percent": disk.percent,
        },
        "boot_time_epoch": boot_time,
    }


async def running_processes_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    limit = _clamp_int(arguments.get("limit"), default=25, minimum=1, maximum=100)
    name_filter = str(arguments.get("name_filter", "")).strip().lower()

    rows: list[dict[str, Any]] = []
    for process in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            name = (process.info.get("name") or "").strip()
            if not name:
                continue
            if name_filter and name_filter not in name.lower():
                continue
            memory_info = process.info.get("memory_info")
            rows.append(
                {
                    "pid": int(process.info["pid"]),
                    "name": name,
                    "memory_mb": round((memory_info.rss if memory_info else 0) / (1024 ** 2), 1),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    rows.sort(key=lambda item: (item["memory_mb"], item["name"].lower()), reverse=True)
    return {
        "processes": rows[:limit],
        "returned": min(len(rows), limit),
        "matched": len(rows),
    }


def _windows_active_window() -> dict[str, Any]:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"supported": True, "title": "", "pid": None, "process_name": None}

    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)

    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    process_name: str | None = None
    if pid.value:
        try:
            process_name = psutil.Process(pid.value).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = None

    return {
        "supported": True,
        "title": buffer.value,
        "pid": int(pid.value) if pid.value else None,
        "process_name": process_name,
    }


async def active_window_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if platform.system() != "Windows":
        return {
            "supported": False,
            "reason": "Active-window inspection is currently implemented for Windows only.",
            "platform": platform.system(),
        }
    return _windows_active_window()


def _safe_search_root(raw_root: str | None) -> Path:
    if raw_root:
        candidate = Path(raw_root).expanduser()
    else:
        candidate = Path.home()
    return candidate.resolve()


async def find_files_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    query = str(arguments.get("query", "")).strip().lower()
    if not query:
        raise ValueError("query is required")

    root = _safe_search_root(str(arguments.get("root", "")).strip() or None)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Search root is not a directory: {root}")

    limit = _clamp_int(arguments.get("limit"), default=20, minimum=1, maximum=50)
    max_depth = _clamp_int(arguments.get("max_depth"), default=5, minimum=1, maximum=8)
    max_visited = 25000

    matches: list[dict[str, Any]] = []
    visited = 0
    root_depth = len(root.parts)

    for current_dir, dirnames, filenames in os.walk(root):
        current_path = Path(current_dir)
        depth = len(current_path.parts) - root_depth
        if depth >= max_depth:
            dirnames[:] = []

        # Avoid large/cache/system-style folders by default while still allowing
        # the user to point the root directly at one if they actually want it.
        dirnames[:] = [
            name
            for name in dirnames
            if not name.startswith(".")
            and name.lower() not in {"node_modules", "target", "__pycache__", "$recycle.bin"}
        ]

        for name in filenames:
            visited += 1
            if visited > max_visited:
                return {
                    "root": str(root),
                    "query": query,
                    "matches": matches,
                    "returned": len(matches),
                    "truncated": True,
                    "visited_files": visited,
                }

            if query not in name.lower():
                continue

            path = current_path / name
            try:
                stat = path.stat()
                size = stat.st_size
                modified = stat.st_mtime
            except OSError:
                size = None
                modified = None

            matches.append(
                {
                    "name": name,
                    "path": str(path),
                    "size_bytes": size,
                    "modified_epoch": modified,
                }
            )
            if len(matches) >= limit:
                return {
                    "root": str(root),
                    "query": query,
                    "matches": matches,
                    "returned": len(matches),
                    "truncated": False,
                    "visited_files": visited,
                }

    return {
        "root": str(root),
        "query": query,
        "matches": matches,
        "returned": len(matches),
        "truncated": False,
        "visited_files": visited,
    }


def desktop_read_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="system_resources",
            description=(
                "Read current host CPU usage, memory usage, disk usage, and boot time. "
                "Use this for questions about how busy or full the computer is."
            ),
            handler=system_resources_handler,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.SYSTEM_READ}),
            risk=RiskLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="running_processes",
            description=(
                "List currently running processes on the SarahNode computer, optionally filtered by process name. "
                "This is read-only and does not stop or alter any process."
            ),
            handler=running_processes_handler,
            parameters={
                "type": "object",
                "properties": {
                    "name_filter": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": [],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.DESKTOP_READ}),
            risk=RiskLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="active_window",
            description=(
                "Read the title and process name of the currently focused foreground window on Windows. "
                "Use this when the user asks what app or window they are currently using."
            ),
            handler=active_window_handler,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.DESKTOP_READ}),
            risk=RiskLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="find_files",
            description=(
                "Search filenames on the local computer without opening, changing, moving, or deleting them. "
                "Defaults to the current user's home folder and returns matching file paths."
            ),
            handler=find_files_handler,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Part of the filename to search for."},
                    "root": {"type": "string", "description": "Optional folder to search. Defaults to the user's home folder."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "max_depth": {"type": "integer", "minimum": 1, "maximum": 8},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.FILES_READ}),
            risk=RiskLevel.READ_ONLY,
        ),
    ]
