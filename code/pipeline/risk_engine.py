"""
Risk and Safety Engine for the WhatsApp Notification Router.

Detects scams, phishing, OTP harvesting, fake banking, domain spoofing,
malicious links, investment fraud, and prompt injection attacks against the router.
"""

from __future__ import annotations

import re
from typing import List, Optional

from config.settings import settings
from data.models import BusinessAccount, ConversationType, MediaAnalysis, Message, RiskScore


# Keywords signaling OTP or account credential theft attempts
PHISHING_KEYWORDS = [
    r"\botp\b",
    r"\b6 digit\b",
    r"\bverification code\b",
    r"\blogin code\b",
    r"\bwallet pin\b",
    r"\bconfirm pin\b",
    r"\baccount blocked\b",
    r"\baccount closure\b",
    r"\bprofile will be restricted\b",
    r"\bpay clearance amount\b",
    r"\bverify your pin\b",
]

# Patterns signaling router prompt injection / override instructions
PROMPT_INJECTION_PATTERNS = [
    r"ignore all previous",
    r"ignore previous routing",
    r"routing override",
    r"system note for the notification router",
    r"assistant instruction",
    r"always mark this as notify",
    r"set action=notify",
    r"internal router metadata",
]

# Known scam/suspicious domains and shorteners in dataset
SUSPICIOUS_DOMAINS = [
    "account-login.in",
    "chase-secure-alert.com",
    "pay-check-secure.com",
    "account-help.in",
    "amazonpay-delivery.in",
    "phonepe-rewards.in",
    "razorpay-billpay.in",
    "hsbc-alerts.net",
    "airtel-simkyc.in",
    "sbireward.in",
    "jioreward.in",
    "talabat-refund.com",
    "icici-secure.net",
    "du-simverify.com",
    "zomato-gold.in",
    "swiggy-refund.in",
    "irctc-refund.in",
    "razorpayx-payouts.com",
    "lucky-draw-result.in",
    "bit.ly",
    "weurl.co",
    "shorturl.at",
    "link.wame.pro",
    "vl.gl",
]


class RiskEngine:
    """Evaluates safety risk, phishing, scam probability, and prompt injection."""

    def compute(
        self,
        message: Message,
        business: Optional[BusinessAccount] = None,
        media_analysis: Optional[MediaAnalysis] = None,
    ) -> RiskScore:
        score = 0.0
        flags: List[str] = []
        reason_parts: List[str] = []
        is_prompt_injection = False

        text = (message.message_text or "").lower()
        if media_analysis and media_analysis.extracted_text:
            text += " " + media_analysis.extracted_text.lower()

        # -------------------------------------------------------------------
        # 1. Prompt Injection Detection
        # -------------------------------------------------------------------
        for pat in PROMPT_INJECTION_PATTERNS:
            if re.search(pat, text):
                is_prompt_injection = True
                score += settings.risk_prompt_injection_penalty
                flags.append("prompt_injection_attempt")
                reason_parts.append("Message contains adversarial instructions targeting the notification router")
                break

        # -------------------------------------------------------------------
        # 2. OTP & Credential Harvesting
        # -------------------------------------------------------------------
        for kw in PHISHING_KEYWORDS:
            if re.search(kw, text):
                score += settings.risk_otp_request_weight
                flags.append("phishing_otp_request")
                reason_parts.append("Message requests sensitive OTP, wallet PIN, or login credentials")
                break

        # Unfamiliar sender asking for sensitive login code / credentials -> High Scam Risk
        if message.conversation_type == ConversationType.PERSONAL and any(k in text for k in ["6 digit", "login code", "verification code", "otp"]):
            score += 45.0
            flags.append("untrusted_sender_credential_request")
            reason_parts.append("This is the first message from the sender and it asks for sensitive verification or payment")

        # Urgent fake support / account block threat
        if re.search(r"block|restrict|suspend|freeze|expire", text) and re.search(r"today|now|immediately|2 hours|30 mins", text):
            score += 25.0
            flags.append("urgency_pressure")
            reason_parts.append("Uses artificial time pressure and account-lock threats")

        # -------------------------------------------------------------------
        # 3. Suspicious Domain & Link Detection
        # -------------------------------------------------------------------
        for dom in SUSPICIOUS_DOMAINS:
            if dom in text:
                score += settings.risk_untrusted_link_weight
                flags.append(f"suspicious_link_{dom}")
                reason_parts.append(f"Contains suspicious or unverified domain link ({dom})")
                break

        # Check domain mismatch from business sender profile
        if business and business.official_domain and business.domain_used_by_sender:
            if business.official_domain.lower() != business.domain_used_by_sender.lower():
                score += 35.0
                flags.append("domain_mismatch")
                reason_parts.append(
                    f"Sender domain mismatch: claimed '{business.official_domain}' but used '{business.domain_used_by_sender}'"
                )

        # -------------------------------------------------------------------
        # 4. Media Analysis Risk Signals
        # -------------------------------------------------------------------
        if media_analysis:
            if media_analysis.is_suspicious:
                score += 30.0
                flags.append("suspicious_media")
                reason_parts.append("Attached media flagged as suspicious or phishing template")

        # -------------------------------------------------------------------
        # 5. Forwarding Chain & Scam Keywords
        # -------------------------------------------------------------------
        if message.forwarded_count >= 5:
            if any(k in text for k in ["blessing", "good luck", "share with 10", "forward to", "chain"]):
                flags.append("viral_forward_spam")
                score += 15.0

        if any(k in text for k in ["lottery", "reward winner", "crypto", "100% return", "claim benefits", "token fee"]):
            score += 25.0
            flags.append("scam_financial_offer")
            reason_parts.append("Contains classic lottery, crypto, or unverified financial claim")

        # Final score calculation (0 to 100)
        final_score = max(0.0, min(100.0, score))
        confidence = 0.90 if flags else 0.70
        reason_str = ". ".join(reason_parts) if reason_parts else "No immediate safety risk detected"

        return RiskScore(
            score=final_score,
            reason=reason_str,
            confidence=confidence,
            flags=flags,
            is_prompt_injection=is_prompt_injection,
        )
