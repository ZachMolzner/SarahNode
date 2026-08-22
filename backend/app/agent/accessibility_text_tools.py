from __future__ import annotations

import base64
import json
import os
import platform
import subprocess
from typing import Any, Mapping

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition


_SET_VALUE_SCRIPT = r'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$query = $env:SARAH_UIA_QUERY
$text = $env:SARAH_UIA_TEXT
$expectedX = 0
$expectedY = 0
[int]::TryParse($env:SARAH_UIA_EXPECTED_X, [ref]$expectedX) | Out-Null
[int]::TryParse($env:SARAH_UIA_EXPECTED_Y, [ref]$expectedY) | Out-Null

if ([string]::IsNullOrWhiteSpace($query)) {
    Write-Output '{"ok":false,"reason":"missing_query"}'
    exit 0
}

$root = [System.Windows.Automation.AutomationElement]::RootElement
$scope = [System.Windows.Automation.TreeScope]::Descendants
$queryNorm = $query.Trim().ToLowerInvariant()
$best = $null
$bestScore = -1

function Consider-Element($element, $allowPartial) {
    try {
        $current = $element.Current
        if ($current.IsOffscreen) { return }
        $name = [string]$current.Name
        if ([string]::IsNullOrWhiteSpace($name)) { return }
        $rect = $current.BoundingRectangle
        if ($rect.Width -lt 2 -or $rect.Height -lt 2) { return }

        $nameNorm = $name.Trim().ToLowerInvariant()
        $score = 0
        if ($nameNorm -eq $queryNorm) {
            $score = 1000
        } elseif ($allowPartial -and $nameNorm.Contains($queryNorm)) {
            $score = 700 - [Math]::Min(200, [Math]::Abs($nameNorm.Length - $queryNorm.Length))
        } elseif ($allowPartial -and $queryNorm.Contains($nameNorm) -and $nameNorm.Length -ge 3) {
            $score = 500 - [Math]::Min(200, [Math]::Abs($nameNorm.Length - $queryNorm.Length))
        } else {
            return
        }

        if ($expectedX -ge $rect.Left -and $expectedX -le $rect.Right -and $expectedY -ge $rect.Top -and $expectedY -le $rect.Bottom) {
            $score += 600
        } else {
            $centerX = $rect.Left + ($rect.Width / 2.0)
            $centerY = $rect.Top + ($rect.Height / 2.0)
            $distance = [Math]::Sqrt([Math]::Pow($centerX - $expectedX, 2) + [Math]::Pow($centerY - $expectedY, 2))
            $score -= [Math]::Min(400, [int]($distance / 10.0))
        }

        if ($score -gt $script:bestScore) {
            $script:bestScore = $score
            $script:best = $element
        }
    } catch {
        return
    }
}

try {
    $flags = [System.Windows.Automation.PropertyConditionFlags]::IgnoreCase
    $nameCondition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::NameProperty,
        $query,
        $flags
    )
    $exactElements = $root.FindAll($scope, $nameCondition)
    $exactLimit = [Math]::Min($exactElements.Count, 100)
    for ($i = 0; $i -lt $exactLimit; $i++) {
        Consider-Element $exactElements.Item($i) $false
    }
} catch {}

if ($null -eq $best) {
    $elements = $root.FindAll($scope, [System.Windows.Automation.Condition]::TrueCondition)
    $limit = [Math]::Min($elements.Count, 7000)
    for ($i = 0; $i -lt $limit; $i++) {
        Consider-Element $elements.Item($i) $true
    }
}

if ($null -eq $best) {
    Write-Output '{"ok":false,"reason":"not_found"}'
    exit 0
}

