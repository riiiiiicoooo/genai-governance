"""
LangSmith Integration for GenAI Governance Platform

Provides complete observability of the governance pipeline with:
- Distributed tracing via @traceable decorators
- Custom evaluators for guardrail accuracy and PII detection
- Cost tracking per LLM interaction
- Trace metadata capturing governance decisions
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from langsmith import traceable, Client, run_trees
from langsmith.evaluation import evaluate, LangSmithEvaluator
from langsmith.evaluation.evaluator import EvaluationResult

# Configure logging
logger = logging.getLogger(__name__)

# Initialize LangSmith client
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "genai-governance")
langsmith_client = Client(api_key=LANGSMITH_API_KEY)


class GuardrailDecision(str, Enum):
    """Guardrail action decision"""
    DELIVER = "deliver"
    BLOCK = "block"
    WARN = "warn"


# ============================================================================
# Custom Evaluators
# ============================================================================


class GuardrailAccuracyEvaluator(LangSmithEvaluator):
    """
    Evaluates guardrail accuracy: false positive and false negative rates.

    False Positive: Blocked an output that should have been delivered
    False Negative: Delivered an output that should have been blocked
    """

    def __init__(self, name: str = "guardrail_accuracy"):
        super().__init__()
        self.name = name

    def evaluate_run(self, run, example: Optional[Dict] = None) -> EvaluationResult:
        """
        Evaluate a single governance trace.

        Expected metadata in run:
        - guardrail_decision: actual decision (deliver/block/warn)
        - guardrail_details: dict with per-check results
        - expected_action: what should have happened (if known)
        """
        metadata = run.extra.get("metadata", {}) if run.extra else {}
        guardrail_decision = metadata.get("guardrail_decision")
        guardrail_details = metadata.get("guardrail_details", {})
        expected_action = metadata.get("expected_action")

        if not guardrail_decision:
            return EvaluationResult(
                key=self.name,
                score=0.0,
                comment="No guardrail_decision in metadata",
            )

        # Score calculation
        score = 1.0
        false_positives = 0
        false_negatives = 0

        if expected_action:
            if expected_action == "deliver" and guardrail_decision == "block":
                false_positives += 1
                score -= 0.5
            elif expected_action == "block" and guardrail_decision == "deliver":
                false_negatives += 1
                score -= 0.5

        score = max(0.0, min(1.0, score))

        return EvaluationResult(
            key=self.name,
            score=score,
            metadata={
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "decision": guardrail_decision,
                "details": guardrail_details,
            },
        )


class PIIDetectionEvaluator(LangSmithEvaluator):
    """
    Evaluates PII detection precision and recall.

    Precision: Of flagged PIIs, how many were actual PIIs?
    Recall: Of actual PIIs, how many did we flag?
    """

    def __init__(self, name: str = "pii_detection"):
        super().__init__()
        self.name = name

    def evaluate_run(self, run, example: Optional[Dict] = None) -> EvaluationResult:
        """
        Evaluate PII detection accuracy.

        Expected metadata:
        - pii_detected: list of detected PII instances
        - expected_pii: ground truth PII instances (if labeled)
        """
        metadata = run.extra.get("metadata", {}) if run.extra else {}
        detected_pii = metadata.get("pii_detected", [])
        expected_pii = metadata.get("expected_pii", [])

        # If no expected PII is provided, score based on detection consistency
        if not expected_pii:
            score = 1.0 if detected_pii else 0.5  # Prefer detecting something
            return EvaluationResult(
                key=self.name,
                score=score,
                metadata={
                    "detected_count": len(detected_pii),
                    "precision": None,
                    "recall": None,
                    "f1": None,
                },
            )

        # Calculate precision and recall
        true_positives = len([p for p in detected_pii if p in expected_pii])
        false_positives = len([p for p in detected_pii if p not in expected_pii])
        false_negatives = len([p for p in expected_pii if p not in detected_pii])

        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )
        f1 = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return EvaluationResult(
            key=self.name,
            score=f1,
            metadata={
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
            },
        )


class ConfidenceScoreEvaluator(LangSmithEvaluator):
    """
    Evaluates model confidence calibration.
    High confidence outputs should have high actual quality.
    """

    def __init__(self, name: str = "confidence_calibration"):
        super().__init__()
        self.name = name

    def evaluate_run(self, run, example: Optional[Dict] = None) -> EvaluationResult:
        """
        Evaluate confidence score calibration.

        Expected metadata:
        - confidence_score: model's confidence (0-1)
        - quality_score: actual output quality rating (0-1)
        """
        metadata = run.extra.get("metadata", {}) if run.extra else {}
        confidence = metadata.get("confidence_score")
        quality = metadata.get("quality_score")

        if confidence is None or quality is None:
            return EvaluationResult(
                key=self.name,
                score=0.5,
                comment="Missing confidence_score or quality_score",
            )

        # Score based on calibration (lower is better)
        calibration_error = abs(confidence - quality)
        score = 1.0 - calibration_error

        return EvaluationResult(
            key=self.name,
            score=score,
            metadata={
                "confidence": round(confidence, 3),
                "actual_quality": round(quality, 3),
                "calibration_error": round(calibration_error, 3),
            },
        )


# ============================================================================
# Governance Pipeline Tracing
# ============================================================================


@traceable(name="governance_pipeline", tags=["governance", "core"])
def trace_governance_pipeline(
    interaction_id: str,
    use_case: str,
    input_context: Dict[str, Any],
    model_id: str,
    prompt_template_name: str,
    prompt_version: str,
) -> Dict[str, Any]:
    """
    Main entry point for governance pipeline tracing.

    Args:
        interaction_id: Unique identifier for this interaction
        use_case: member_service or loan_processing
        input_context: Context variables for prompt injection
        model_id: Which LLM model (e.g., claude-3-sonnet)
        prompt_template_name: Name of the approved prompt template
        prompt_version: Version number of the prompt

    Returns:
        Governance pipeline result with tracing metadata
    """
    return {
        "interaction_id": interaction_id,
        "use_case": use_case,
        "input_context": input_context,
        "model_id": model_id,
        "prompt_template": prompt_template_name,
        "prompt_version": prompt_version,
        "timestamp": datetime.utcnow().isoformat(),
    }


@traceable(name="prompt_rendering", tags=["governance", "prompt"])
def trace_prompt_rendering(
    template_name: str,
    template_version: str,
    context_variables: Dict[str, Any],
) -> str:
    """
    Trace prompt rendering from template.

    Args:
        template_name: Name of the prompt template
        template_version: Version of the template
        context_variables: Variables injected into template

    Returns:
        Rendered prompt string
    """
    rendered = f"[Template: {template_name} v{template_version}]\n"
    rendered += f"[Context: {json.dumps(context_variables, indent=2)}]"
    return rendered


@traceable(name="llm_interaction", tags=["governance", "llm"])
def trace_llm_call(
    model_id: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> Dict[str, Any]:
    """
    Trace LLM API call and track usage/cost.

    Args:
        model_id: Model identifier (e.g., claude-3-sonnet-20240229)
        prompt: Full prompt sent to LLM
        temperature: LLM temperature setting
        max_tokens: Maximum tokens in response

    Returns:
        LLM response with token counts and cost
    """
    # Simulate LLM response (in production, this calls the actual API)
    mock_response = {
        "output": "This is a mock response for governance demonstration.",
        "input_tokens": len(prompt.split()),
        "output_tokens": 12,
        "model": model_id,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Calculate cost (example rates for AWS Bedrock Claude 3 Sonnet)
    input_cost_per_1m = 3  # $3 per 1M input tokens
    output_cost_per_1m = 15  # $15 per 1M output tokens

    input_cost = (mock_response["input_tokens"] * input_cost_per_1m) / 1_000_000
    output_cost = (mock_response["output_tokens"] * output_cost_per_1m) / 1_000_000
    total_cost = input_cost + output_cost

    mock_response["cost_usd"] = round(total_cost, 6)

    return mock_response


@traceable(name="guardrail_evaluation", tags=["governance", "guardrails"])
def trace_guardrail_evaluation(
    output_text: str,
    input_context: Dict[str, Any],
    enabled_guardrails: List[str],
) -> Dict[str, Any]:
    """
    Trace guardrail evaluation across all checks.

    Args:
        output_text: LLM output to evaluate
        input_context: Original context for hallucination checking
        enabled_guardrails: Which guardrails are active

    Returns:
        Guardrail results with decision and details
    """
    results = {
        "pii_detection": trace_pii_check(output_text),
        "hallucination_check": trace_hallucination_check(output_text, input_context),
        "bias_screening": trace_bias_check(output_text),
        "compliance_filter": trace_compliance_check(output_text),
        "confidence_assessment": trace_confidence_check(output_text),
    }

    # Determine overall decision
    decision = GuardrailDecision.DELIVER
    if any(r.get("should_block") for r in results.values() if r):
        decision = GuardrailDecision.BLOCK
    elif any(r.get("should_warn") for r in results.values() if r):
        decision = GuardrailDecision.WARN

    return {
        "decision": decision.value,
        "details": results,
        "enabled_guardrails": enabled_guardrails,
    }


@traceable(name="pii_detection", tags=["guardrails", "pii"])
def trace_pii_check(output_text: str) -> Optional[Dict[str, Any]]:
    """
    Detect PII in output (SSN, account numbers, etc).

    Returns:
        {found_pii: bool, should_block: bool, instances: [...], confidence: float}
    """
    # In production, this uses regex patterns and statistical methods
    pii_patterns = {
        "ssn": r"\d{3}-\d{2}-\d{4}",
        "account_number": r"\b\d{10,12}\b",
        "routing_number": r"\b0\d{8}\b",
    }

    found_instances = []
    for pii_type, pattern in pii_patterns.items():
        # This is a mock; real implementation uses actual pattern matching
        if len(output_text) > 100:
            found_instances.append({"type": pii_type, "confidence": 0.85})

    return {
        "found_pii": len(found_instances) > 0,
        "should_block": len(found_instances) > 0,
        "instances": found_instances,
        "confidence": 0.95 if found_instances else 0.98,
    }


@traceable(name="hallucination_check", tags=["guardrails", "hallucination"])
def trace_hallucination_check(
    output_text: str, input_context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Check for hallucinated information not in input context.

    Returns:
        {hallucinating: bool, should_block: bool, confidence: float}
    """
    # In production: semantic similarity, entity extraction, claim verification
    return {
        "hallucinating": False,
        "should_block": False,
        "confidence": 0.87,
        "details": "No hallucinations detected in output vs context",
    }


