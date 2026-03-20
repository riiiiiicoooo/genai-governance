"""
Token Cost Optimizer — Economic awareness layer for GenAI governance.

In regulated industries, compliance costs are unavoidable. But the cost
of a guardrail check that rarely triggers (e.g., Presidio NLP scanning
FAQ routing) is a waste. This module applies tiered, risk-based optimization:

- Low-risk use cases (FAQ, simple routing): skip expensive NLP checks
- High-risk use cases (financial advice, decision-influencing): full pipeline
- Per-template token budgeting: compress prompts if they exceed efficiency threshold
- Model downgrade recommendations: use Haiku for simple tasks, Sonnet for complex ones
- Monthly cost projection: show exact ROI of optimization choices

Design principles:
- NEVER sacrifice compliance for cost (regulatory guardrails are non-negotiable)
- AGGRESSIVELY optimize non-compliance paths
- Make token economics visible to product teams
- Quantify the cost of guardrail choices explicitly
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from collections import defaultdict
import math


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskLevel(Enum):
    """Risk classification determines guardrail intensity."""
    LOW = "low"           # FAQ, simple routing, non-financial info
    MEDIUM = "medium"     # Informational customer-facing
    HIGH = "high"         # Financial decisions, account actions, legal impact


class ModelTier(Enum):
    """LLM model families for cost/quality tradeoff."""
    HAIKU = "claude_3_haiku"           # $0.25/$1.25 per 1M tokens (5-7s latency)
    SONNET = "claude_3_sonnet"         # $3/$15 per 1M tokens (2-3s latency)
    OPUS = "claude_3_opus"             # $15/$75 per 1M tokens (4-6s latency)
    GPT_4O_MINI = "gpt_4o_mini"       # $0.15/$0.60 per 1M tokens
    GPT_4O = "gpt_4o"                  # $5/$15 per 1M tokens


class GuardrailTier(Enum):
    """Guardrail pipeline intensity."""
    LITE = "lite"           # Basic regex patterns only
    STANDARD = "standard"   # Regex + pattern libraries
    FULL = "full"           # Regex + Presidio NLP + all checks


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ModelPrice:
    """Pricing for an LLM model."""
    model_id: str
    provider: str  # "bedrock", "azure", "openai", etc.
    input_cost_per_1m: float      # Cost per 1M input tokens
    output_cost_per_1m: float     # Cost per 1M output tokens
    typical_latency_ms: int       # P50 latency in milliseconds
    supports_streaming: bool = True
    max_tokens: int = 4096


@dataclass
class PromptMetrics:
    """Metrics captured for a prompt template."""
    template_id: str
    rendered_token_count: int
    system_tokens: int
    user_tokens: int
    typical_completion_tokens: int  # Based on historical avg
    use_case_risk_level: RiskLevel
    daily_interactions: int = 0
    recommended_model: Optional[ModelTier] = None


@dataclass
class GuardrailCostBreakdown:
    """Cost of guardrail pipeline for a given use case."""
    risk_level: RiskLevel
    tier: GuardrailTier
    presidio_cost_per_call: float = 0.0  # Compute cost if using NLP
    pattern_check_cost_per_call: float = 0.0
    total_monthly_cost: float = 0.0
    tokens_saved_by_lite_mode: int = 0
    monthly_savings_vs_full: float = 0.0


@dataclass
class CostProjection:
    """Monthly cost estimate for a specific configuration."""
    template_id: str
    model: ModelTier
    guardrail_tier: GuardrailTier
    daily_interactions: int
    avg_input_tokens: int
    avg_output_tokens: int
    monthly_input_cost: float = 0.0
    monthly_output_cost: float = 0.0
    monthly_guardrail_cost: float = 0.0
    total_monthly_cost: float = 0.0
    cost_per_interaction: float = 0.0


@dataclass
class ModelDowngradeRecommendation:
    """Recommendation to downgrade from current model to cheaper alternative."""
    use_case: str
    current_model: ModelTier
    recommended_model: ModelTier
    quality_delta_risk: str  # "none", "low", "medium", "high"
    estimated_monthly_savings: float
    reasoning: str
    historical_performance: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Main Optimizer Class
# ---------------------------------------------------------------------------

class TokenCostOptimizer:
    """
    Manages model pricing, token budgets, guardrail costs, and model selection.

    This is the economic nervous system of GenAI governance: it translates
    regulatory requirements (use guardrails) into cost-optimized execution
    (guardrails only where needed).
    """

    def __init__(self):
        """Initialize the optimizer with standard model pricing."""
        self.model_registry: Dict[ModelTier, ModelPrice] = self._initialize_models()
        self.template_budgets: Dict[str, PromptMetrics] = {}
        self.guardrail_costs: Dict[RiskLevel, GuardrailCostBreakdown] = {}
        self.cost_history: List[CostProjection] = []
        self.model_downgrade_history: List[ModelDowngradeRecommendation] = []
        self._initialize_guardrail_costs()

    def _initialize_models(self) -> Dict[ModelTier, ModelPrice]:
        """Set up model pricing registry (Q1 2026 public pricing)."""
        return {
            ModelTier.HAIKU: ModelPrice(
                model_id="claude-3-haiku-20250307",
                provider="bedrock",
                input_cost_per_1m=0.25,
                output_cost_per_1m=1.25,
                typical_latency_ms=800,
            ),
            ModelTier.SONNET: ModelPrice(
                model_id="claude-3-5-sonnet-20241022",
                provider="bedrock",
                input_cost_per_1m=3.0,
                output_cost_per_1m=15.0,
                typical_latency_ms=300,
            ),
            ModelTier.OPUS: ModelPrice(
                model_id="claude-3-opus-20250219",
                provider="bedrock",
                input_cost_per_1m=15.0,
                output_cost_per_1m=75.0,
                typical_latency_ms=600,
            ),
            ModelTier.GPT_4O_MINI: ModelPrice(
                model_id="gpt-4o-mini",
                provider="azure",
                input_cost_per_1m=0.15,
                output_cost_per_1m=0.60,
                typical_latency_ms=500,
            ),
            ModelTier.GPT_4O: ModelPrice(
                model_id="gpt-4o",
                provider="azure",
                input_cost_per_1m=5.0,
                output_cost_per_1m=15.0,
                typical_latency_ms=400,
            ),
        }

    def _initialize_guardrail_costs(self) -> None:
        """
        Set up guardrail cost profiles by risk level.

        Presidio NLP scanning costs ~$0.001-0.002 per call (on-prem compute).
        Pattern checking costs negligible.
        Full pipeline overhead: ~5-8% of LLM token cost.
        """
        self.guardrail_costs = {
            RiskLevel.LOW: GuardrailCostBreakdown(
                risk_level=RiskLevel.LOW,
                tier=GuardrailTier.LITE,
                presidio_cost_per_call=0.0,  # Skip Presidio for low-risk
                pattern_check_cost_per_call=0.00001,
                monthly_savings_vs_full=0.0008,  # Baseline
            ),
            RiskLevel.MEDIUM: GuardrailCostBreakdown(
                risk_level=RiskLevel.MEDIUM,
                tier=GuardrailTier.STANDARD,
                presidio_cost_per_call=0.0005,
                pattern_check_cost_per_call=0.00002,
                monthly_savings_vs_full=0.0004,
            ),
            RiskLevel.HIGH: GuardrailCostBreakdown(
                risk_level=RiskLevel.HIGH,
                tier=GuardrailTier.FULL,
                presidio_cost_per_call=0.0015,
                pattern_check_cost_per_call=0.00003,
                monthly_savings_vs_full=0.0,  # Full pipeline, no savings
            ),
        }

    # -----------------------------------------------------------------------
    # Core Optimization Methods
    # -----------------------------------------------------------------------

    def optimize_prompt(
        self,
        template_id: str,
        rendered_prompt: str,
        risk_level: RiskLevel,
        compression_threshold_tokens: int = 2000,
    ) -> Tuple[bool, Optional[str], PromptMetrics]:
        """
        Analyze a rendered prompt and suggest compression if needed.

        Args:
            template_id: Unique identifier for this prompt template
            rendered_prompt: The full rendered prompt (system + user)
            risk_level: Risk classification for guardrail purposes
            compression_threshold_tokens: Alert if exceeds this (default 2000)

        Returns:
            Tuple of:
            - needs_compression: bool
            - compression_suggestion: str or None
            - PromptMetrics: detailed metrics about the prompt

        Rationale:
        Longer prompts = more input tokens = higher cost and latency.
        But we never compress compliance-critical context (e.g., risk disclaimers).
        For non-critical scaffolding (examples, context filler), we suggest:
        - Few-shot examples: reduce from 5 to 2
        - Verbose instructions: use token-count-aware rephrasing
        - Redundant context: deduplicate
        """
        # Approximate token count (actual tokenizer should be used in prod)
        estimated_tokens = len(rendered_prompt) // 4
        system_tokens = len(rendered_prompt.split("---")[0]) // 4 if "---" in rendered_prompt else estimated_tokens // 3
        user_tokens = estimated_tokens - system_tokens

        metrics = PromptMetrics(
            template_id=template_id,
            rendered_token_count=estimated_tokens,
            system_tokens=system_tokens,
            user_tokens=user_tokens,
            typical_completion_tokens=500,  # Domain avg
            use_case_risk_level=risk_level,
        )

        needs_compression = estimated_tokens > compression_threshold_tokens
        suggestion = None

        if needs_compression:
            if "example" in rendered_prompt.lower():
                suggestion = (
                    f"Prompt exceeds {compression_threshold_tokens} tokens ({estimated_tokens} actual). "
                    "Consider: (1) Reduce few-shot examples from 5 to 2. "
                    "(2) Shorten verbose instructions. "
                    "(3) Deduplicate context. "
                    f"Potential savings: ~{(estimated_tokens - compression_threshold_tokens) * 30 / 1_000_000:.4f} "
                    "USD per 10K interactions."
                )
            else:
                suggestion = (
                    f"Prompt at {estimated_tokens} tokens (threshold {compression_threshold_tokens}). "
                    "Review for unnecessary verbosity. "
                )

        self.template_budgets[template_id] = metrics
        return needs_compression, suggestion, metrics

    def select_guardrail_tier(self, use_case_risk_level: RiskLevel) -> GuardrailTier:
        """
        Select guardrail intensity based on risk level.

        Args:
            use_case_risk_level: Risk classification of the use case

        Returns:
            GuardrailTier to apply

        Logic:
        - LOW: Skip Presidio NLP (expensive), use regex only
        - MEDIUM: Run pattern libraries + selective Presidio
        - HIGH: Full pipeline (Presidio NLP + all checks)

        This is the core cost-vs-compliance tradeoff: we never compromise
        compliance guardrails, but we ruthlessly optimize non-critical paths.

        Example:
        - FAQ routing (LOW risk): Does this match "account_balance" pattern? → LITE
        - Customer service (MEDIUM risk): Look for PII mentions → STANDARD
        - Loan approval (HIGH risk): Full Presidio scan, bias detection → FULL
        """
        return self.guardrail_costs[use_case_risk_level].tier

    def estimate_monthly_cost(
        self,
        daily_interactions: int,
        avg_input_tokens: int,
        avg_output_tokens: int,
        model: ModelTier,
        risk_level: RiskLevel,
    ) -> CostProjection:
        """
        Project monthly cost for a use case.

        Args:
            daily_interactions: Expected daily volume
            avg_input_tokens: Average input token count per interaction
            avg_output_tokens: Average output token count per interaction
            model: Which model to use
            risk_level: For guardrail cost estimation

        Returns:
            CostProjection with detailed monthly breakdown

        Formula:
        - LLM cost = (daily * 30) * (input_tokens * input_rate + output_tokens * output_rate) / 1M
        - Guardrail cost = daily * 30 * guardrail_cost_per_call
        - Total = LLM + guardrail

        Example:
        - 1000 daily interactions
        - 500 input, 200 output tokens
        - Sonnet ($3/$15 per 1M)
        - Monthly LLM cost = 30K * (500 * 3 + 200 * 15) / 1M = $63
        - MEDIUM risk STANDARD tier = ~$1.50
        - Total ≈ $64.50/month
        """
        model_price = self.model_registry[model]
        guardrail_cost = self.guardrail_costs[risk_level]

        monthly_interactions = daily_interactions * 30

        # LLM token costs
        input_cost = (monthly_interactions * avg_input_tokens * model_price.input_cost_per_1m) / 1_000_000
        output_cost = (monthly_interactions * avg_output_tokens * model_price.output_cost_per_1m) / 1_000_000

        # Guardrail costs
        total_guardrail_cost_per_call = (
            guardrail_cost.presidio_cost_per_call + guardrail_cost.pattern_check_cost_per_call
        )
        guardrail_cost_total = monthly_interactions * total_guardrail_cost_per_call

        total_cost = input_cost + output_cost + guardrail_cost_total
        cost_per_interaction = total_cost / monthly_interactions if monthly_interactions > 0 else 0

        projection = CostProjection(
            template_id="",  # Will be set by caller if needed
            model=model,
            guardrail_tier=guardrail_cost.tier,
            daily_interactions=daily_interactions,
            avg_input_tokens=avg_input_tokens,
            avg_output_tokens=avg_output_tokens,
            monthly_input_cost=input_cost,
            monthly_output_cost=output_cost,
            monthly_guardrail_cost=guardrail_cost_total,
            total_monthly_cost=total_cost,
            cost_per_interaction=cost_per_interaction,
        )

        self.cost_history.append(projection)
        return projection

    def recommend_model_downgrade(
        self,
        use_case: str,
        current_model: ModelTier,
        daily_interactions: int,
        avg_input_tokens: int,
        avg_output_tokens: int,
        quality_thresholds: Optional[Dict[str, float]] = None,
    ) -> Optional[ModelDowngradeRecommendation]:
        """
        Suggest a cheaper model if quality delta is acceptable.

        Args:
            use_case: Name of the use case (e.g., "FAQ routing")
            current_model: Currently deployed model
            daily_interactions: Daily volume
            avg_input_tokens: Average input length
            avg_output_tokens: Average output length
            quality_thresholds: Dict of metric -> min_acceptable_score

        Returns:
            ModelDowngradeRecommendation if a downgrade is advisable, else None

        Strategy:
        For simple tasks (FAQ routing, classification), Haiku is 12x cheaper
        than Sonnet with <2% quality loss. For complex tasks (reasoning,
        novel synthesis), Opus may be necessary.

        Example:
        - FAQ routing is 95% exact-match classification
        - Haiku: 96% accuracy (vs Sonnet 97%)
        - Monthly savings: $180 at 10K daily interactions
        - Recommendation: YES, downgrade to Haiku

        - Complex advisory is novel synthesis + nuance
        - Haiku: 71% acceptable (vs Sonnet 93%)
        - Monthly savings: $180
        - Recommendation: NO, quality risk too high
        """
        current_cost = self.estimate_monthly_cost(
            daily_interactions, avg_input_tokens, avg_output_tokens, current_model, RiskLevel.MEDIUM
        )

        candidates = [m for m in ModelTier if m.value < current_model.value]
        if not candidates:
            return None

        best_downgrade = None

        for candidate_model in sorted(candidates, key=lambda x: self.model_registry[x].input_cost_per_1m, reverse=True):
            candidate_cost = self.estimate_monthly_cost(
                daily_interactions, avg_input_tokens, avg_output_tokens, candidate_model, RiskLevel.MEDIUM
            )

            monthly_savings = current_cost.total_monthly_cost - candidate_cost.total_monthly_cost

            # Heuristic quality assessment (in production, use actual metrics)
            quality_risk = "low"
            reasoning = f"Downgrade from {current_model.value} to {candidate_model.value}. "

            if use_case.lower() in ["faq", "routing", "classification", "simple"]:
                quality_risk = "none"
                reasoning += "Use case is deterministic classification; model choice has minimal impact."
            elif use_case.lower() in ["summarization", "extraction"]:
                quality_risk = "low"
                reasoning += "Summarization benefits from better models, but Haiku/mini are 90%+ effective."
            elif use_case.lower() in ["reasoning", "decision", "complex"]:
                quality_risk = "medium"
                reasoning += "Complex reasoning benefits from larger models. Downgrade should be validated."

            reasoning += f" Estimated savings: ${monthly_savings:.2f}/month."

            recommendation = ModelDowngradeRecommendation(
                use_case=use_case,
                current_model=current_model,
                recommended_model=candidate_model,
                quality_delta_risk=quality_risk,
                estimated_monthly_savings=monthly_savings,
                reasoning=reasoning,
                historical_performance=None,
            )

            # Accept first viable downgrade (largest savings with acceptable quality)
            if quality_risk != "high" and monthly_savings > 10:
                best_downgrade = recommendation
                break

        if best_downgrade:
            self.model_downgrade_history.append(best_downgrade)

        return best_downgrade

    def get_cost_dashboard(self) -> Dict[str, Any]:
        """
        Return comprehensive cost breakdown across all templates and models.

        Returns:
            Dict with:
            - per_template_costs: costs by template ID
            - per_model_costs: aggregate costs by model
            - per_use_case_costs: aggregate by risk level
            - optimization_opportunities: list of recommendations
            - monthly_total: overall monthly projection

        This is what the CFO and product teams see to understand economic
        impact of GenAI deployments.
        """
        per_template = defaultdict(lambda: {"input": 0.0, "output": 0.0, "guardrail": 0.0, "total": 0.0})
        per_model = defaultdict(lambda: {"input": 0.0, "output": 0.0, "guardrail": 0.0, "total": 0.0})
        per_use_case = defaultdict(lambda: {"input": 0.0, "output": 0.0, "guardrail": 0.0, "total": 0.0})

        for projection in self.cost_history:
            # Per-template breakdown (if template_id set)
            if projection.template_id:
                per_template[projection.template_id]["input"] += projection.monthly_input_cost
                per_template[projection.template_id]["output"] += projection.monthly_output_cost
                per_template[projection.template_id]["guardrail"] += projection.monthly_guardrail_cost
                per_template[projection.template_id]["total"] += projection.total_monthly_cost

            # Per-model breakdown
            model_key = projection.model.value
            per_model[model_key]["input"] += projection.monthly_input_cost
            per_model[model_key]["output"] += projection.monthly_output_cost
            per_model[model_key]["guardrail"] += projection.monthly_guardrail_cost
            per_model[model_key]["total"] += projection.total_monthly_cost

        monthly_total = sum(p.total_monthly_cost for p in self.cost_history)

        return {
            "per_template_costs": dict(per_template),
            "per_model_costs": dict(per_model),
            "optimization_opportunities": [
                {
                    "title": rec.reasoning,
                    "estimated_savings": f"${rec.estimated_monthly_savings:.2f}/month",
                    "risk": rec.quality_delta_risk,
                }
                for rec in self.model_downgrade_history
            ],
            "monthly_total": f"${monthly_total:.2f}",
            "cost_history_count": len(self.cost_history),
        }
