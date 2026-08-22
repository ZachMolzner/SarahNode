from __future__ import annotations

from dataclasses import replace

from app.agent.app_lifecycle_tools import hardened_close_app_tool, hardened_terminate_app_tool
from app.agent.automation import AutomationRegistry
from app.agent.builtin_tools import builtin_tools
from app.agent.confirmed_action_tools import confirmed_action_tools
from app.agent.desktop_action_tools import desktop_action_tools
from app.agent.desktop_tools import desktop_read_tools
from app.agent.event_bus import EventBus
from app.agent.keyboard_tools import keyboard_tools
from app.agent.permissions import default_policy
from app.agent.pointer_tools import pointer_tools
from app.agent.screen_tools import screen_read_tools
from app.agent.tool_registry import ToolRegistry
from app.agent.web_launch_tools import safe_open_url_tool
from app.agent.windows_focus_tools import hardened_focus_app_tool


class SarahAgentRuntime:
    def __init__(self) -> None:
        self.permissions = default_policy()
        self.tools = ToolRegistry(self.permissions)
        self.tools.register_many(builtin_tools())
        self.tools.register_many(desktop_read_tools())
        self.tools.register_many(screen_read_tools())

        # Phase 4B low-risk actions can execute immediately when explicitly requested.
        action_tools = [
            replace(
                tool,
                description=(
                    "Use only when the user explicitly asks Sarah to perform this desktop action now. "
                    "Never use for hypothetical questions, instructions, or suggestions. "
                    + tool.description
                ),
            )
            for tool in desktop_action_tools()
            if tool.name not in {"open_url", "focus_app"}
        ]
        self.tools.register_many(action_tools)
        self.tools.register(hardened_focus_app_tool())
        self.tools.register(safe_open_url_tool())

        # Phase 4C/4D mutation and termination tools require confirmed=True at the
        # ToolRegistry boundary. Batch execution never bypasses this permission check.
        confirmed_tools = [
            tool
            for tool in confirmed_action_tools()
            if tool.name not in {"close_app", "terminate_app"}
        ]
        self.tools.register_many(confirmed_tools)
        self.tools.register(hardened_close_app_tool())
        self.tools.register(hardened_terminate_app_tool())

        # Phase 5C internal input tools remain invisible to both language models.
        # Pointer movement, bounded scrolling, and the five allowlisted navigation/edit
        # keys are LOW risk. Click, literal text typing, and Enter are separate MEDIUM
        # risk primitives and require confirmed=True at ToolRegistry boundary.
        self.tools.register_many(pointer_tools())
        self.tools.register_many(keyboard_tools())

        self.events = EventBus()
        self.automations = AutomationRegistry()

    def capabilities(self) -> dict[str, object]:
        return {
            "architecture_version": 12,
            "tool_count": len(self.tools.list_tools()),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "risk": tool.risk.value,
                    "scopes": sorted(scope.value for scope in tool.scopes),
                    "requires_confirmation": self.permissions.requires_confirmation(tool),
                }
                for tool in self.tools.list_tools()
            ],
            "granted_scopes": sorted(scope.value for scope in self.permissions.granted_scopes),
            "automation_count": len(self.automations.list()),
            "systems": {
                "memory": "persistent_learning_active",
                "model_gateway": "active",
                "tool_registry": "active",
                "permissions": "active",
                "event_bus": "ready",
                "automations": "scaffolded",
                "desktop_tools": "read_only_active",
                "file_search": "read_only_active",
                "safe_desktop_actions": "active",
                "app_launch": "allowlisted_active",
                "app_focus": "verified_foreground_active",
                "file_open": "safe_types_active",
                "url_launch": "http_https_active",
                "confirmed_file_create": "active",
                "confirmed_file_move_rename": "active",
                "confirmed_recycle_bin": "active",
                "confirmed_app_close": "verified_window_close_launch_aware",
                "confirmed_force_app_terminate": "high_risk_launch_aware",
                "multi_action_plans": "up_to_8_sequential_actions_active",
                "batch_confirmation": "single_confirmation_for_mutating_plan",
                "screen_metadata": "read_only_active",
                "screen_awareness": "explicit_ephemeral_local_vision_active",
                "screen_visual_reasoning": "describe_read_diagnose_locate_plan_active",
                "screen_target_localization": "windows_uia_first_vision_fallback_active",
                "screen_pointer_preview": "explicit_visual_target_active",
                "screen_click": "single_left_click_confirmed_revalidation_active",
                "screen_click_verification": "fresh_post_click_visual_check_active",
                "screen_keyboard": "literal_unicode_confirmed_plus_controlled_single_keys_active",
                "screen_enter": "confirmed_single_press_receiving_window_revalidation_active",
                "screen_safe_keys": "escape_tab_backspace_arrow_up_arrow_down_single_press_active",
                "screen_hotkeys": "not_available",
                "screen_key_modifiers": "not_available",
                "screen_sensitive_typing": "blocked",
                "screen_scroll": "bounded_vertical_wheel_active",
                "screen_drag_drop": "not_available",
                "screen_capture_persistence": "none",
                "permanent_delete": "not_available",
                "broad_desktop_control": "still_gated",
                "web_tools": "provider_dependent",
                "personal_services": "planned",
                "voice": "planned",
                "smart_home": "planned",
            },
        }


agent_runtime = SarahAgentRuntime()