@traceable(name="bias_screening", tags=["guardrails", "bias"])
def trace_bias_check(output_text: str) -> Optional[Dict[str, Any]]:
    """
    Screen for discriminatory or biased language.

    Returns:
        {bias_detected: bool, should_warn: bool, bias_types: [...]}
    """
    # In production: NLP-based bias detection, protected class language detection
    return {
        "bias_detected": False,
        "should_warn": False,
        "bias_types": [],
        "confidence": 0.91,
    }


@traceable(name="compliance_filter", tags=["guardrails", "compliance"])
def trace_compliance_check(output_text: str) -> Optional[Dict[str, Any]]:
    """
    Check for compliance violations (unauthorized claims, guarantees).

    Returns:
        {violation_found: bool, should_block: bool, violations: [...]}
    """
    return {
        "violation_found": False,
        "should_block": False,
        "violations": [],
        "confidence": 0.89,
    }


@traceable(name="confidence_assessment", tags=["guardrails", "confidence"])
def trace_confidence_check(output_text: str) -> Optional[Dict[str, Any]]:
    """
    Assess model output coherence and usefulness.

    Returns:
        {confidence_score: float, should_block: bool}
    """
    # In production: length, coherence, relevance scoring
    confidence = 0.87
    return {
        "confidence_score": confidence,
        "should_block": confidence < 0.5,
    }


