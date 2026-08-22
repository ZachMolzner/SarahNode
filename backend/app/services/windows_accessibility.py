from __future__ import annotations

import asyncio
import base64
import ctypes
import json
import os
import platform
import subprocess
from dataclasses import dataclass
from ctypes import wintypes

from app.services.screen_awareness import ScreenAnalysisResult, ScreenAwarenessError, ScreenAwarenessService, VisualTarget


@dataclass(frozen=True, slots=True)
class AccessibilityMatch:
    name: str
    control_type: str
    left: int
    top: int
    right: int
    bottom: int
    exact: bool


# The PowerShell program is static. The requested control name is passed only through
# an environment variable so user text is never interpolated into executable code.
_UIA_SCRIPT = r'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$query = $env:SARAH_UIA_QUERY
if ([string]::IsNullOrWhiteSpace($query)) {
    Write-Output '{"found":false}'
    exit 0
}

$root = [System.Windows.Automation.AutomationElement]::RootElement
$trueCondition = [System.Windows.Automation.Condition]::TrueCondition
$elements = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $trueCondition)

$best = $null
$bestScore = -1
$limit = [Math]::Min($elements.Count, 12000)
$queryNorm = $query.Trim().ToLowerInvariant()

for ($i = 0; $i -lt $limit; $i++) {
    $element = $elements.Item($i)
    try {
        $current = $element.Current
        if ($current.IsOffscreen) { continue }
        $name = [string]$current.Name
        if ([string]::IsNullOrWhiteSpace($name)) { continue }
        $rect = $current.BoundingRectangle
        if ($rect.Width -lt 2 -or $rect.Height -lt 2) { continue }

        $nameNorm = $name.Trim().ToLowerInvariant()
        $score = 0
        $exact = $false
        if ($nameNorm -eq $queryNorm) {
            $score = 1000
            $exact = $true
        } elseif ($nameNorm.Contains($queryNorm)) {
            $score = 700 - [Math]::Min(200, [Math]::Abs($nameNorm.Length - $queryNorm.Length))
        } elseif ($queryNorm.Contains($nameNorm) -and $nameNorm.Length -ge 3) {
            $score = 500 - [Math]::Min(200, [Math]::Abs($nameNorm.Length - $queryNorm.Length))
        } else {
            continue
        }

        # Prefer interactive-looking controls over large containers/text nodes when
        # names are otherwise equally good.
        $controlType = [string]$current.ControlType.ProgrammaticName
        if ($controlType -match 'Button|Edit|Hyperlink|TabItem|MenuItem|CheckBox|RadioButton|ComboBox|ListItem') {
            $score += 80
        }
        if ($rect.Width -gt 1600 -or $rect.Height -gt 1000) { $score -= 100 }

        if ($score -gt $bestScore) {
            $bestScore = $score
            $best = [ordered]@{
                found = $true
                name = $name
                control_type = $controlType
                left = [int][Math]::Round($rect.Left)
                top = [int][Math]::Round($rect.Top)
                right = [int][Math]::Round($rect.Right)
                bottom = [int][Math]::Round($rect.Bottom)
                exact = $exact
                score = $score
            }
        }
    } catch {
        continue
    }
}

