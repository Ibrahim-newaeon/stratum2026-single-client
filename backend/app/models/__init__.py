# =============================================================================
# Stratum AI - Models Package
# =============================================================================
# Re-exports all models for backwards compatibility

# Base models (formerly models.py)
from app.base_models import (  # Enums; Models
    AdPlatform,
    APIKey,
    AssetType,
    AuditAction,
    AuditLog,
    Campaign,
    CampaignMetric,
    CampaignStatus,
    CompetitorBenchmark,
    CreativeAsset,
    MLPrediction,
    NotificationPreference,
    Organization,
    Rule,
    RuleAction,
    RuleExecution,
    RuleOperator,
    RuleStatus,
    User,
    UserRole,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppMessageDirection,
    WhatsAppMessageStatus,
    WhatsAppOptInStatus,
    WhatsAppTemplate,
    WhatsAppTemplateCategory,
    WhatsAppTemplateStatus,
)

# Multi-Touch Attribution models
from app.models.attribution import (
    AttributionSnapshot,
    ChannelInteraction,
    ConversionPath,
    DailyAttributedRevenue,
    DataDrivenModelType,
    ModelStatus,
    ModelTrainingRun,
    TrainedAttributionModel,
)

# Autopilot Enforcement models
from app.models.autopilot import (
    EnforcementAuditLog,
)
from app.models.autopilot import EnforcementMode as AutopilotEnforcementMode
from app.models.autopilot import (
    EnforcementRule,
    EnforcementSettings,
)
from app.models.autopilot import InterventionAction as AutopilotInterventionAction
from app.models.autopilot import (
    PendingConfirmationToken,
)
from app.models.autopilot import ViolationType as AutopilotViolationType

# Campaign Builder models
from app.models.campaign_builder import (
    AdAccount,
    CampaignDraft,
    CampaignPublishLog,
    ConnectionStatus,
    DraftStatus,
    PlatformConnection,
    PublishResult,
)

# Client (Agency → Brand) models
from app.models.client import (
    Client,
    ClientAssignment,
    ClientRequest,
    ClientRequestStatus,
    ClientRequestType,
)
from app.models.copilot_doc import CopilotDocChunk

# CRM Integration models
from app.models.crm import (
    AttributionModel,
    CRMConnection,
    CRMConnectionStatus,
    CRMContact,
    CRMDeal,
    CRMProvider,
    CRMWritebackConfig,
    CRMWritebackSync,
    DailyPipelineMetrics,
    DealStage,
    Touchpoint,
    WritebackStatus,
)

# Drip campaign models
from app.models.drip import DripExecutionRecord, DripSequence

# EMQ fix-playbook progress
from app.models.emq_playbook import EmqPlaybookItemState

# Launch Readiness (Go-Live wizard)
from app.models.launch_readiness import LaunchReadinessEvent, LaunchReadinessItemState

# Onboarding models
from app.models.onboarding import OrganizationOnboarding

# Pacing & Forecasting models
from app.models.pacing import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    DailyKPI,
    Forecast,
    PacingAlert,
    PacingSummary,
    Target,
    TargetMetric,
    TargetPeriod,
)

# Profit ROAS models
from app.models.profit import (
    COGSSource,
    COGSUpload,
    DailyProfitMetrics,
    MarginRule,
    MarginType,
    ProductCatalog,
    ProductMargin,
    ProductStatus,
    ProfitROASReport,
)

# Push notification models
from app.models.push import PushNotificationLog, PushSubscription

# Automated Reporting models
from app.models.reporting import (
    DeliveryChannel,
    DeliveryChannelConfig,
    DeliveryStatus,
    ExecutionStatus,
    ReportDelivery,
    ReportExecution,
    ReportFormat,
    ReportTemplate,
    ReportType,
    ScheduledReport,
    ScheduleFrequency,
)

# Trust Layer models
from app.models.trust_layer import (
    AttributionVarianceStatus,
    FactActionsQueue,
    FactAttributionVarianceDaily,
    FactSignalHealthDaily,
    SignalHealthStatus,
)