try {
    $current = $best.Current
    if ([bool]$current.IsPassword) {
        Write-Output '{"ok":false,"reason":"password_field"}'
        exit 0
    }

    $patternObject = $null
    if (-not $best.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$patternObject)) {
        Write-Output '{"ok":false,"reason":"value_pattern_unavailable"}'
        exit 0
    }

    $valuePattern = [System.Windows.Automation.ValuePattern]$patternObject
    if ($valuePattern.Current.IsReadOnly) {
        Write-Output '{"ok":false,"reason":"read_only"}'
        exit 0
    }

    $best.SetFocus()
    $valuePattern.SetValue($text)
    [ordered]@{
        ok = $true
        name = [string]$current.Name
        control_type = [string]$current.ControlType.ProgrammaticName
        character_count = $text.Length
    } | ConvertTo-Json -Compress
} catch {
    [ordered]@{
        ok = $false
        reason = "set_value_failed"
        error_type = $_.Exception.GetType().Name
    } | ConvertTo-Json -Compress
}
'''


def _encoded_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def _parse_result(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {"ok": False, "reason": "empty_response"}
    line = next((candidate.strip() for candidate in reversed(text.splitlines()) if candidate.strip().startswith("{")), "")
    if not line:
        return {"ok": False, "reason": "invalid_response"}
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return {"ok": False, "reason": "invalid_json"}
    return payload if isinstance(payload, dict) else {"ok": False, "reason": "invalid_payload"}


def _validated_arguments(arguments: Mapping[str, Any]) -> tuple[str, str, int, int]:
    query = str(arguments.get("target_query") or "").strip()
    text = arguments.get("text")
    if not query:
        raise ValueError("target_query is required")
    if not isinstance(text, str) or not text:
        raise ValueError("literal text is required")
    if len(text) > 500:
        raise ValueError("A single text replacement is limited to 500 characters")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValueError("Control characters, Enter, Tab, and newlines are not allowed")
    try:
        expected_x = int(arguments.get("expected_x"))
        expected_y = int(arguments.get("expected_y"))
    except (TypeError, ValueError) as exc:
        raise ValueError("expected_x and expected_y are required physical screen coordinates") from exc
    return query, text, expected_x, expected_y


async def replace_text_value_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if platform.system() != "Windows":
        raise RuntimeError("Windows UI Automation text replacement is available only on Windows")
    query, text, expected_x, expected_y = _validated_arguments(arguments)

    env = os.environ.copy()
    env["SARAH_UIA_QUERY"] = query
    env["SARAH_UIA_TEXT"] = text
    env["SARAH_UIA_EXPECTED_X"] = str(expected_x)
    env["SARAH_UIA_EXPECTED_Y"] = str(expected_y)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            _encoded_powershell(_SET_VALUE_SCRIPT),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=env,
        creationflags=creationflags,
    )
    if completed.returncode != 0:
        raise RuntimeError("Windows UI Automation text replacement process failed")

    result = _parse_result(completed.stdout)
    if not result.get("ok"):
        reason = str(result.get("reason") or "unknown_failure")
        readable = {
            "not_found": "the revalidated text field was not found",
            "password_field": "the target is a password field",
            "value_pattern_unavailable": "the target does not expose a replaceable text value",
            "read_only": "the target is read-only",
            "set_value_failed": "Windows rejected replacement of the field value",
        }.get(reason, f"text replacement failed ({reason})")
        raise RuntimeError(readable)

    return {
        "action": "uia_text_replaced",
        "target_name": str(result.get("name") or query),
        "character_count": int(result.get("character_count") or len(text)),
        "special_keys": False,
        "clipboard_used": False,
        "replacement": True,
    }


def accessibility_text_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="replace_text_value",
            description=(
                "Internal Phase 5C tool. Replace the current value of one freshly revalidated Windows UI Automation "
                "text field with the exact confirmed literal text. No Enter, Tab, hotkeys, clipboard paste, or password fields."
            ),
            handler=replace_text_value_handler,
            parameters={
                "type": "object",
                "properties": {
                    "target_query": {"type": "string"},
                    "text": {"type": "string", "minLength": 1, "maxLength": 500},
                    "expected_x": {"type": "integer"},
                    "expected_y": {"type": "integer"},
                },
                "required": ["target_query", "text", "expected_x", "expected_y"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.SCREEN_TYPE}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
            model_visible=False,
        )
    ]
