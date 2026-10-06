"""
Data loader and indexer for the WhatsApp Notification Router.

Loads all CSV datasets from the dataset/ folder, parses them into typed dataclasses,
and creates high-performance lookup indexes for fast contextual queries.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from data.models import (
    Action,
    BusinessAccount,
    ConversationType,
    DailyNotificationSummary,
    Group,
    GroupMembership,
    HistoricalMessage,
    ImageReference,
    MediaType,
    Message,
    MessageEvent,
    MessageType,
    SampleMessage,
    User,
    UserBusinessHistory,
    VoiceNoteReference,
)


def _safe_int(val: str, default: int = 0) -> int:
    val = (val or "").strip()
    if not val:
        return default
    try:
        return int(float(val))
    except ValueError:
        return default


def _safe_float(val: str, default: Optional[float] = None) -> Optional[float]:
    val = (val or "").strip()
    if not val:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _safe_bool(val: str) -> bool:
    val = (val or "").strip().lower()
    return val in ("1", "true", "yes", "t")


def _safe_opt_str(val: str) -> Optional[str]:
    val = (val or "").strip()
    return val if val else None


def _parse_conversation_type(val: str) -> ConversationType:
    val = (val or "").strip().lower()
    try:
        return ConversationType(val)
    except ValueError:
        return ConversationType.PERSONAL


def _parse_media_type(val: str) -> Optional[MediaType]:
    val = (val or "").strip().lower()
    if not val:
        return None
    try:
        return MediaType(val)
    except ValueError:
        return None


@dataclass
class DataStore:
    """Indexed container for all loaded dataset files."""
    dataset_dir: Path
    
    messages: List[Message] = field(default_factory=list)
    sample_messages: List[SampleMessage] = field(default_factory=list)
    users: Dict[str, User] = field(default_factory=dict)
    groups: Dict[str, Group] = field(default_factory=dict)
    group_members: Dict[Tuple[str, str], GroupMembership] = field(default_factory=dict)  # (group_id, user_id)
    group_members_by_group: Dict[str, List[GroupMembership]] = field(default_factory=dict)
    group_members_by_user: Dict[str, List[GroupMembership]] = field(default_factory=dict)
    business_accounts: Dict[str, BusinessAccount] = field(default_factory=dict)
    user_business_history: Dict[Tuple[str, str], UserBusinessHistory] = field(default_factory=dict)  # (user_id, biz_id)
    message_history: List[HistoricalMessage] = field(default_factory=list)
    message_history_by_user: Dict[str, List[HistoricalMessage]] = field(default_factory=dict)
    message_history_by_id: Dict[str, HistoricalMessage] = field(default_factory=dict)
    message_events: List[MessageEvent] = field(default_factory=list)
    message_events_by_key: Dict[Tuple[str, str], MessageEvent] = field(default_factory=dict)  # (user_id, msg_id)
    message_events_by_msg_id: Dict[str, List[MessageEvent]] = field(default_factory=dict)
    images: Dict[str, ImageReference] = field(default_factory=dict)
    voice_notes: Dict[str, VoiceNoteReference] = field(default_factory=dict)
    daily_summaries_by_user: Dict[str, List[DailyNotificationSummary]] = field(default_factory=dict)

    def get_user(self, user_id: Optional[str]) -> Optional[User]:
        return self.users.get(user_id) if user_id else None

    def get_group(self, group_id: Optional[str]) -> Optional[Group]:
        return self.groups.get(group_id) if group_id else None

    def get_membership(self, group_id: Optional[str], user_id: Optional[str]) -> Optional[GroupMembership]:
        if not group_id or not user_id:
            return None
        return self.group_members.get((group_id, user_id))

    def get_business(self, business_id: Optional[str]) -> Optional[BusinessAccount]:
        return self.business_accounts.get(business_id) if business_id else None

    def get_user_business_history(self, user_id: Optional[str], business_id: Optional[str]) -> Optional[UserBusinessHistory]:
        if not user_id or not business_id:
            return None
        return self.user_business_history.get((user_id, business_id))

    def get_media_path(self, media_type: Optional[MediaType], media_id: Optional[str]) -> Optional[Path]:
        if not media_id:
            return None
        if media_type == MediaType.IMAGE and media_id in self.images:
            return self.dataset_dir / self.images[media_id].file_path
        if media_type == MediaType.VOICE and media_id in self.voice_notes:
            return self.dataset_dir / self.voice_notes[media_id].file_path
        return None

    def get_historical_messages_for_user(self, user_id: str) -> List[HistoricalMessage]:
        return self.message_history_by_user.get(user_id, [])

    def get_event_for_message(self, user_id: str, message_id: str) -> Optional[MessageEvent]:
        return self.message_events_by_key.get((user_id, message_id))


class DataLoader:
    """Loads CSV files from the specified dataset directory into a DataStore."""

    def __init__(self, dataset_dir: str | Path):
        self.dataset_dir = Path(dataset_dir).resolve()

    def load_all(self) -> DataStore:
        ds = DataStore(dataset_dir=self.dataset_dir)
        self._load_users(ds)
        self._load_groups(ds)
        self._load_group_members(ds)
        self._load_business_accounts(ds)
        self._load_user_business_history(ds)
        self._load_message_history(ds)
        self._load_message_events(ds)
        self._load_images(ds)
        self._load_voice_notes(ds)
        self._load_daily_summaries(ds)
        self._load_messages(ds)
        self._load_sample_messages(ds)
        return ds

    def _read_csv(self, filename: str) -> List[Dict[str, str]]:
        file_path = self.dataset_dir / filename
        if not file_path.exists():
            return []
        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return [row for row in reader]

    def _load_messages(self, ds: DataStore) -> None:
        rows = self._read_csv("messages.csv")
        for r in rows:
            msg = Message(
                message_id=r["message_id"].strip(),
                user_id=r["user_id"].strip(),
                conversation_type=_parse_conversation_type(r.get("conversation_type", "")),
                group_id=_safe_opt_str(r.get("group_id", "")),
                business_id=_safe_opt_str(r.get("business_id", "")),
                sender_user_id=_safe_opt_str(r.get("sender_user_id", "")),
                created_at=r.get("created_at", "").strip(),
                message_text=r.get("message_text", "").strip(),
                media_type=_parse_media_type(r.get("media_type", "")),
                media_id=_safe_opt_str(r.get("media_id", "")),
                forwarded_count=_safe_int(r.get("forwarded_count", "0")),
            )
            ds.messages.append(msg)

    def _load_sample_messages(self, ds: DataStore) -> None:
        rows = self._read_csv("sample_messages.csv")
        for r in rows:
            try:
                act = Action(r.get("action", "mute").strip().lower())
            except ValueError:
                act = Action.MUTE
            try:
                mtype = MessageType(r.get("message_type", "unknown").strip().lower())
            except ValueError:
                mtype = MessageType.UNKNOWN

            msg = SampleMessage(
                message_id=r["message_id"].strip(),
                user_id=r["user_id"].strip(),
                conversation_type=_parse_conversation_type(r.get("conversation_type", "")),
                group_id=_safe_opt_str(r.get("group_id", "")),
                business_id=_safe_opt_str(r.get("business_id", "")),
                sender_user_id=_safe_opt_str(r.get("sender_user_id", "")),
                created_at=r.get("created_at", "").strip(),
                message_text=r.get("message_text", "").strip(),
                media_type=_parse_media_type(r.get("media_type", "")),
                media_id=_safe_opt_str(r.get("media_id", "")),
                forwarded_count=_safe_int(r.get("forwarded_count", "0")),
                action=act,
                message_type=mtype,
                reason=r.get("reason", "").strip(),
                confidence=_safe_float(r.get("confidence", "0.5"), 0.5) or 0.5,
                evidence_message_ids=r.get("evidence_message_ids", "none").strip(),
            )
            ds.sample_messages.append(msg)

    def _load_users(self, ds: DataStore) -> None:
        rows = self._read_csv("users.csv")
        for r in rows:
            u = User(
                user_id=r["user_id"].strip(),
                do_not_disturb_window=r.get("do_not_disturb_window", "").strip(),
                messages_opened_30d=_safe_int(r.get("messages_opened_30d", "0")),
                messages_replied_30d=_safe_int(r.get("messages_replied_30d", "0")),
                notifications_dismissed_30d=_safe_int(r.get("notifications_dismissed_30d", "0")),
                messages_reported_30d=_safe_int(r.get("messages_reported_30d", "0")),
            )
            ds.users[u.user_id] = u

    def _load_groups(self, ds: DataStore) -> None:
        rows = self._read_csv("groups.csv")
        for r in rows:
            g = Group(
                group_id=r["group_id"].strip(),
                group_name=r.get("group_name", "").strip(),
                group_type=r.get("group_type", "").strip(),
                member_count=_safe_int(r.get("member_count", "0")),
                admin_count=_safe_int(r.get("admin_count", "0")),
                created_at=r.get("created_at", "").strip(),
                messages_30d=_safe_int(r.get("messages_30d", "0")),
            )
            ds.groups[g.group_id] = g

    def _load_group_members(self, ds: DataStore) -> None:
        rows = self._read_csv("group_members.csv")
        for r in rows:
            gm = GroupMembership(
                group_id=r["group_id"].strip(),
                user_id=r["user_id"].strip(),
                role=r.get("role", "member").strip(),
                joined_at=r.get("joined_at", "").strip(),
                messages_sent_30d=_safe_int(r.get("messages_sent_30d", "0")),
                messages_read_30d=_safe_int(r.get("messages_read_30d", "0")),
                replies_sent_30d=_safe_int(r.get("replies_sent_30d", "0")),
                notifications_dismissed_30d=_safe_int(r.get("notifications_dismissed_30d", "0")),
                group_muted_by_user=_safe_bool(r.get("group_muted_by_user", "0")),
            )
            key = (gm.group_id, gm.user_id)
            ds.group_members[key] = gm
            ds.group_members_by_group.setdefault(gm.group_id, []).append(gm)
            ds.group_members_by_user.setdefault(gm.user_id, []).append(gm)

    def _load_business_accounts(self, ds: DataStore) -> None:
        rows = self._read_csv("business_accounts.csv")
        for r in rows:
            b = BusinessAccount(
                business_id=r["business_id"].strip(),
                display_name=r.get("display_name", "").strip(),
                brand_name=r.get("brand_name", "").strip(),
                category=r.get("category", "").strip(),
                verified=_safe_bool(r.get("verified", "0")),
                official_domain=r.get("official_domain", "").strip(),
                domain_used_by_sender=r.get("domain_used_by_sender", "").strip(),
                account_age_days=_safe_int(r.get("account_age_days", "0")),
                messages_sent_30d=_safe_int(r.get("messages_sent_30d", "0")),
                user_reports_30d=_safe_int(r.get("user_reports_30d", "0")),
                domain_used_by_sender_age_days=_safe_int(r.get("domain_used_by_sender_age_days", "0")),
            )
            ds.business_accounts[b.business_id] = b

    def _load_user_business_history(self, ds: DataStore) -> None:
        rows = self._read_csv("user_business_history.csv")
        for r in rows:
            ubh = UserBusinessHistory(
                user_id=r["user_id"].strip(),
                business_id=r["business_id"].strip(),
                why_user_knows_account=r.get("why_user_knows_account", "").strip(),
                last_activity_at=r.get("last_activity_at", "").strip(),
                allows_promotions=_safe_bool(r.get("allows_promotions", "0")),
                promotions_opted_out_at=_safe_opt_str(r.get("promotions_opted_out_at", "")),
                activity_count_180d=_safe_int(r.get("activity_count_180d", "0")),
                messages_opened_30d=_safe_int(r.get("messages_opened_30d", "0")),
                messages_dismissed_30d=_safe_int(r.get("messages_dismissed_30d", "0")),
                messages_replied_30d=_safe_int(r.get("messages_replied_30d", "0")),
                last_reply_at=_safe_opt_str(r.get("last_reply_at", "")),
            )
            ds.user_business_history[(ubh.user_id, ubh.business_id)] = ubh

    def _load_message_history(self, ds: DataStore) -> None:
        rows = self._read_csv("message_history.csv")
        for r in rows:
            hm = HistoricalMessage(
                message_id=r["message_id"].strip(),
                user_id=r["user_id"].strip(),
                conversation_type=_parse_conversation_type(r.get("conversation_type", "")),
                group_id=_safe_opt_str(r.get("group_id", "")),
                business_id=_safe_opt_str(r.get("business_id", "")),
                sender_user_id=_safe_opt_str(r.get("sender_user_id", "")),
                created_at=r.get("created_at", "").strip(),
                message_text=r.get("message_text", "").strip(),
                media_type=_parse_media_type(r.get("media_type", "")),
                media_id=_safe_opt_str(r.get("media_id", "")),
                forwarded_count=_safe_int(r.get("forwarded_count", "0")),
            )
            ds.message_history.append(hm)
            ds.message_history_by_user.setdefault(hm.user_id, []).append(hm)
            ds.message_history_by_id[hm.message_id] = hm

    def _load_message_events(self, ds: DataStore) -> None:
        rows = self._read_csv("message_events.csv")
        for r in rows:
            me = MessageEvent(
                user_id=r["user_id"].strip(),
                message_id=r["message_id"].strip(),
                message_opened=_safe_bool(r.get("message_opened", "0")),
                message_replied=_safe_bool(r.get("message_replied", "0")),
                reaction_time_minutes=_safe_float(r.get("reaction_time_minutes", "")),
                notification_dismissed=_safe_bool(r.get("notification_dismissed", "0")),
                muted_after_message=_safe_bool(r.get("muted_after_message", "0")),
                message_reported=_safe_bool(r.get("message_reported", "0")),
            )
            ds.message_events.append(me)
            ds.message_events_by_key[(me.user_id, me.message_id)] = me
            ds.message_events_by_msg_id.setdefault(me.message_id, []).append(me)

    def _load_images(self, ds: DataStore) -> None:
        rows = self._read_csv("images.csv")
        for r in rows:
            img = ImageReference(
                image_id=r["image_id"].strip(),
                file_path=r["file_path"].strip(),
            )
            ds.images[img.image_id] = img

    def _load_voice_notes(self, ds: DataStore) -> None:
        rows = self._read_csv("voice_notes.csv")
        for r in rows:
            vn = VoiceNoteReference(
                voice_note_id=r["voice_note_id"].strip(),
                file_path=r["file_path"].strip(),
            )
            ds.voice_notes[vn.voice_note_id] = vn

    def _load_daily_summaries(self, ds: DataStore) -> None:
        rows = self._read_csv("daily_notification_summary.csv")
        for r in rows:
            dns = DailyNotificationSummary(
                user_id=r["user_id"].strip(),
                date=r.get("date", "").strip(),
                notifications_sent=_safe_int(r.get("notifications_sent", "0")),
                notifications_dismissed=_safe_int(r.get("notifications_dismissed", "0")),
            )
            ds.daily_summaries_by_user.setdefault(dns.user_id, []).append(dns)
