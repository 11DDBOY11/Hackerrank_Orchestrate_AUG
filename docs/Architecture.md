# Architecture Specification — AI Multimodal Notification Router

## System Architecture

The AI-powered Multimodal WhatsApp Notification Router is built using **Clean Architecture** and **SOLID Principles**:

```text
               +----------------------------------+
               |     CLI / main.py Entrypoint     |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |      DataLoader & DataStore      |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |          ContextBuilder          |
               +----------------------------------+
             /         |                 |          \
            v          v                 v           v
      MediaEngine TrustEngine RiskEngine PersonalizationEngine
            \          |                 |          /
             v         v                 v         v
               +----------------------------------+
               |      Normalized UnifiedMessage   |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |    ReasoningEngine (Gemini LLM)  |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |     DecisionEngine & Overrides   |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |   OutputGenerator & Logger       |
               +----------------------------------+
```

---

## High-Level Responsibilities

1. **ContextBuilder**: Joins message payload with metadata tables (User, Group, Business, Historical Messages).
2. **MediaEngine**: Processes multimodal content via Groq Vision API (`llama-3.2-11b-vision-preview`) for images and Groq Audio API (`whisper-large-v3`) for MP3 voice notes.
3. **TrustEngine**: Evaluates sender reputation, account verification, domain matching, and shared history.
4. **RiskEngine**: Independent security layer for OTP phishing, fake support pressure, domain spoofing, and prompt injection attacks.
5. **PersonalizationEngine**: Adjusts routing scores based on individual user engagement rates, muted group settings, and promotional opt-out timestamps.
6. **ReasoningEngine**: Prompts Groq LLM (`llama-3.3-70b-versatile`) with structured contextual JSON and few-shot benchmark examples.
7. **DecisionEngine**: Combines LLM inference with deterministic safety overrides and weighted thresholds to issue the final `notify`, `digest`, or `mute` action.
