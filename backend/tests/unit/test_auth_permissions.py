import pytest
from adhkar.auth.permissions import (
    DEFAULT_PROFILES,
    PERMISSION_CATALOG,
    validate_permissions,
)


def test_catalog_size_locked():
    assert len(PERMISSION_CATALOG) == 14


def test_catalog_immutable():
    # frozenset is hashable; cannot add via union without copying
    with pytest.raises(AttributeError):
        PERMISSION_CATALOG.add("anyNewPermission")  # type: ignore[attr-defined]


def test_default_profiles_present():
    assert set(DEFAULT_PROFILES.keys()) == {"org-admin", "analyst", "read-only", "portal-user"}


def test_org_admin_has_all_permissions():
    assert DEFAULT_PROFILES["org-admin"] == PERMISSION_CATALOG


def test_analyst_subset_of_catalog():
    assert DEFAULT_PROFILES["analyst"].issubset(PERMISSION_CATALOG)


def test_read_only_view_only():
    for p in DEFAULT_PROFILES["read-only"]:
        assert p.startswith("view")


def test_validate_permissions_accepts_known():
    out = validate_permissions(["manageUser", "viewAudit", "manageUser"])
    assert out == ["manageUser", "viewAudit"]  # dedup + sort


def test_validate_permissions_rejects_unknown():
    with pytest.raises(ValueError) as exc:
        validate_permissions(["manageUser", "noSuchPermission"])
    assert "noSuchPermission" in str(exc.value)
