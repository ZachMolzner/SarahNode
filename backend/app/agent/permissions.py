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
    # Start conservative: read-only information access only. Write/control scopes
    # are granted explicitly by the user or settings layer later.
    return PermissionPolicy(
        granted_scopes={
            PermissionScope.FILES_READ,
            PermissionScope.DESKTOP_READ,
            PermissionScope.WEB_READ,
            PermissionScope.SYSTEM_READ,
        }
    )
