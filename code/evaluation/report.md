# WhatsApp Notification Router — Evaluation Report

**Benchmark Dataset Size**: 30 sample messages

## Overall Summary Metrics

- **Action Classification Accuracy**: `76.67%`
- **Message Type Classification Accuracy**: `66.67%`

## Per-Class Action Metrics

| Action | Precision | Recall | F1 Score |
| --- | --- | --- | --- |
| `notify` | 80.0% | 88.9% | 84.2% |
| `digest` | 64.3% | 81.8% | 72.0% |
| `mute` | 100.0% | 60.0% | 75.0% |

## Confusion Matrix

| Actual \ Predicted | Notify | Digest | Mute |
| --- | --- | --- | --- |
| **notify** | 8 | 1 | 0 |
| **digest** | 2 | 9 | 0 |
| **mute** | 0 | 4 | 6 |

## Failure Analysis & Case Inspection

Total misclassifications: `7`

| Message ID | Actual Action | Predicted Action | Text Snippet | Router Reason |
| --- | --- | --- | --- | --- |
| `sample_msg_006` | `notify` | `digest` | @u_004 when you get 5 mins can you call? Nothing dramatic, j... | Casual group chat with moderate personalization. |
| `sample_msg_011` | `digest` | `notify` | Thank you for choosing PVR Cinemas,

We would love to hear a... | Active delivery status. |
| `sample_msg_013` | `mute` | `digest` | Good morning all. Stay positive, keep smiling and share bles... | Forwarded message with low importance and risk. |
| `sample_msg_014` | `mute` | `digest` | Fwd as received. Drink warm water every hour and avoid cold ... | Unverified forwarded message with low risk. |
| `sample_msg_041` | `digest` | `notify` | ... | Casual voice message from trusted group member. |
| `sample_msg_045` | `mute` | `digest` | Photos for the kurta set are attached. Pickup is near Gate 2... | Non-urgent marketplace update with attached photos. |
| `sample_msg_047` | `mute` | `digest` | Reminder: your account has a shopping offer available.

Sele... | Promotional message from verified business. |
