"""
Configuration and settings for the WhatsApp Notification Router.

All thresholds, model names, weights, and file paths are centralized here.
None of these values are hardcoded in the pipeline logic.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / "dataset"
CODE_DIR = ROOT_DIR / "code"
LOGS_DIR = ROOT_DIR / "logs"
DOCS_DIR = ROOT_DIR / "docs"
EVALUATION_DIR = CODE_DIR / "evaluation"

# Ensure runtime directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    """System settings and engine thresholds."""
    
    # Groq API Settings
    api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    groq_vision_model: str = os.getenv("GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview")
    groq_audio_model: str = os.getenv("GROQ_AUDIO_MODEL", "whisper-large-v3")
    
    temperature: float = 0.1
    max_tokens: int = 512
    max_retries: int = 1
    request_timeout_seconds: int = 15
    
    # Paths
    dataset_dir: Path = DATASET_DIR
    output_file: Path = DATASET_DIR / "output.csv"
    log_file: Path = LOGS_DIR / "log.txt"
    report_file: Path = EVALUATION_DIR / "report.md"
    
    # Trust Engine Thresholds
    trust_high_threshold: float = 75.0
    trust_low_threshold: float = 30.0
    trust_admin_bonus: float = 20.0
    trust_known_contact_bonus: float = 25.0
    trust_verified_biz_bonus: float = 30.0
    trust_unverified_biz_penalty: float = -25.0
    trust_domain_mismatch_penalty: float = -40.0
    
    # Risk Engine Thresholds (0-100)
    risk_scam_threshold: float = 50.0      # Score >= 50 is classified as scam/spam -> MUTE
    risk_high_threshold: float = 80.0
    risk_phishing_kw_weight: float = 30.0
    risk_otp_request_weight: float = 40.0
    risk_untrusted_link_weight: float = 25.0
    risk_prompt_injection_penalty: float = 90.0
    
    # Personalization Engine Thresholds
    personalization_opted_out_penalty: float = -40.0
    personalization_high_engagement_bonus: float = 30.0
    personalization_ignored_history_penalty: float = -30.0
    
    # Hybrid Decision Weights (for weighted scoring)
    w_importance: float = 0.35
    w_urgency: float = 0.35
    w_trust: float = 0.15
    w_personalization: float = 0.15
    w_risk_penalty: float = 0.50
    
    # Action Score Decision Thresholds
    notify_threshold: float = 0.65    # Score >= 0.65 -> NOTIFY
    digest_threshold: float = 0.35    # 0.35 <= Score < 0.65 -> DIGEST
                                      # Score < 0.35 -> MUTE


settings = Settings()
