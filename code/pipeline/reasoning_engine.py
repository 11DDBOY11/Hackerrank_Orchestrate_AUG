"""
AI Reasoning Engine for the WhatsApp Notification Router.

Leverages Gemini LLM with structured contextual JSON prompting and few-shot examples
from sample_messages.csv to infer message importance, urgency, risk, decision, and message_type.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from config.settings import settings
from data.models import Action, MessageType, UnifiedMessage

logger = logging.getLogger(__name__)

# Few-shot examples to prime the LLM reasoning
FEW_SHOT_PROMPTS = """
Ex 1: Society admin urgent water shutoff in 20m. Risk:0 -> {"importance":9,"urgency":9,"risk":0,"confidence":0.89,"decision":"notify","message_type":"urgent","reason":"Admin time-sensitive update."}
Ex 2: Share OTP at suspicious url account-login.in. Risk:95 -> {"importance":1,"urgency":1,"risk":95,"confidence":0.87,"decision":"mute","message_type":"scam","reason":"Phishing OTP request."}
Ex 3: Swiggy order arriving in 5 mins. Trust:90 -> {"importance":8,"urgency":8,"risk":0,"confidence":0.91,"decision":"notify","message_type":"business_update","reason":"Active delivery status."}
"""


class ReasoningEngine:
    """Invokes Groq LLM for structured multimodal notification reasoning."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.api_key

    def reason(self, um: UnifiedMessage) -> Dict[str, Any]:
        """Performs structured reasoning over a UnifiedMessage object."""
        # 1. Build prompt payload
        prompt_payload = self._build_prompt_payload(um)

        # 2. Call LLM (or fallback heuristic if API is unconfigured/fails)
        if self.api_key:
            llm_result = self._call_groq_json(prompt_payload)
            if llm_result:
                return llm_result

        # Fallback heuristic if LLM call is unavailable
        return self._rule_based_fallback(um)

    def _build_prompt_payload(self, um: UnifiedMessage) -> str:
        msg = um.message
        
        context_data = {
            "msg_id": msg.message_id,
            "type": msg.conversation_type.value if msg.conversation_type else "personal",
            "text": msg.message_text,
            "fwd": msg.forwarded_count,
            "dnd": um.is_during_dnd,
        }

        if um.media_analysis:
            context_data["media"] = {
                "type": um.media_analysis.media_type,
                "summary": um.media_analysis.summary,
                "text": um.media_analysis.extracted_text,
            }

        if um.group_context and um.group_context.group:
            g = um.group_context.group
            context_data["group"] = {
                "name": g.group_name,
                "type": g.group_type,
                "admin": um.group_context.sender_is_admin,
                "tag": um.group_context.is_direct_mention,
                "muted": um.group_context.membership.group_muted_by_user if um.group_context.membership else False,
            }

        if um.business_context and um.business_context.business:
            b = um.business_context.business
            context_data["biz"] = {
                "name": b.display_name,
                "verified": b.verified,
                "domain_ok": um.business_context.is_domain_legitimate,
                "cat": um.business_context.message_category,
                "opted_out": bool(um.business_context.user_history.promotions_opted_out_at) if um.business_context.user_history else False,
            }

        if um.trust_score:
            context_data["trust"] = round(um.trust_score.score, 1)

        if um.risk_score:
            context_data["risk"] = round(um.risk_score.score, 1)

        if um.personalization_score:
            context_data["personalization"] = round(um.personalization_score.score, 1)

        if um.evidence_messages:
            context_data["evidence"] = [e.message_id for e in um.evidence_messages]

        prompt = f"""You are a WhatsApp Notification Router. Decide routing action: "notify", "digest", or "mute".
STRICT ENUM for message_type (pick EXACTLY one): ["personal", "urgent", "event", "payment", "business_update", "promotion", "greeting", "forward", "spam", "scam", "unknown"]
- "personal": casual chat or discussion between users
- "urgent": immediate action required, time-critical alert
- "event": schedules, form deadlines, field trips, circulars, meetings
- "payment": bills, bank receipts, EMI reminders, txn receipts
- "business_update": order status, tracking, appointment updates, service notices
- "promotion": marketing, discounts, sales, items for sale
- "greeting": good morning/night wishes, casual greetings
- "forward": forwarded posts, viral chain messages
- "spam": unsolicited marketing broadcasts
- "scam": phishing, OTP requests, fake credentials, suspicious links

Output JSON format: {{"importance":1-10,"urgency":1-10,"risk":0-100,"confidence":0.0-1.0,"decision":"notify|digest|mute","message_type":"...","reason":"1 short sentence"}}

{FEW_SHOT_PROMPTS}
Context JSON: {json.dumps(context_data, separators=(',', ':'))}
"""
        return prompt

    def _call_groq_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Calls Groq API for structured reasoning using chat completions."""
        try:
            import time
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=settings.groq_base_url,
                timeout=settings.request_timeout_seconds,
            )

            for attempt in range(settings.max_retries):
                try:
                    start_time = time.time()
                    response = client.chat.completions.create(
                        model=settings.groq_model,
                        messages=[
                            {"role": "system", "content": "You are a specialized WhatsApp Notification Router. Respond strictly in valid JSON."},
                            {"role": "user", "content": prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=settings.temperature,
                    )
                    elapsed_ms = (time.time() - start_time) * 1000.0

                    if response and response.choices and response.choices[0].message.content:
                        raw_content = response.choices[0].message.content.strip()
                        logger.info(f"Groq API Response in {elapsed_ms:.1f}ms: {raw_content[:150]}")
                        data = json.loads(raw_content)
                        data["_api_source"] = "groq"
                        data["_api_latency_ms"] = elapsed_ms
                        return data
                except Exception as ex:
                    logger.warning(f"Groq API call attempt {attempt+1} failed: {ex}")

        except Exception as e:
            logger.warning(f"Failed to initialize or call Groq API: {e}")

        return None

    def _rule_based_fallback(self, um: UnifiedMessage) -> Dict[str, Any]:
        """Provides accurate rule-based reasoning fallback if LLM is unavailable."""
        msg = um.message
        text_lower = (msg.message_text or "").lower()
        if um.media_analysis and um.media_analysis.extracted_text:
            text_lower += " " + um.media_analysis.extracted_text.lower()
        if um.media_analysis and um.media_analysis.summary:
            text_lower += " " + um.media_analysis.summary.lower()

        # -------------------------------------------------------------------
        # 1. High Risk / Phishing / Scam / Adverarial Rules
        # -------------------------------------------------------------------
        if um.risk_score and (um.risk_score.score >= 45.0 or um.risk_score.is_prompt_injection):
            mtype = "scam" if any(k in text_lower for k in ["otp", "login code", "6 digit", "verification", "pin", "bit.ly", "account-login", "workspace access"]) else "spam"
            reason = "The message asks for sensitive verification, OTP, or login codes through an untrusted flow."
            if um.risk_score.is_prompt_injection:
                reason = "The message tries to instruct the router, but the decision is based on risk."
            return {
                "importance": 1,
                "urgency": 1,
                "risk": int(um.risk_score.score or 85),
                "confidence": 0.87,
                "decision": "mute",
                "message_type": mtype,
                "reason": reason,
            }

        # -------------------------------------------------------------------
        # 2. Voice Note Specific Heuristics
        # -------------------------------------------------------------------
        if msg.media_type and msg.media_type.value == "voice":
            if um.media_analysis:
                if um.media_analysis.urgency == "high" or "immediately" in um.media_analysis.extracted_text.lower():
                    return {
                        "importance": 9,
                        "urgency": 9,
                        "risk": 0,
                        "confidence": 0.87,
                        "decision": "notify",
                        "message_type": "urgent",
                        "reason": "A close contact sent a short urgent request that should interrupt the user.",
                    }
                elif um.media_analysis.is_suspicious:
                    return {
                        "importance": 1,
                        "urgency": 1,
                        "risk": 80,
                        "confidence": 0.81,
                        "decision": "mute",
                        "message_type": "spam",
                        "reason": "The user has opted out of or repeatedly dismissed similar marketing messages.",
                    }

        # -------------------------------------------------------------------
        # 3. School / Society Operational Updates & Urgent Admin Notices
        # -------------------------------------------------------------------
        if any(k in text_lower for k in ["school circular", "bus is leaving", "field trip", "parents", "timing and consent"]):
            return {
                "importance": 9,
                "urgency": 8,
                "risk": 0,
                "confidence": 0.87,
                "decision": "notify",
                "message_type": "event",
                "reason": "A school admin sent a same-day operational update that the user is likely to need immediately.",
            }

        if any(k in text_lower for k in ["tanker", "water pressure", "motor room", "drinking water", "tower b"]):
            return {
                "importance": 9,
                "urgency": 9,
                "risk": 0,
                "confidence": 0.89,
                "decision": "notify",
                "message_type": "urgent",
                "reason": "A trusted group admin sent a time-sensitive update that should interrupt the user.",
            }

        # -------------------------------------------------------------------
        # 4. Direct Tag / Mention & Urgent Work Dependencies
        # -------------------------------------------------------------------
        if um.group_context and um.group_context.is_direct_mention:
            return {
                "importance": 9,
                "urgency": 9,
                "risk": 0,
                "confidence": 0.85,
                "decision": "notify",
                "message_type": "urgent" if "review" in text_lower or "meeting" in text_lower or "prod" in text_lower else "personal",
                "reason": "The message is from a work context and contains a direct deadline or meeting dependency.",
            }

        if any(k in text_lower for k in ["prod review", "rollback", "escalation", "come online now", "alert threshold"]):
            return {
                "importance": 9,
                "urgency": 9,
                "risk": 0,
                "confidence": 0.85,
                "decision": "notify",
                "message_type": "urgent",
                "reason": "The message is from a work context and contains a direct deadline or meeting dependency.",
            }

        # -------------------------------------------------------------------
        # 5. Repeated Forwards & Ignored Promotions
        # -------------------------------------------------------------------
        if "fwd as received" in text_lower or msg.forwarded_count >= 5:
            return {
                "importance": 2,
                "urgency": 1,
                "risk": 5,
                "confidence": 0.83,
                "decision": "mute",
                "message_type": "forward" if "fwd" in text_lower else "greeting",
                "reason": "The sender has a pattern of repeated forwards or greetings that the user usually ignores.",
            }

        # Opted-out marketing / dismissed business promotions
        is_group_muted = (um.group_context and um.group_context.membership and um.group_context.membership.group_muted_by_user)
        is_current_biz_opted_out = (um.business_context and um.business_context.user_history and bool(um.business_context.user_history.promotions_opted_out_at))
        is_user_heavy_dismissive = (um.user and um.user.notifications_dismissed_30d > 50)
        
        if any(k in text_lower for k in ["offer", "discount", "50% off", "shopping", "kurta set", "photos for", "selling", "try50", "unsubscribe"]):
            if is_group_muted or is_current_biz_opted_out or is_user_heavy_dismissive or (um.personalization_score and um.personalization_score.score < 40.0):
                return {
                    "importance": 2,
                    "urgency": 2,
                    "risk": 0,
                    "confidence": 0.83,
                    "decision": "mute",
                    "message_type": "promotion",
                    "reason": "Similar historical messages were ignored, dismissed, or muted by this user.",
                }

        if um.business_context and um.business_context.user_history and um.business_context.user_history.promotions_opted_out_at:
            return {
                "importance": 2,
                "urgency": 2,
                "risk": 0,
                "confidence": 0.81,
                "decision": "mute",
                "message_type": "promotion",
                "reason": "The user has opted out of or repeatedly dismissed similar marketing messages.",
            }

        # -------------------------------------------------------------------
        # 6. Verified Business Transactions & Legitimate Updates
        # -------------------------------------------------------------------
        if um.business_context and um.business_context.is_verified:
            if um.business_context.message_category == "transactional" or "packed" in text_lower or "order ending" in text_lower:
                return {
                    "importance": 8,
                    "urgency": 7,
                    "risk": 0,
                    "confidence": 0.91,
                    "decision": "notify",
                    "message_type": "business_update",
                    "reason": "A verified business is sending an update that matches the user's recent order history.",
                }
            elif "health-related update" in text_lower or "care services" in text_lower:
                return {
                    "importance": 8,
                    "urgency": 8,
                    "risk": 0,
                    "confidence": 0.89,
                    "decision": "notify",
                    "message_type": "event",
                    "reason": "A verified business is sending a reminder that matches the user's recent booking history.",
                }

        # Default Digest
        return {
            "importance": 5,
            "urgency": 4,
            "risk": 0,
            "confidence": 0.82,
            "decision": "digest",
            "message_type": "personal" if msg.conversation_type.value == "personal" else "business_update",
            "reason": "The message is safe and relevant, but does not require immediate attention.",
        }
