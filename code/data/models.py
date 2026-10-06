"""
Data models for the WhatsApp Notification Router.

All domain objects are defined here as dataclasses for clarity,
immutability where appropriate, and type safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Action(str, Enum):
    """Routing action for a message."""
    NOTIFY = "notify"
    DIGEST = "digest"
    MUTE = "mute"


class MessageType(str, Enum):
    """Allowed message type classifications."""
    PERSONAL = "personal"
    URGENT = "urgent"
    EVENT = "event"
    PAYMENT = "payment"
    BUSINESS_UPDATE = "business_update"
    PROMOTION = "promotion"
    GREETING = "greeting"
    FORWARD = "forward"
    SPAM = "spam"
    SCAM = "scam"
    UNKNOWN = "unknown"


class ConversationType(str, Enum):
    """Type of WhatsApp conversation."""
    PERSONAL = "personal"
    GROUP = "group"
    BUSINESS = "business"


class MediaType(str, Enum):
    """Type of media attached to a message."""
    IMAGE = "image"
    VOICE = "voice"
    NONE = ""


# ---------------------------------------------------------------------------
# Input Data Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Message:
    """A single incoming message to be routed."""
    message_id: str
    user_id: str
    conversation_type: ConversationType
    group_id: Optional[str]
    business_id: Optional[str]
    sender_user_id: Optional[str]
    created_at: str
    message_text: str
    media_type: Optional[MediaType]
    media_id: Optional[str]
    forwarded_count: int


@dataclass(frozen=True)
class SampleMessage:
    """A solved sample message with expected output (for evaluation)."""
    message_id: str
    user_id: str
    conversation_type: ConversationType
    group_id: Optional[str]
    business_id: Optional[str]
    sender_user_id: Optional[str]
    created_at: str
    message_text: str
    media_type: Optional[MediaType]
    media_id: Optional[str]
    forwarded_count: int
    # Expected output fields
    action: Action
    message_type: MessageType
    reason: str
    confidence: float
    evidence_message_ids: str


@dataclass(frozen=True)
class User:
    """User notification preferences and behavior."""
    user_id: str
    do_not_disturb_window: str  # e.g. "22:00-07:00"
    messages_opened_30d: int
    messages_replied_30d: int
    notifications_dismissed_30d: int
    messages_reported_30d: int


@dataclass(frozen=True)
class Group:
    """WhatsApp group metadata."""
    group_id: str
    group_name: str
    group_type: str
    member_count: int
    admin_count: int
    created_at: str
    messages_30d: int


@dataclass(frozen=True)
class GroupMembership:
    """User-group relationship and engagement."""
    group_id: str
    user_id: str
    role: str  # "admin" or "member"
    joined_at: str
    messages_sent_30d: int
    messages_read_30d: int
    replies_sent_30d: int
    notifications_dismissed_30d: int
    group_muted_by_user: bool


@dataclass(frozen=True)
class BusinessAccount:
    """Business sender profile."""
    business_id: str
    display_name: str
    brand_name: str
    category: str
    verified: bool
    official_domain: str
    domain_used_by_sender: str
    account_age_days: int
    messages_sent_30d: int
    user_reports_30d: int
    domain_used_by_sender_age_days: int


@dataclass(frozen=True)
class UserBusinessHistory:
    """User's relationship with a business account."""
    user_id: str
    business_id: str
    why_user_knows_account: str
    last_activity_at: str
    allows_promotions: bool
    promotions_opted_out_at: Optional[str]
    activity_count_180d: int
    messages_opened_30d: int
    messages_dismissed_30d: int
    messages_replied_30d: int
    last_reply_at: Optional[str]


@dataclass(frozen=True)
class HistoricalMessage:
    """A past message from message_history.csv."""
    message_id: str
    user_id: str
    conversation_type: ConversationType
    group_id: Optional[str]
    business_id: Optional[str]
    sender_user_id: Optional[str]
    created_at: str
    message_text: str
    media_type: Optional[MediaType]
    media_id: Optional[str]
    forwarded_count: int


@dataclass(frozen=True)
class MessageEvent:
    """User reaction to a historical message."""
    user_id: str
    message_id: str
    message_opened: bool
    message_replied: bool
    reaction_time_minutes: Optional[float]
    notification_dismissed: bool
    muted_after_message: bool
    message_reported: bool


