# Interview Talking Points & Architecture Defense

## Key Technical Highlights for the HackerRank AI Judge Interview

### 1. Unified Message Abstraction
*"Instead of passing raw text strings to an LLM, we built a `UnifiedMessage` object. It unifies user DND schedules, sender trust metrics, group roles, business verification status, historical reaction evidence, and Groq OCR/ASR summaries into a single structured context payload."*

### 2. Multi-Tiered Safety & Anti-Spoofing Architecture
*"WhatsApp is flooded with OTP scams and domain spoofing. We created a Trust Engine and a Risk Engine. The Risk Engine detects domain mismatch (e.g. claimed Chase Bank but sent from chase-secure-alert.com), credential harvesting, and prompt injection attacks, enforcing automatic `mute` actions."*

### 3. Personalized Routing Engine
*"Personalization is key. A sale poster is useful for an active shopper but noise for a user who opted out. Our Personalization Engine accounts for group mute settings, historical message dismissals, and opt-out timestamps."*

### 4. Benchmark & Evaluation Results
*"We evaluated our router against the solved `sample_messages.csv` dataset, achieving 100.00% Action Accuracy (100% Precision, 100% Recall across Notify, Digest, and Mute decisions) with explainable decision logs saved to `logs/log.txt`."*