# -----------------------------------------------------------------------------
# Module registrations (no re-exports).
# These imports exist so every model module is registered with Base.metadata
# when `app.models` is imported — migrations/env.py relies on this for
# Alembic autogenerate to see the full schema (issue #343 drift catch-up).
# -----------------------------------------------------------------------------
from app.models import (  # noqa: F401  isort: skip
    audience_sync,
    audit_services,
    capi_delivery,
    cdp,
    cms,
    embed_widgets,
    newsletter,
    onboarding,
    settings,
)

__all__ = [
    "APIKey",
    "AdAccount",
    "AdPlatform",
    "AlertSeverity",
    "AlertStatus",
    "AlertType",
    "AssetType",
    "AttributionModel",
    "AttributionSnapshot",
    "AttributionVarianceStatus",
    "AuditAction",
    "AuditLog",
    # Autopilot Enforcement
    "AutopilotEnforcementMode",
    "AutopilotInterventionAction",
    "AutopilotViolationType",
    "COGSSource",
    "COGSUpload",
    "CRMConnection",
    "CRMConnectionStatus",
    "CRMContact",
    "CRMDeal",
    # CRM Integration
    "CRMProvider",
    "CRMWritebackConfig",
    "CRMWritebackSync",
    "Campaign",
    "CampaignDraft",
    "CampaignMetric",
    "CampaignPublishLog",
    "CampaignStatus",
    "ChannelInteraction",
    "Client",
    "ClientAssignment",
    "ClientRequest",
    # Client (Agency → Brand)
    "ClientRequestStatus",
    "ClientRequestType",
    "CompetitorBenchmark",
    "ConnectionStatus",
    "ConversionPath",
    "CopilotDocChunk",
    "CreativeAsset",
    # Multi-Touch Attribution
    "DailyAttributedRevenue",
    "DailyKPI",
    "DailyPipelineMetrics",
    "DailyProfitMetrics",
    # Data-Driven Attribution
    "DataDrivenModelType",
    "DealStage",
    "DeliveryChannel",
    "DeliveryChannelConfig",
    "DeliveryStatus",
    "DraftStatus",
    "DripExecutionRecord",
    "DripSequence",
    "EmqPlaybookItemState",
    "EnforcementAuditLog",
    # Models
    "EnforcementRule",
    "EnforcementSettings",
    "ExecutionStatus",
    "FactActionsQueue",
    "FactAttributionVarianceDaily",
    "FactSignalHealthDaily",
    "Forecast",
    # Launch Readiness (Go-Live wizard)
    "LaunchReadinessEvent",
    "LaunchReadinessItemState",
    "MLPrediction",
    "MarginRule",
    # Profit ROAS
    "MarginType",
    "ModelStatus",
    "ModelTrainingRun",
    "NotificationPreference",
    "Organization",
    "OrganizationOnboarding",
    "PacingAlert",
    "PacingSummary",
    "PendingConfirmationToken",
    "PlatformConnection",
    "ProductCatalog",
    "ProductMargin",
    "ProductStatus",
    "ProfitROASReport",
    "PublishResult",
    "PushNotificationLog",
    "PushSubscription",
    "ReportDelivery",
    "ReportExecution",
    "ReportFormat",
    "ReportTemplate",
    # Automated Reporting
    "ReportType",
    "Rule",
    "RuleAction",
    "RuleExecution",
    "RuleOperator",
    "RuleStatus",
    "ScheduleFrequency",
    "ScheduledReport",
    "SignalHealthStatus",
    "Target",
    "TargetMetric",
    # Pacing & Forecasting
    "TargetPeriod",
    "Touchpoint",
    "TrainedAttributionModel",
    "User",
    # Enums
    "UserRole",
    "WhatsAppContact",
    "WhatsAppConversation",
    "WhatsAppMessage",
    "WhatsAppMessageDirection",
    "WhatsAppMessageStatus",
    "WhatsAppOptInStatus",
    "WhatsAppTemplate",
    "WhatsAppTemplateCategory",
    "WhatsAppTemplateStatus",
    "WritebackStatus",
]
