"""
Notification Router Orchestrator for the WhatsApp Notification Router.

Coordinates data loading, context enrichment, media processing, AI reasoning,
and final decision generation across batches of incoming messages.
"""

from __future__ import annotations

import logging
import time
from typing import List, Tuple

from data.data_loader import DataStore
from data.models import Message, RoutingDecision, UnifiedMessage
from pipeline.context_builder import ContextBuilder
from pipeline.decision_engine import DecisionEngine
from pipeline.reasoning_engine import ReasoningEngine

logger = logging.getLogger(__name__)


class NotificationRouter:
    """End-to-end router orchestrating the AI-powered routing pipeline."""

    def __init__(
        self,
        ds: DataStore,
        context_builder: Optional[ContextBuilder] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        decision_engine: Optional[DecisionEngine] = None,
    ):
        self.ds = ds
        self.context_builder = context_builder or ContextBuilder(ds)
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.decision_engine = decision_engine or DecisionEngine()
        self.llm_success_count = 0
        self.fallback_count = 0

    def route_message(self, message: Message) -> Tuple[RoutingDecision, UnifiedMessage]:
        """Routes a single incoming message through the entire pipeline."""
        start_time = time.time()

        # Step 1: Build enriched UnifiedMessage context
        um = self.context_builder.build_unified_message(message)

        # Step 2: AI / Multimodal Reasoning
        reasoning_res = self.reasoning_engine.reason(um)

        if reasoning_res.get("_api_source") == "groq":
            self.llm_success_count += 1
        else:
            self.fallback_count += 1

        # Step 3: Decision Engine (Apply overrides & validation)
        decision = self.decision_engine.make_decision(um, reasoning_res)

        elapsed_ms = (time.time() - start_time) * 1000.0
        decision.execution_time_ms = elapsed_ms
        decision.llm_raw_output = str(reasoning_res)

        return decision, um

    def route_batch(self, messages: List[Message]) -> List[Tuple[RoutingDecision, UnifiedMessage]]:
        """Routes a list of incoming messages in batch mode."""
        self.llm_success_count = 0
        self.fallback_count = 0
        results = []
        for msg in messages:
            try:
                dec, um = self.route_message(msg)
                results.append((dec, um))
            except Exception as e:
                logger.error(f"Error routing message_id={msg.message_id}: {e}", exc_info=True)

        logger.info(
            f"Batch Routing Complete: {len(results)} total messages. "
            f"Groq LLM Responses: {self.llm_success_count}, Rule Fallbacks: {self.fallback_count}"
        )
        print(
            f"      Execution Source Statistics:\n"
            f"        - Live Groq LLM Responses: {self.llm_success_count}\n"
            f"        - Offline Rule Fallbacks:   {self.fallback_count}"
        )
        return results
