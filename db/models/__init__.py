"""
Import every model here so Alembic autogenerate sees them all.
"""

from db.base import Base
from db.models.alert import Alert, AlertSeverity
from db.models.artifact import NarrativeArtifact
from db.models.audit_log import AuditAction, AuditLog
from db.models.contract import Contract, SubstitutabilityRating
from db.models.correction import Correction, CorrectionReason
from db.models.excerpt import Excerpt
from db.models.org import Org, OrgRole, OrgVendorAccess, User
from db.models.score import ConfidenceTier, DimensionScore, VendorScore
from db.models.signal import Signal, SignalMetric
from db.models.vendor import EntityType, Vendor
from db.integrity.crypto_shred import ShreddedField, SubjectKey

__all__ = [
    "Base",
    "Vendor",
    "EntityType",
    "Signal",
    "SignalMetric",
    "Excerpt",
    "VendorScore",
    "DimensionScore",
    "ConfidenceTier",
    "Alert",
    "AlertSeverity",
    "NarrativeArtifact",
    "Contract",
    "SubstitutabilityRating",
    "Correction",
    "CorrectionReason",
    "AuditLog",
    "AuditAction",
    "Org",
    "OrgRole",
    "OrgVendorAccess",
    "User",
    "SubjectKey",
    "ShreddedField",
]
from db.models.api_key import (
    
    ApiCostEvent,
    ApiKey,
    ApiKeyScope,
    ErasureRequest,
    ErasureStatus,
)