@dataclass(frozen=True)
class DailyNotificationSummary:
    """Daily notification load for a user."""
    user_id: str
    date: str
    notifications_sent: int
    notifications_dismissed: int


@dataclass(frozen=True)
class ImageReference:
    """Image ID to file path mapping."""
    image_id: str
    file_path: str


@dataclass(frozen=True)
class VoiceNoteReference:
    """Voice note ID to file path mapping."""
    voice_note_id: str
    file_path: str


# ---------------------------------------------------------------------------
# Computed / Enriched Models
# ---------------------------------------------------------------------------

@dataclass
class MediaAnalysis:
    """Result of analyzing an image or voice note."""
    media_id: str
    media_type: str  # "image" or "voice"
    extracted_text: str = ""
    summary: str = ""
    detected_type: str = ""  # poster, screenshot, receipt, scam_qr, etc.
    entities: dict = field(default_factory=dict)
    urgency: str = "low"  # low, medium, high
    is_suspicious: bool = False
    raw_transcript: str = ""  # for voice notes
    language: str = "en"
    error: Optional[str] = None


@dataclass
class TrustScore:
    """Sender trust assessment."""
    score: float = 50.0  # 0-100
    reason: str = ""
    confidence: float = 0.5
    factors: dict = field(default_factory=dict)


@dataclass
class RiskScore:
    """Message safety/risk assessment."""
    score: float = 0.0  # 0-100 (higher = more risky)
    reason: str = ""
    confidence: float = 0.5
    flags: list = field(default_factory=list)
    is_prompt_injection: bool = False


@dataclass
class PersonalizationScore:
    """User-specific relevance score."""
    score: float = 50.0  # 0-100
    reason: str = ""
    engagement_likelihood: float = 0.5
    factors: dict = field(default_factory=dict)


@dataclass
class GroupContext:
    """Enriched group context for a message."""
    group: Optional[Group] = None
    membership: Optional[GroupMembership] = None
    sender_is_admin: bool = False
    is_direct_mention: bool = False
    group_importance: str = "medium"  # low, medium, high
    message_significance: str = "normal"  # normal, announcement, urgent


@dataclass
class BusinessContext:
    """Enriched business context for a message."""
    business: Optional[BusinessAccount] = None
    user_history: Optional[UserBusinessHistory] = None
    is_verified: bool = False
    is_domain_legitimate: bool = True
    business_category: str = ""
    message_category: str = ""  # transactional, marketing, authentication


@dataclass
class EvidenceMessage:
    """A historical message used as evidence for the routing decision."""
    message_id: str
    relevance: str = ""
    event: Optional[MessageEvent] = None


@dataclass
class UnifiedMessage:
    """
    The fully enriched message object passed to the reasoning engine.
    Single source of truth for all context about an incoming message.
    """
    # Core message
    message: Message = field(default_factory=lambda: None)  # type: ignore
    
    # User context
    user: Optional[User] = None
    daily_notification_load: list = field(default_factory=list)
    
    # Sender context
    sender: Optional[User] = None
    
    # Conversation context
    group_context: Optional[GroupContext] = None
    business_context: Optional[BusinessContext] = None
    
    # Media analysis
    media_analysis: Optional[MediaAnalysis] = None
    
    # Computed scores
    trust_score: Optional[TrustScore] = None
    risk_score: Optional[RiskScore] = None
    personalization_score: Optional[PersonalizationScore] = None
    
    # Evidence
    evidence_messages: list = field(default_factory=list)
    
    # Derived flags
    is_during_dnd: bool = False
    sender_is_known: bool = False
    ds: Any = None


# ---------------------------------------------------------------------------
# Output Models
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    """Final routing decision for a message."""
    message_id: str
    action: Action
    message_type: MessageType
    reason: str
    confidence: float
    evidence_message_ids: str  # semicolon-separated or "none"
    
    # Internal metadata (not written to output.csv)
    importance: int = 5
    urgency: int = 5
    risk: int = 0
    llm_raw_output: str = ""
    execution_time_ms: float = 0.0