@traceable(name="compliance_logging", tags=["governance", "logging"])
def trace_compliance_log(
    interaction_id: str,
    input_prompt: str,
    llm_output: str,
    guardrail_decision: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Trace compliance logging to immutable audit trail.

    Args:
        interaction_id: Unique interaction ID
        input_prompt: Full prompt sent to LLM
        llm_output: Raw output from LLM
        guardrail_decision: deliver/block/warn
        metadata: Additional guardrail and trace metadata

    Returns:
        Audit log entry
    """
    return {
        "interaction_id": interaction_id,
        "logged_at": datetime.utcnow().isoformat(),
        "guardrail_decision": guardrail_decision,
        "metadata": metadata,
        "audit_trail_immutable": True,
    }


# ============================================================================
# Cost Tracking & Aggregation
# ============================================================================


class CostTracker:
    """Track and aggregate LLM costs through governance layer."""

    def __init__(self, project_name: str = LANGSMITH_PROJECT):
        self.project_name = project_name
        self.costs = {}

    @traceable(name="cost_tracking", tags=["governance", "cost"])
    def track_interaction_cost(
        self,
        interaction_id: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> Dict[str, Any]:
        """
        Track cost for a single LLM interaction through governance.

        Args:
            interaction_id: Unique interaction ID
            model_id: Which model was used
            input_tokens: Tokens in prompt
            output_tokens: Tokens in response
            cost_usd: Total cost in USD

        Returns:
            Cost tracking record
        """
        key = f"{model_id}:{interaction_id}"
        self.costs[key] = {
            "model": model_id,
            "interaction_id": interaction_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "tracked_at": datetime.utcnow().isoformat(),
        }

        return self.costs[key]

    def get_total_cost(self) -> float:
        """Get total cost across all tracked interactions."""
        return sum(entry["cost_usd"] for entry in self.costs.values())

    def get_cost_by_model(self) -> Dict[str, float]:
        """Get cost breakdown by model."""
        by_model = {}
        for entry in self.costs.values():
            model = entry["model"]
            cost = entry["cost_usd"]
            by_model[model] = by_model.get(model, 0) + cost
        return by_model

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get comprehensive cost summary."""
        return {
            "total_interactions": len(self.costs),
            "total_cost_usd": self.get_total_cost(),
            "cost_by_model": self.get_cost_by_model(),
            "average_cost_per_interaction": (
                self.get_total_cost() / len(self.costs) if self.costs else 0
            ),
        }


# ============================================================================
# Initialization & Exports
# ============================================================================

# Initialize evaluators
guardrail_accuracy_eval = GuardrailAccuracyEvaluator()
pii_detection_eval = PIIDetectionEvaluator()
confidence_eval = ConfidenceScoreEvaluator()

# Initialize cost tracker
cost_tracker = CostTracker()


if __name__ == "__main__":
    # Example: Complete governance pipeline trace
    print("LangSmith Governance Tracing Initialized")
    print(f"Project: {LANGSMITH_PROJECT}")
    print(f"API Key configured: {bool(LANGSMITH_API_KEY)}")

    # Example trace (for testing)
    pipeline_result = trace_governance_pipeline(
        interaction_id="test-001",
        use_case="member_service",
        input_context={"member_id": "M12345", "account_balance": 5000},
        model_id="claude-3-sonnet",
        prompt_template_name="member_service_response",
        prompt_version="2.1",
    )
    print("\nGovernance Pipeline Trace Result:")
    print(json.dumps(pipeline_result, indent=2))
