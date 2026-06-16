"""SQLAlchemy ORM models for Adhkar IR."""

from adhkar.db.models.ai_call import AiCall
from adhkar.db.models.alert import Alert
from adhkar.db.models.analyzer_job import AnalyzerJob
from adhkar.db.models.api_key import ApiKey
from adhkar.db.models.attachment import Attachment, CaseShare
from adhkar.db.models.audit_log import AuditLog
from adhkar.db.models.case import Case
from adhkar.db.models.case_embedding import CaseEmbedding
from adhkar.db.models.case_link import CaseLink
from adhkar.db.models.case_page import CasePage
from adhkar.db.models.comment import Comment
from adhkar.db.models.kb import CaseTemplate, KnowledgeBasePage
from adhkar.db.models.membership import UserOrgMembership
from adhkar.db.models.mfa_secret import MfaSecret
from adhkar.db.models.notification import (
    NotificationDelivery,
    NotificationEndpoint,
    NotificationRule,
)
from adhkar.db.models.observable import Observable
from adhkar.db.models.org_sharing import OrgSharing
from adhkar.db.models.organization import Organization
from adhkar.db.models.outbox_event import OutboxEvent
from adhkar.db.models.profile import Profile
from adhkar.db.models.session import Session
from adhkar.db.models.task import Task, TaskLog
from adhkar.db.models.taxonomy import TaxonomyEntry
from adhkar.db.models.ttp import CaseTtp, TtpCatalogEntry
from adhkar.db.models.user import User

__all__ = [
    "AiCall",
    "Alert",
    "AnalyzerJob",
    "ApiKey",
    "Attachment",
    "AuditLog",
    "Case",
    "CaseEmbedding",
    "CaseLink",
    "CasePage",
    "CaseShare",
    "CaseTemplate",
    "CaseTtp",
    "Comment",
    "KnowledgeBasePage",
    "MfaSecret",
    "NotificationDelivery",
    "NotificationEndpoint",
    "NotificationRule",
    "Observable",
    "OrgSharing",
    "Organization",
    "OutboxEvent",
    "Profile",
    "Session",
    "Task",
    "TaskLog",
    "TaxonomyEntry",
    "TtpCatalogEntry",
    "User",
    "UserOrgMembership",
]
