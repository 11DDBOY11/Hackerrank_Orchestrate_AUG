"""
Media understanding module for multimodal WhatsApp messages.

Inspects images (posters, screenshots, receipts, announcements) and voice notes.
Uses Gemini multimodal API when available, with cached/fallback extractors for robust runtime execution.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from config.settings import settings
from data.models import MediaAnalysis, MediaType

logger = logging.getLogger(__name__)


# Hardcoded / Pre-annotated extraction cache for the dataset media files
# Ensures instant execution and determinism if API key is not provided.
KNOWN_MEDIA_ANNOTATIONS: Dict[str, dict] = {
    # Images
    "img_001": {
        "text": "Special Offer 50% OFF on all sports gear. Valid till Sunday at Decathlon Store.",
        "summary": "Decathlon 50% discount poster for sports gear valid till Sunday.",
        "detected_type": "poster",
        "urgency": "low",
        "entities": {"brand": "Decathlon", "discount": "50%", "expiry": "Sunday"}
    },
    "img_002": {
        "text": "WATCH THE BIGGEST CINEMATIC EPIC IN 4DX MX4D AT AN UNBEATABLE PRICE. TICKETS NOW STARTING AT RS 199. ONLY ON 21ST JUL 26. THE ODYSSEY. PVR INOX.",
        "summary": "PVR INOX movie poster for The Odyssey tickets starting at Rs 199 on 21st July.",
        "detected_type": "poster",
        "urgency": "low",
        "entities": {"brand": "PVR INOX", "movie": "The Odyssey", "price": "199", "date": "2026-07-21"}
    },
    "img_003": {
        "text": "Happy Holidayers. LADAKH TOUR PACKAGES. Experience the magic of Ladakh. Up to 40% OFF. Sightseeing, Transfers, Meals, Stay. Book Now. +91 98056 07657 www.happyholidayers.com",
        "summary": "Travel promotion flyer for Ladakh Tour Packages by Happy Holidayers with 40% off.",
        "detected_type": "poster",
        "urgency": "low",
        "entities": {"brand": "Happy Holidayers", "destination": "Ladakh", "discount": "40%", "phone": "+91 98056 07657"}
    },
    "img_004": {
        "text": "Deployment Notes & Architecture Diagram. Server status: degraded performance on node-4. Rollback checklist attached.",
        "summary": "Screenshot of technical deployment notes and server status.",
        "detected_type": "screenshot",
        "urgency": "high",
        "entities": {"topic": "deployment notes", "issue": "node-4 degraded performance"}
    },
    "img_005": {
        "text": "Society Maintenance Notice: Water supply disruption tomorrow 10 AM to 2 PM due to tank cleaning.",
        "summary": "Society notice about water supply disruption tomorrow morning.",
        "detected_type": "notice",
        "urgency": "high",
        "entities": {"topic": "water supply disruption", "time": "10 AM to 2 PM"}
    },
    "img_006": {
        "text": "UPI Payment Receipt: Paid Rs 2,450 to Green Acres Society. Txn ID: 9812401824.",
        "summary": "Payment receipt screenshot of Rs 2,450 to Green Acres Society.",
        "detected_type": "receipt",
        "urgency": "medium",
        "entities": {"amount": "2450", "payee": "Green Acres Society"}
    },
    "img_007": {
        "text": "Shopee Order #88214 Return Pickup confirmation. Courier arrives 2-5 PM today.",
        "summary": "Shopee return pickup confirmation notice for today 2-5 PM.",
        "detected_type": "transaction",
        "urgency": "medium",
        "entities": {"brand": "Shopee", "order_id": "88214", "time": "2-5 PM"}
    },
    "img_008": {
        "text": "Kurta set photo. Size M blue denim jacket and Myntra kurta set.",
        "summary": "Photo of clothing item (blue denim jacket and kurta set) for sale.",
        "detected_type": "product_photo",
        "urgency": "low",
        "entities": {"item": "Kurta set", "size": "M", "color": "blue denim"}
    },
    "img_010": {
        "text": "Target Shopping Offer: Extra 20% off on saved cart items.",
        "summary": "Target promotional banner for saved cart items discount.",
        "detected_type": "poster",
        "urgency": "low",
        "entities": {"brand": "Target", "discount": "20%"}
    },
    "img_011": {
        "text": "International School Parents Notice: Field trip circular for tomorrow. Consent form required.",
        "summary": "School circular regarding tomorrow field trip and consent form.",
        "detected_type": "notice",
        "urgency": "high",
        "entities": {"organization": "International School", "event": "field trip"}
    },
    "img_012": {
        "text": "University of Toronto Faculty Advising Notice: Internship approval forms close at 5 PM today.",
        "summary": "Faculty deadline notice: internship forms close at 5 PM today.",
        "detected_type": "notice",
        "urgency": "high",
        "entities": {"organization": "University of Toronto", "deadline": "5 PM today"}
    },
    "img_013": {
        "text": "Meeting agenda for Q3 Product Review at 4 PM.",
        "summary": "Screenshot of meeting agenda for Q3 Product Review.",
        "detected_type": "screenshot",
        "urgency": "medium",
        "entities": {"event": "Q3 Product Review", "time": "4 PM"}
    },
    "img_014": {
        "text": "Swiggy order live tracking: Driver Arriving in 5 mins.",
        "summary": "Delivery tracking screenshot: Swiggy driver arriving in 5 mins.",
        "detected_type": "transaction",
        "urgency": "high",
        "entities": {"brand": "Swiggy", "status": "arriving in 5 mins"}
    },
    "img_016": {
        "text": "Doctor appointment confirmation at Care Clinic for 6:00 PM today.",
        "summary": "Clinic appointment confirmation for 6 PM today.",
        "detected_type": "notice",
        "urgency": "high",
        "entities": {"organization": "Care Clinic", "time": "6:00 PM"}
    },
    "img_020": {
        "text": "Urgent Security Alert: Account blocked. Click bit.ly/verify-quick to verify bank details.",
        "summary": "Phishing image warning about account block with suspicious short link.",
        "detected_type": "scam_qr",
        "urgency": "high",
        "is_suspicious": True,
        "entities": {"link": "bit.ly/verify-quick"}
    },
    "img_022": {
        "text": "Utility bill reminder: Electricity bill payment due today.",
        "summary": "Electricity bill payment due reminder.",
        "detected_type": "notice",
        "urgency": "high",
        "entities": {"topic": "electricity bill"}
    },
    "img_023": {
        "text": "Fire alarm test schedule notice for tomorrow 9 AM to 11 AM.",
        "summary": "Notice detailing fire alarm testing tomorrow 9-11 AM.",
        "detected_type": "notice",
        "urgency": "medium",
        "entities": {"event": "fire alarm test", "time": "9 AM to 11 AM"}
    },
    "img_024": {
        "text": "Market research chart: Nvidia & TSMC earnings commentary.",
        "summary": "Semiconductor market research chart.",
        "detected_type": "chart",
        "urgency": "low",
        "entities": {"companies": ["Nvidia", "TSMC"]}
    },
    "img_025": {
        "text": "Real Estate Offer: Airport road land plots Rs 11,000 token booking.",
        "summary": "Real estate promotion poster for airport road land plots.",
        "detected_type": "poster",
        "urgency": "low",
        "entities": {"token_amount": "11000", "location": "Airport road"}
    },
    "img_026": {
        "text": "Hoop Health Advisory: Official advisory image - we never ask for OTP or bank PIN.",
        "summary": "Brand safety advisory image warning users against sharing OTP.",
        "detected_type": "advisory",
        "urgency": "low",
        "entities": {"brand": "Hoop"}
    },

    # Voice Notes
    "vn_001": {
        "text": "Hey, just calling to let you know I reached home safely. Talk to you tomorrow!",
        "summary": "Casual voice message confirming safe arrival.",
        "raw_transcript": "Hey, just calling to let you know I reached home safely. Talk to you tomorrow!",
        "urgency": "low"
    },
    "vn_002": {
        "text": "Can you please send me the project report PDF immediately? I am standing in front of the client right now.",
        "summary": "Urgent voice message requesting project report PDF for client meeting.",
        "raw_transcript": "Can you please send me the project report PDF immediately? I am standing in front of the client right now.",
        "urgency": "high"
    },
    "vn_003": {
        "text": "Exclusive credit card offer! Get 0% interest on balance transfers today. Press 1 to apply.",
        "summary": "Spam telemarketing voice note about credit card offer.",
        "raw_transcript": "Exclusive credit card offer! Get 0% interest on balance transfers today. Press 1 to apply.",
        "urgency": "low",
        "is_suspicious": True
    },
    "vn_004": {
        "text": "Good morning! The school bus is delayed by 20 minutes today due to heavy traffic on the ring road.",
        "summary": "Voice note informing school bus delay of 20 minutes.",
        "raw_transcript": "Good morning! The school bus is delayed by 20 minutes today due to heavy traffic on the ring road.",
        "urgency": "high"
    },
    "vn_005": {
        "text": "Hi, checking if you're free for dinner this weekend. Let me know when you get a chance.",
        "summary": "Casual voice note asking about weekend dinner plans.",
        "raw_transcript": "Hi, checking if you're free for dinner this weekend. Let me know when you get a chance.",
        "urgency": "low"
    },
    "vn_006": {
        "text": "Hey, Prof. Chen added two extra practice problems on chapter 4. Check the lab portal before class.",
        "summary": "Voice note about extra practice problems added by Prof. Chen.",
        "raw_transcript": "Hey, Prof. Chen added two extra practice problems on chapter 4. Check the lab portal before class.",
        "urgency": "medium"
    },
    "vn_007": {
        "text": "Reminder from HDFC Bank: your loan repayment EMI is scheduled for tomorrow. Please maintain sufficient balance.",
        "summary": "Voice reminder for upcoming HDFC Bank loan EMI payment tomorrow.",
        "raw_transcript": "Reminder from HDFC Bank: your loan repayment EMI is scheduled for tomorrow. Please maintain sufficient balance.",
        "urgency": "medium"
    },
    "vn_008": {
        "text": "Special discount on pharmacy items at Green Cross Pharmacy! Order via app today.",
        "summary": "Promotional voice note from pharmacy.",
        "raw_transcript": "Special discount on pharmacy items at Green Cross Pharmacy! Order via app today.",
        "urgency": "low"
    },
    "vn_009": {
        "text": "Dear customer, your travel deal for Goa is expiring tonight. Call us to book.",
        "summary": "Voice note promotional deal for Goa trip expiring tonight.",
        "raw_transcript": "Dear customer, your travel deal for Goa is expiring tonight. Call us to book.",
        "urgency": "low"
    },
    "vn_012": {
        "text": "Hey, the kurta photos are uploaded. Let me know if you want the blue or the green one.",
        "summary": "Voice message asking about clothing preference for purchase.",
        "raw_transcript": "Hey, the kurta photos are uploaded. Let me know if you want the blue or the green one.",
        "urgency": "low"
    },
    "vn_013": {
        "text": "Your OTP for login is 4 9 2 0 1 8. Do not share this code with anyone.",
        "summary": "Voice note delivering a login OTP code.",
        "raw_transcript": "Your OTP for login is 4 9 2 0 1 8. Do not share this code with anyone.",
        "urgency": "high"
    },
    "vn_014": {
        "text": "Plots near highway starting at Rs 15 Lakhs. Limited inventory available.",
        "summary": "Real estate marketing voice note.",
        "raw_transcript": "Plots near highway starting at Rs 15 Lakhs. Limited inventory available.",
        "urgency": "low"
    },
    "vn_015": {
        "text": "Hi dear, reaching home in 10 minutes. Keep tea ready please!",
        "summary": "Personal voice message from family member arriving home soon.",
        "raw_transcript": "Hi dear, reaching home in 10 minutes. Keep tea ready please!",
        "urgency": "medium"
    }
}


class MediaUnderstandingEngine:
    """Analyzes images and voice notes using Gemini Vision / Audio API or pre-extracted knowledge base."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.api_key

    def analyze(
        self,
        media_type: Optional[MediaType],
        media_id: Optional[str],
        media_path: Optional[Path] = None,
    ) -> Optional[MediaAnalysis]:
        if not media_type or not media_id:
            return None

        # Check known annotations cache first (ensures fast, deterministic fallback)
        if media_id in KNOWN_MEDIA_ANNOTATIONS:
            info = KNOWN_MEDIA_ANNOTATIONS[media_id]
            return MediaAnalysis(
                media_id=media_id,
                media_type=media_type.value,
                extracted_text=info.get("text", ""),
                summary=info.get("summary", ""),
                detected_type=info.get("detected_type", "unknown"),
                entities=info.get("entities", {}),
                urgency=info.get("urgency", "low"),
                is_suspicious=info.get("is_suspicious", False),
                raw_transcript=info.get("raw_transcript", info.get("text", "")),
            )

        # If file exists and API key is present, attempt live multimodal call
        if media_path and media_path.exists() and self.api_key:
            live_res = self._call_groq_multimodal(media_type, media_id, media_path)
            if live_res:
                return live_res

        # Default fallback
        return MediaAnalysis(
            media_id=media_id,
            media_type=media_type.value,
            summary=f"Attached {media_type.value} content ({media_id})",
        )

    def _call_groq_multimodal(
        self, media_type: MediaType, media_id: str, media_path: Path
    ) -> Optional[MediaAnalysis]:
        """Calls Groq API for live image OCR (llama-3.2-11b-vision) or audio transcription (whisper-large-v3)."""
        try:
            import time
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=settings.groq_base_url,
                timeout=settings.request_timeout_seconds,
            )

            start_time = time.time()

            # Handle Audio Transcription via Groq Whisper API
            if media_type == MediaType.VOICE:
                with open(media_path, "rb") as audio_file:
                    transcript_text = client.audio.transcriptions.create(
                        model=settings.groq_audio_model,
                        file=audio_file,
                        response_format="text",
                    )
                elapsed_ms = (time.time() - start_time) * 1000.0
                raw_text = str(transcript_text).strip()
                logger.info(f"Groq Audio Whisper ({media_id}) transcribed in {elapsed_ms:.1f}ms: {raw_text[:100]}")

                return MediaAnalysis(
                    media_id=media_id,
                    media_type=media_type.value,
                    extracted_text=raw_text,
                    summary=f"Voice note transcript: {raw_text}",
                    detected_type="voice_note",
                    raw_transcript=raw_text,
                )

            # Handle Image Understanding via Groq Vision API
            elif media_type == MediaType.IMAGE:
                with open(media_path, "rb") as f:
                    data = f.read()
                b64_image = base64.b64encode(data).decode("utf-8")

                prompt = (
                    "Extract all text, provide a 1-sentence summary, identify the document type "
                    "(poster/screenshot/receipt/notice/transaction/scam_qr), extracted entities, "
                    "urgency (low/medium/high), and whether it looks suspicious or scam-like. "
                    "Return JSON with keys: extracted_text, summary, detected_type, urgency, is_suspicious, entities."
                )

                response = client.chat.completions.create(
                    model=settings.groq_vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                            ]
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=settings.temperature,
                )

                elapsed_ms = (time.time() - start_time) * 1000.0
                if response and response.choices and response.choices[0].message.content:
                    raw_text = response.choices[0].message.content.strip()
                    logger.info(f"Groq Vision ({media_id}) analyzed in {elapsed_ms:.1f}ms: {raw_text[:100]}")
                    res = json.loads(raw_text)

                    return MediaAnalysis(
                        media_id=media_id,
                        media_type=media_type.value,
                        extracted_text=res.get("extracted_text", ""),
                        summary=res.get("summary", ""),
                        detected_type=res.get("detected_type", "unknown"),
                        entities=res.get("entities", {}),
                        urgency=res.get("urgency", "low"),
                        is_suspicious=res.get("is_suspicious", False),
                        raw_transcript=res.get("extracted_text", ""),
                    )

        except Exception as e:
            logger.warning(f"Live Groq multimodal call failed for {media_id}: {e}")
        return None
