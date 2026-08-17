from __future__ import annotations

from dataclasses import dataclass, field

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition


class PermissionDenied(RuntimeError):
    pass


@dataclass(slots=True)
class PermissionPolicy:
    granted_scopes: set[PermissionScope] = field(default_factory=set)
    allow_low_risk_without_confirmation: bool = True

    def grant(self, *scopes: PermissionScope) -> None:
        self.granted_scopes.update(scopes)

    def revoke(self, *scopes: PermissionScope) -> None:
        for scope in scopes:
            self.granted_scopes.discard(scope)

    def missing_scopes(self, tool: ToolDefinition) -> set[PermissionScope]:
        return set(tool.scopes) - self.granted_scopes

    def requires_confirmation(self, tool: ToolDefinition) -> bool:
        if tool.requires_confirmation:
            return True
        if tool.risk in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
            return True
        if tool.risk is RiskLevel.LOW:
            return not self.allow_low_risk_without_confirmation
        return False

    def authorize(self, tool: ToolDefinition, *, confirmed: bool = False) -> None:
        missing = self.missing_scopes(tool)
        if missing:
            readable = ", ".join(sorted(scope.value for scope in missing))
            raise PermissionDenied(f"Missing permission scope(s): {readable}")
        if self.requires_confirmation(tool) and not confirmed:
            raise PermissionDenied(f"Tool '{tool.name}' requires user confirmation")


def default_policy() -> PermissionPolicy:
    # Local-first defaults allow read-only inspection (including explicit screen
    # inspection), Sarah's persistent memory, low-risk launch/pointer actions, and
    # deliberately narrow confirmed mutation/click scopes. screen.click is granted
    # but its tool is MEDIUM risk and explicitly requires confirmed=True. Broad
    # files.write, desktop.control, and system.control remain ungranted.
    return PermissionPolicy(
        granted_scopes={
            PermissionScope.FILES_READ,
            PermissionScope.FILES_OPEN,
            PermissionScope.FILES_CREATE,
            PermissionScope.FILES_MOVE,
            PermissionScope.FILES_RECYCLE,
            PermissionScope.DESKTOP_READ,
            PermissionScope.SCREEN_READ,
            PermissionScope.SCREEN_POINTER,
            PermissionScope.SCREEN_CLICK,
            PermissionScope.APPS_LAUNCH,
            PermissionScope.APPS_FOCUS,
            PermissionScope.APPS_CLOSE,
            PermissionScope.APPS_TERMINATE,
            PermissionScope.WEB_READ,
            PermissionScope.WEB_LAUNCH,
            PermissionScope.SYSTEM_READ,
            PermissionScope.MEMORY_READ,
            PermissionScope.MEMORY_WRITE,
        }
    )
