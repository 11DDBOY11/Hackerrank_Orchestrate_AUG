"""
Evaluator for the WhatsApp Notification Router.

Evaluates predictions against sample_messages.csv ground-truth labels.
Calculates Accuracy, Precision, Recall, F1 per action, Confusion Matrix,
Decision Distribution, and generates evaluation/report.md.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, List

CODE_DIR = Path(__file__).resolve().parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from config.settings import settings
from data.data_loader import DataLoader
from data.models import Action, MessageType
from pipeline.notification_router import NotificationRouter

logger = logging.getLogger(__name__)


def evaluate_pipeline(dataset_dir: str | Path = settings.dataset_dir) -> Dict[str, float]:
    """Runs pipeline on sample_messages.csv and evaluates accuracy & metrics."""
    loader = DataLoader(dataset_dir)
    ds = loader.load_all()
    sample_msgs = ds.sample_messages

    if not sample_msgs:
        print("No sample messages found for evaluation.")
        return {}

    router = NotificationRouter(ds)
    
    correct_action = 0
    correct_mtype = 0
    total = len(sample_msgs)

    action_tp: Dict[str, int] = {a.value: 0 for a in Action}
    action_fp: Dict[str, int] = {a.value: 0 for a in Action}
    action_fn: Dict[str, int] = {a.value: 0 for a in Action}

    confusion_matrix: Dict[str, Dict[str, int]] = {
        actual.value: {pred.value: 0 for pred in Action} for actual in Action
    }

    failure_cases: List[Dict] = []

    for sm in sample_msgs:
        # Convert sample message to standard Message for routing
        dec, um = router.route_message(sm)

        actual_act = sm.action.value
        pred_act = dec.action.value
        actual_mtype = sm.message_type.value
        pred_mtype = dec.message_type.value

        confusion_matrix[actual_act][pred_act] += 1

        if actual_act == pred_act:
            correct_action += 1
            action_tp[actual_act] += 1
        else:
            action_fp[pred_act] += 1
            action_fn[actual_act] += 1
            failure_cases.append({
                "id": sm.message_id,
                "text": sm.message_text[:60],
                "actual_action": actual_act,
                "pred_action": pred_act,
                "actual_mtype": actual_mtype,
                "pred_mtype": pred_mtype,
                "reason": dec.reason,
            })

        if actual_mtype == pred_mtype:
            correct_mtype += 1

    action_acc = (correct_action / total) * 100.0 if total > 0 else 0.0
    mtype_acc = (correct_mtype / total) * 100.0 if total > 0 else 0.0

    print(f"\nEvaluation Benchmark Results ({total} sample messages):")
    print(f"  - Action Accuracy:       {action_acc:.2f}% ({correct_action}/{total})")
    print(f"  - Message Type Accuracy: {mtype_acc:.2f}% ({correct_mtype}/{total})")

    # Generate Markdown Report
    _write_evaluation_report(
        total=total,
        action_acc=action_acc,
        mtype_acc=mtype_acc,
        action_tp=action_tp,
        action_fp=action_fp,
        action_fn=action_fn,
        confusion_matrix=confusion_matrix,
        failure_cases=failure_cases,
    )

    return {"action_accuracy": action_acc, "mtype_accuracy": mtype_acc}


def _write_evaluation_report(
    total: int,
    action_acc: float,
    mtype_acc: float,
    action_tp: Dict[str, int],
    action_fp: Dict[str, int],
    action_fn: Dict[str, int],
    confusion_matrix: Dict[str, Dict[str, int]],
    failure_cases: List[Dict],
):
    report_path = settings.report_file
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# WhatsApp Notification Router — Evaluation Report\n")
    lines.append(f"**Benchmark Dataset Size**: {total} sample messages\n")
    lines.append("## Overall Summary Metrics\n")
    lines.append(f"- **Action Classification Accuracy**: `{action_acc:.2f}%`")
    lines.append(f"- **Message Type Classification Accuracy**: `{mtype_acc:.2f}%`\n")

    lines.append("## Per-Class Action Metrics\n")
    lines.append("| Action | Precision | Recall | F1 Score |")
    lines.append("| --- | --- | --- | --- |")

    for act in Action:
        a = act.value
        tp = action_tp[a]
        fp = action_fp[a]
        fn = action_fn[a]
        prec = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        lines.append(f"| `{a}` | {prec:.1f}% | {rec:.1f}% | {f1:.1f}% |")

    lines.append("\n## Confusion Matrix\n")
    lines.append("| Actual \\ Predicted | Notify | Digest | Mute |")
    lines.append("| --- | --- | --- | --- |")
    for actual in ["notify", "digest", "mute"]:
        row = confusion_matrix[actual]
        lines.append(f"| **{actual}** | {row['notify']} | {row['digest']} | {row['mute']} |")

    lines.append("\n## Failure Analysis & Case Inspection\n")
    if failure_cases:
        lines.append(f"Total misclassifications: `{len(failure_cases)}`\n")
        lines.append("| Message ID | Actual Action | Predicted Action | Text Snippet | Router Reason |")
        lines.append("| --- | --- | --- | --- | --- |")
        for fc in failure_cases[:10]:  # Top 10 failures
            lines.append(f"| `{fc['id']}` | `{fc['actual_action']}` | `{fc['pred_action']}` | {fc['text']}... | {fc['reason']} |")
    else:
        lines.append("Perfect classification on all sample benchmark messages! Zero failures detected.\n")

    with open(report_path, mode="w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Saved evaluation report to: {report_path}")


if __name__ == "__main__":
    evaluate_pipeline()
