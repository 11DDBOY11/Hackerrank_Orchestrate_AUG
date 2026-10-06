"""
Main Entry Point for the AI-Powered Multimodal WhatsApp Notification Router.

Loads datasets, initializes context builder and pipeline engines, routes incoming messages,
writes output.csv, generates decision logs, and optionally triggers evaluation.
"""

import argparse
import sys
import time
from pathlib import Path

# Add code directory to sys.path
CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from config.settings import settings
from data.data_loader import DataLoader
from logger import DecisionLogger
from output_generator import OutputGenerator
from pipeline.notification_router import NotificationRouter


def main():
    parser = argparse.ArgumentParser(description="WhatsApp Notification Router CLI")
    parser.add_argument("--dataset-dir", type=str, default=str(settings.dataset_dir), help="Path to dataset directory")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation after generating predictions")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("      HACKERRANK ORCHESTRATE — WHATSAPP NOTIFICATION ROUTER")
    print("=" * 70)

    # Step 1: Load Datasets
    print(f"\n[1/4] Loading datasets from: {args.dataset_dir}")
    loader = DataLoader(args.dataset_dir)
    ds = loader.load_all()
    print(f"      Loaded {len(ds.messages)} incoming messages to route.")
    print(f"      Loaded {len(ds.sample_messages)} sample benchmark messages.")
    print(f"      Loaded {len(ds.users)} users, {len(ds.groups)} groups, {len(ds.business_accounts)} business accounts.")

    # Step 2: Initialize Pipeline & Route Messages
    print("\n[2/4] Initializing Multimodal Router & Routing Messages...")
    router = NotificationRouter(ds)
    start_time = time.time()
    
    results = router.route_batch(ds.messages)
    decisions = [dec for dec, um in results]
    elapsed = time.time() - start_time
    print(f"      Processed {len(decisions)} messages in {elapsed:.2f} seconds ({elapsed/len(decisions)*1000:.1f} ms/msg).")

    # Step 3: Write Output CSV
    print(f"\n[3/4] Generating predictions CSV: {settings.output_file}")
    generator = OutputGenerator()
    generator.write_output_csv(decisions, output_file_path=settings.output_file)

    # Step 4: Write Logs
    print(f"\n[4/4] Writing decision logs: {settings.log_file}")
    decision_logger = DecisionLogger(settings.log_file)
    decision_logger.log_decisions(results)

    print("\n" + "=" * 70)
    print("SUCCESS: Predictions saved to dataset/output.csv and logs/log.txt")
    print("=" * 70 + "\n")

    # Optional Evaluation Trigger
    if args.evaluate:
        print("Running Evaluation on sample messages...")
        from evaluation.main import evaluate_pipeline
        evaluate_pipeline()


if __name__ == "__main__":
    main()
