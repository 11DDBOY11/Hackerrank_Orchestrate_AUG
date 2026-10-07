import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add root project directory to sys.path so we can import code modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import our 8-engine routing pipeline & models
from code.config import settings
from code.data.data_loader import DataLoader
from code.data.models import Message, RoutingDecision
from code.pipeline.notification_router import NotificationRouter

app = FastAPI(
    title="WhatsApp Multimodal Notification Router API",
    description="Cross-platform Mobile Backend for Real-Time Notification Triage & Anti-Phishing",
    version="1.0.0"
)

# Enable CORS for mobile apps & PWAs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DataLoader & Router singleton
data_loader = DataLoader()
router = NotificationRouter(data_loader=data_loader)

# In-memory storage for mobile session state & digests
triage_history: List[Dict[str, Any]] = []

class NotificationRequest(BaseModel):
    message_id: Optional[str] = Field(default=None, description="Optional unique message ID")
    sender_id: str = Field(..., example="usr_001", description="User ID or Phone Number of sender")
    chat_type: str = Field(default="direct", example="direct", description="direct or group")
    group_id: Optional[str] = Field(default=None, example="grp_001", description="Group ID if group chat")
    content: str = Field(..., example="Your OTP for login is 492011. Do not share it.", description="Text content of the message")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="ISO Timestamp")
    has_image: bool = Field(default=False)
    has_audio: bool = Field(default=False)
    image_path: Optional[str] = None
    audio_path: Optional[str] = None

class TriageResponse(BaseModel):
    message_id: str
    action: str
    message_type: str
    reason: str
    confidence: float
    evidence_message_ids: str
    processed_at: str

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "online",
        "system": "WhatsApp Notification Router API",
        "groq_api_configured": bool(settings.groq_api_key),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/triage", response_model=TriageResponse)
def triage_notification(payload: NotificationRequest):
    """
    Evaluates an incoming push notification in real-time.
    Returns action (notify, digest, mute), category, risk level, and rationale.
    """
    msg_id = payload.message_id or f"msg_live_{int(datetime.now().timestamp() * 1000)}"
    
    # Construct domain Message object
    msg = Message(
        message_id=msg_id,
        sender_id=payload.sender_id,
        chat_type=payload.chat_type,
        group_id=payload.group_id,
        timestamp=payload.timestamp,
        content=payload.content,
        has_image=payload.has_image,
        has_audio=payload.has_audio,
        image_path=payload.image_path,
        audio_path=payload.audio_path
    )
    
    # Run through the 8-engine routing pipeline
    decision = router.route_message(msg)
    
    record = {
        "message_id": decision.message_id,
        "sender_id": payload.sender_id,
        "chat_type": payload.chat_type,
        "content": payload.content,
        "action": decision.action,
        "message_type": decision.message_type,
        "reason": decision.reason,
        "confidence": decision.confidence,
        "evidence_message_ids": decision.evidence_message_ids,
        "processed_at": datetime.now().isoformat()
    }
    
    triage_history.insert(0, record)
    if len(triage_history) > 200:
        triage_history.pop()
        
    return TriageResponse(
        message_id=decision.message_id,
        action=decision.action,
        message_type=decision.message_type,
        reason=decision.reason,
        confidence=decision.confidence,
        evidence_message_ids=decision.evidence_message_ids,
        processed_at=record["processed_at"]
    )

@app.get("/api/v1/digest")
def get_daily_digest():
    """Returns batched non-urgent digest notifications."""
    digest_items = [item for item in triage_history if item["action"] == "digest"]
    return {
        "total_digest_items": len(digest_items),
        "items": digest_items
    }

@app.get("/api/v1/stats")
def get_triage_stats():
    """Returns aggregate mobile notification metrics."""
    total = len(triage_history)
    notify_count = sum(1 for x in triage_history if x["action"] == "notify")
    digest_count = sum(1 for x in triage_history if x["action"] == "digest")
    mute_count = sum(1 for x in triage_history if x["action"] == "mute")
    scams_blocked = sum(1 for x in triage_history if x["action"] == "mute" and x["message_type"] == "scam")
    
    return {
        "total_processed": total,
        "notify_count": notify_count,
        "digest_count": digest_count,
        "mute_count": mute_count,
        "scams_blocked": scams_blocked,
        "notify_percentage": round((notify_count / total * 100), 1) if total > 0 else 0,
        "digest_percentage": round((digest_count / total * 100), 1) if total > 0 else 0,
        "mute_percentage": round((mute_count / total * 100), 1) if total > 0 else 0,
    }

# Mount static folder for PWA dashboard
static_path = Path(__file__).parent / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    index_file = static_path / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>WhatsApp Router API Running</h1><p>Visit <a href='/docs'>/docs</a> for API Swagger.</p>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)