if ($null -eq $best) {
    Write-Output '{"found":false}'
} else {
    $best | ConvertTo-Json -Compress
}
'''


def _encoded_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def _virtual_screen_bounds() -> tuple[int, int, int, int]:
    if platform.system() != "Windows":
        raise ScreenAwarenessError("Windows accessibility control lookup is available only on Windows.")
    user32 = ctypes.windll.user32
    # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN
    left = int(user32.GetSystemMetrics(76))
    top = int(user32.GetSystemMetrics(77))
    width = int(user32.GetSystemMetrics(78))
    height = int(user32.GetSystemMetrics(79))
    if width <= 0 or height <= 0:
        raise ScreenAwarenessError("Windows did not report a usable virtual desktop size.")
    return left, top, width, height


def _normalize_rect(
    rect: tuple[int, int, int, int],
    desktop: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    left, top, right, bottom = rect
    desk_left, desk_top, desk_width, desk_height = desktop
    if right <= left or bottom <= top:
        return None
    desk_right = desk_left + desk_width
    desk_bottom = desk_top + desk_height
    if right <= desk_left or left >= desk_right or bottom <= desk_top or top >= desk_bottom:
        return None

    left = max(desk_left, min(desk_right, left))
    right = max(desk_left, min(desk_right, right))
    top = max(desk_top, min(desk_bottom, top))
    bottom = max(desk_top, min(desk_bottom, bottom))
    if right <= left or bottom <= top:
        return None

    norm_left = int(round((left - desk_left) * 1000 / desk_width))
    norm_right = int(round((right - desk_left) * 1000 / desk_width))
    norm_top = int(round((top - desk_top) * 1000 / desk_height))
    norm_bottom = int(round((bottom - desk_top) * 1000 / desk_height))
    normalized = tuple(max(0, min(1000, value)) for value in (norm_left, norm_top, norm_right, norm_bottom))
    if normalized[2] <= normalized[0] or normalized[3] <= normalized[1]:
        return None
    return normalized


def _parse_match(stdout: str) -> AccessibilityMatch | None:
    text = stdout.strip()
    if not text:
        return None
    # PowerShell can emit benign assembly/runtime lines before JSON on some hosts.
    line = next((candidate.strip() for candidate in reversed(text.splitlines()) if candidate.strip().startswith("{")), "")
    if not line:
        return None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload.get("found"):
        return None
    try:
        left = int(payload["left"])
        top = int(payload["top"])
        right = int(payload["right"])
        bottom = int(payload["bottom"])
    except (KeyError, TypeError, ValueError):
        return None
    name = str(payload.get("name") or "").strip()
    if not name or right <= left or bottom <= top:
        return None
    return AccessibilityMatch(
        name=name,
        control_type=str(payload.get("control_type") or "Control").replace("ControlType.", ""),
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        exact=bool(payload.get("exact")),
    )


def _run_lookup(target_query: str) -> AccessibilityMatch | None:
    if platform.system() != "Windows":
        return None
    env = os.environ.copy()
    env["SARAH_UIA_QUERY"] = target_query
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                _encoded_powershell(_UIA_SCRIPT),
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            env=env,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return _parse_match(completed.stdout)


async def locate_control_with_windows_accessibility(
    screen: ScreenAwarenessService,
    target_query: str,
) -> ScreenAnalysisResult | None:
    """Locate a visible named UI control through Windows UI Automation.

    SarahNode is hidden during the lookup so the accessibility tree from Sarah's own
    chat cannot satisfy a query such as "Search the web" or "Not now".
    """
    if platform.system() != "Windows":
        return None

    hidden_hwnd: int | None = None
    try:
        hidden_hwnd = screen._hide_sarah_if_foreground()
        if hidden_hwnd is not None:
            await asyncio.sleep(0.2)
        match = await asyncio.to_thread(_run_lookup, target_query)
    finally:
        screen._restore_sarah_window(hidden_hwnd)

    if match is None:
        return None

    desktop = _virtual_screen_bounds()
    bbox = _normalize_rect((match.left, match.top, match.right, match.bottom), desktop)
    if bbox is None:
        return None

    desk_left, desk_top, desk_width, desk_height = desktop
    confidence = 0.99 if match.exact else 0.82
    target = VisualTarget(
        label=match.name,
        role=match.control_type or "control",
        visible_text=match.name,
        bbox_normalized=bbox,
        confidence=confidence,
    )
    return ScreenAnalysisResult(
        text=f'Windows accessibility identified "{match.name}" as a visible {target.role}.',
        model="windows-uia",
        reasoning_mode="locate",
        source_width=desk_width,
        source_height=desk_height,
        sent_width=desk_width,
        sent_height=desk_height,
        capture_left=desk_left,
        capture_top=desk_top,
        capture_width=desk_width,
        capture_height=desk_height,
        sarah_hidden_for_capture=hidden_hwnd is not None,
        targets=(target,),
        recommended_steps=(),
        caution=None,
    )
