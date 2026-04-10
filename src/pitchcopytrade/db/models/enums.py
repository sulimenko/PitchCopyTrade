from enum import Enum

from sqlalchemy import Enum as SqlEnum


class RoleSlug(str, Enum):
    ADMIN = "admin"
    AUTHOR = "author"
    MODERATOR = "moderator"


class UserStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    INACTIVE = "inactive"


class InviteDeliveryStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"
    RESENT = "resent"


class LeadSourceType(str, Enum):
    ADS = "ads"
    BLOGGER = "blogger"
    ORGANIC = "organic"
    DIRECT = "direct"
    REFERRAL = "referral"


class StrategyStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProductType(str, Enum):
    STRATEGY = "strategy"
    AUTHOR = "author"
    BUNDLE = "bundle"


class PaymentProvider(str, Enum):
    STUB_MANUAL = "stub_manual"
    TBANK = "tbank"


class PaymentStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class SubscriptionStatus(str, Enum):
    PENDING = "pending"
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class MessageKind(str, Enum):
    IDEA = "idea"
    UPDATE = "update"
    CLOSE = "close"
    CANCEL = "cancel"
    NOTE = "note"


class MessageType(str, Enum):
    TEXT = "text"
    DOCUMENT = "document"
    DEAL = "deal"
    MIXED = "mixed"


class MessageStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"


class MessageModeration(str, Enum):
    REQUIRED = "required"
    DIRECT = "direct"


class MessageDeliver(str, Enum):
    STRATEGY = "strategy"
    AUTHOR = "author"
    BUNDLE = "bundle"


class MessageChannel(str, Enum):
    TELEGRAM = "telegram"
    MINIAPP = "miniapp"
    WEB = "web"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class LegalDocumentType(str, Enum):
    DISCLAIMER = "disclaimer"
    OFFER = "offer"
    PRIVACY_POLICY = "privacy_policy"
    PAYMENT_CONSENT = "payment_consent"


class InstrumentType(str, Enum):
    EQUITY = "equity"


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [str(item.value) for item in enum_cls]


def sql_enum(enum_cls: type[Enum], *, name: str) -> SqlEnum:
    return SqlEnum(
        enum_cls,
        name=name,
        values_callable=enum_values,
    )
