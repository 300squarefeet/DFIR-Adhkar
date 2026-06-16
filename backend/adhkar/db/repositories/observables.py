"""Org-scoped repository for Observable."""

from adhkar.db.models import Observable
from adhkar.db.repositories.base import OrgScopedRepository


class ObservableRepository(OrgScopedRepository[Observable]):
    model = Observable
