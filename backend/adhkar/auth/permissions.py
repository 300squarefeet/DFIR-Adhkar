"""Frozen permission catalog + default profiles (RBAC seed data)."""

from typing import Final

# All permission keys recognized in Adhkar IR. New permissions are added in
# code releases; the profile editor only allows subset selection.
PERMISSION_CATALOG: Final[frozenset[str]] = frozenset(
    {
        "manageOrganization",
        "manageUser",
        "manageProfile",
        "manageApiKey",
        "viewAudit",
        "manageCase",
        "viewCase",
        "manageAlert",
        "viewAlert",
        "manageObservable",
        "viewObservable",
        "manageTask",
        "viewTask",
        "manageConfig",
    }
)


def validate_permissions(perms: list[str]) -> list[str]:
    """Reject unknown permissions; return sorted unique list."""
    unknown = [p for p in perms if p not in PERMISSION_CATALOG]
    if unknown:
        raise ValueError(f"unknown permissions: {unknown}")
    return sorted(set(perms))


# Default profile names + their permission sets, seeded per organization on create.
DEFAULT_PROFILES: Final[dict[str, frozenset[str]]] = {
    "org-admin": PERMISSION_CATALOG,
    "analyst": frozenset(
        {
            "manageCase",
            "viewCase",
            "manageAlert",
            "viewAlert",
            "manageObservable",
            "viewObservable",
            "manageTask",
            "viewTask",
            "viewAudit",
        }
    ),
    "read-only": frozenset(
        {
            "viewCase",
            "viewAlert",
            "viewObservable",
            "viewTask",
        }
    ),
    "portal-user": frozenset(),  # populated in Phase 9
}
