"""
Prompt Registry — Versioned prompt template management for regulated GenAI.

The module that stopped an engineer from accidentally telling the LLM to
hallucinate account balances in production.

In unregulated environments, prompt engineering is casual. Engineers
tweak prompts in code, push to production, and iterate. In banking,
every prompt is effectively a model parameter — and under SR 11-7,
model parameter changes require documentation, review, and approval.

This registry treats prompts as versioned, auditable artifacts with
approval workflows. No prompt change reaches production without review.

Design principles:
- Every prompt version is immutable once created
- Every deployment requires explicit approval
- Every variable injection is validated against a schema
- Full version history is retained for regulatory examination
- A/B testing support for controlled prompt experiments
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional, Any
from collections import defaultdict
import re
import json
import hashlib


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PromptStatus(Enum):
    """Lifecycle status of a prompt version."""
    DRAFT = "draft"                # Being written, not yet submitted
    PENDING_REVIEW = "pending_review"  # Submitted for MRM review
    APPROVED = "approved"          # MRM signed off, can be deployed
    DEPLOYED = "deployed"          # Currently active in production
    DEPRECATED = "deprecated"      # Replaced by newer version
    REJECTED = "rejected"          # MRM rejected, needs revision


class UseCase(Enum):
    """Approved GenAI use cases."""
    CUSTOMER_SERVICE = "customer_service"
    DOCUMENT_SUMMARIZATION = "document_summarization"
    ADVISOR_BRIEFING = "advisor_briefing"
    INTERNAL_SEARCH = "internal_search"
    COMPLIANCE_REVIEW = "compliance_review"


class RiskTier(Enum):
    """Risk classification of the use case (determines approval rigor)."""
    TIER_1 = "tier_1"    # Customer-facing, decision-influencing (highest scrutiny)
    TIER_2 = "tier_2"    # Customer-facing, informational
    TIER_3 = "tier_3"    # Internal-only, productivity tool (lowest scrutiny)


class VariableType(Enum):
    """Types of variables that can be injected into prompts."""
    TEXT = "text"              # Free text (e.g., customer message)
    ACCOUNT_DATA = "account_data"    # Structured account info
    PII = "pii"                # Contains personally identifiable info
    FINANCIAL = "financial"    # Numbers, rates, balances
    SYSTEM = "system"          # System-generated context


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class PromptVariable:
    """A variable slot within a prompt template.

    Each variable has a type, validation rules, and PII classification.
    This ensures that the right data goes into the right slot and that
    PII is tracked throughout the pipeline.
    """
    name: str                      # e.g., "customer_message"
    variable_type: VariableType
    description: str
    required: bool = True
    max_length: Optional[int] = None
    contains_pii: bool = False
    validation_pattern: Optional[str] = None  # Regex for validation
    default_value: Optional[str] = None
    sanitize: bool = False         # Strip PII before injection


@dataclass
class PromptVersion:
    """A single immutable version of a prompt template.

    Once created, a version cannot be modified. Changes require
    creating a new version. This ensures auditability — regulators
    can see exactly what prompt was active at any point in time.
    """
    id: str                        # "cust_svc_v3.2"
    template_id: str               # Parent template ID
    version: str                   # "3.2"
    created_at: datetime
    created_by: str                # Engineer who wrote it
    status: PromptStatus

    # Content
    system_prompt: str
    user_prompt_template: str      # Contains {{variable}} placeholders
    variables: list[PromptVariable]

    # Model configuration
    model_id: str                  # "anthropic.claude-3-sonnet"
    temperature: float = 0.3
    max_tokens: int = 1024
    top_p: float = 0.9

    # Metadata
    use_case: UseCase = UseCase.CUSTOMER_SERVICE
    risk_tier: RiskTier = RiskTier.TIER_2
    description: str = ""
    change_reason: str = ""        # Why this version was created
    previous_version: Optional[str] = None

    # Guardrail configuration
    guardrails_enabled: list[str] = field(default_factory=lambda: [
        "pii_detection", "hallucination_check", "bias_screen",
        "compliance_filter", "confidence_assessment",
    ])

    # Approval tracking
    reviewer: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: str = ""
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: str = ""

    # Deployment tracking
    deployed_at: Optional[datetime] = None
    deployed_by: Optional[str] = None
    retired_at: Optional[datetime] = None

    # Testing results
    evaluation_score: Optional[float] = None
    evaluation_report_id: Optional[str] = None
    bias_test_passed: Optional[bool] = None

    # Integrity
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            content = self.system_prompt + self.user_prompt_template
            self.content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    @property
    def is_deployable(self) -> bool:
        return self.status == PromptStatus.APPROVED

    @property
    def is_active(self) -> bool:
        return self.status == PromptStatus.DEPLOYED

    @property
    def variable_names(self) -> list[str]:
        return [v.name for v in self.variables]

    @property
    def pii_variables(self) -> list[PromptVariable]:
        return [v for v in self.variables if v.contains_pii]


@dataclass
class PromptTemplate:
    """A prompt template with its full version history.

    Each template represents a single use case (e.g., "customer service
    response"). It contains all versions ever created, with exactly one
    version deployed at any time.
    """
    id: str                        # "cust_svc_response"
    name: str                      # "Member Service Response"
    use_case: UseCase
    risk_tier: RiskTier
    owner: str                     # Team or individual responsible
    created_at: datetime
    description: str

    versions: list[PromptVersion] = field(default_factory=list)

    @property
    def active_version(self) -> Optional[PromptVersion]:
        for v in self.versions:
            if v.status == PromptStatus.DEPLOYED:
                return v
        return None

    @property
    def latest_version(self) -> Optional[PromptVersion]:
        if not self.versions:
            return None
        return sorted(self.versions, key=lambda v: v.created_at)[-1]

    @property
    def version_count(self) -> int:
        return len(self.versions)

    @property
    def approval_rate(self) -> float:
        submitted = [
            v for v in self.versions
            if v.status != PromptStatus.DRAFT
        ]
        if not submitted:
            return 0.0
        approved = [
            v for v in submitted
            if v.status in (PromptStatus.APPROVED, PromptStatus.DEPLOYED, PromptStatus.DEPRECATED)
        ]
        return (len(approved) / len(submitted)) * 100


@dataclass
class RenderedPrompt:
    """A prompt with variables injected, ready to send to the LLM.

    This is the output of the rendering step. It includes the final
    prompt text plus metadata about what variables were injected and
    whether any contained PII.
    """
    template_id: str
    version_id: str
    rendered_at: datetime
    system_prompt: str
    user_prompt: str
    model_id: str
    temperature: float
    max_tokens: int

    # Variable tracking
    variables_injected: dict[str, str]  # variable_name -> value summary (PII redacted)
    pii_present: bool
    pii_variables_used: list[str]

    # Guardrail config
    guardrails_enabled: list[str]

    # Integrity
    render_hash: str = ""


@dataclass
class ABTest:
    """A/B test between two prompt versions."""
    id: str
    template_id: str
    variant_a: str                 # Version ID
    variant_b: str                 # Version ID
    traffic_split: float           # Fraction to variant B (0.0-1.0)
    start_date: datetime
    end_date: Optional[datetime] = None
    status: str = "active"         # "active", "completed", "cancelled"
    total_impressions_a: int = 0
    total_impressions_b: int = 0
    approved_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Prompt Registry
# ---------------------------------------------------------------------------

class PromptRegistry:
    """Manages all prompt templates and their versions.

    The central authority for what prompts are allowed in production.
    Every application-to-LLM interaction starts here.
    """

    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}
        self._ab_tests: list[ABTest] = []
        self._render_log: list[RenderedPrompt] = []

    # -- Template Management ------------------------------------------------

    def register_template(self, template: PromptTemplate) -> PromptTemplate:
        if template.id in self._templates:
            raise ValueError(f"Template '{template.id}' already registered.")
        self._templates[template.id] = template
        return template

    def get_template(self, template_id: str) -> PromptTemplate:
        if template_id not in self._templates:
            raise KeyError(f"Template '{template_id}' not found.")
        return self._templates[template_id]

    def list_templates(self) -> list[PromptTemplate]:
        return list(self._templates.values())

    # -- Version Management -------------------------------------------------

    def create_version(
        self,
        template_id: str,
        version: PromptVersion,
    ) -> PromptVersion:
        """Create a new version of an existing template."""
        template = self.get_template(template_id)

        # Validate version doesn't duplicate
        existing = [v.version for v in template.versions]
        if version.version in existing:
            raise ValueError(
                f"Version '{version.version}' already exists for template '{template_id}'."
            )

        # Validate variables in template match declared variables
        placeholders = set(re.findall(r'\{\{(\w+)\}\}', version.user_prompt_template))
        declared = set(v.name for v in version.variables)
        missing = placeholders - declared
        if missing:
            raise ValueError(
                f"Template contains undeclared variables: {missing}"
            )

        template.versions.append(version)
        return version

    def submit_for_review(self, template_id: str, version_id: str) -> PromptVersion:
        """Submit a draft version for MRM review."""
        version = self._get_version(template_id, version_id)
        if version.status != PromptStatus.DRAFT:
            raise ValueError(f"Only draft versions can be submitted. Current status: {version.status.value}")
        version.status = PromptStatus.PENDING_REVIEW
        return version

    def approve_version(
        self,
        template_id: str,
        version_id: str,
        approved_by: str,
        notes: str = "",
        evaluation_score: Optional[float] = None,
        bias_test_passed: Optional[bool] = None,
    ) -> PromptVersion:
        """MRM approves a version for deployment."""
        version = self._get_version(template_id, version_id)
        if version.status != PromptStatus.PENDING_REVIEW:
            raise ValueError(f"Only pending versions can be approved. Current: {version.status.value}")

        version.status = PromptStatus.APPROVED
        version.approved_by = approved_by
        version.approved_at = datetime.now()
        version.approval_notes = notes
        version.evaluation_score = evaluation_score
        version.bias_test_passed = bias_test_passed
        return version

    def reject_version(
        self,
        template_id: str,
        version_id: str,
        rejected_by: str,
        reason: str,
    ) -> PromptVersion:
        """MRM rejects a version."""
        version = self._get_version(template_id, version_id)
        version.status = PromptStatus.REJECTED
        version.reviewer = rejected_by
        version.reviewed_at = datetime.now()
        version.review_notes = reason
        return version

    def deploy_version(
        self,
        template_id: str,
        version_id: str,
        deployed_by: str,
    ) -> PromptVersion:
        """Deploy an approved version (and retire the current active one)."""
        template = self.get_template(template_id)
        version = self._get_version(template_id, version_id)

        if version.status != PromptStatus.APPROVED:
            raise ValueError(f"Only approved versions can be deployed. Current: {version.status.value}")

        # Retire current active version
        current = template.active_version
        if current:
            current.status = PromptStatus.DEPRECATED
            current.retired_at = datetime.now()

        version.status = PromptStatus.DEPLOYED
        version.deployed_at = datetime.now()
        version.deployed_by = deployed_by
        return version

    # -- Prompt Rendering ---------------------------------------------------

    def render(
        self,
        template_id: str,
        variables: dict[str, str],
        version_override: Optional[str] = None,
    ) -> RenderedPrompt:
        """Render a prompt template with injected variables.

        This is the main method called by applications. It:
        1. Finds the active version (or overridden version)
        2. Validates all required variables are provided
        3. Validates variable values against schemas
        4. Injects variables into the template
        5. Returns the rendered prompt ready for the LLM
        """
        template = self.get_template(template_id)

        # Select version
        if version_override:
            version = self._get_version(template_id, version_override)
        else:
            # Check for active A/B test
            ab_version = self._get_ab_test_version(template_id)
            if ab_version:
                version = ab_version
            else:
                version = template.active_version

        if not version:
            raise ValueError(f"No active version found for template '{template_id}'.")

        if version.status not in (PromptStatus.DEPLOYED, PromptStatus.APPROVED):
            raise ValueError(f"Version '{version.id}' is not deployable (status: {version.status.value}).")

        # Validate required variables
        for var in version.variables:
            if var.required and var.name not in variables:
                if var.default_value is not None:
                    variables[var.name] = var.default_value
                else:
                    raise ValueError(f"Required variable '{var.name}' not provided.")

        # Validate variable values
        for var in version.variables:
            if var.name in variables:
                value = variables[var.name]

                if var.max_length and len(value) > var.max_length:
                    raise ValueError(
                        f"Variable '{var.name}' exceeds max length ({len(value)} > {var.max_length})."
                    )

                if var.validation_pattern:
                    if not re.match(var.validation_pattern, value):
                        raise ValueError(
                            f"Variable '{var.name}' fails validation pattern."
                        )

        # Render the user prompt
        rendered_user = version.user_prompt_template
        for var_name, value in variables.items():
            rendered_user = rendered_user.replace(f"{{{{{var_name}}}}}", value)

        # Track PII
        pii_vars = [
            v.name for v in version.variables
            if v.contains_pii and v.name in variables
        ]

        # Build redacted variable summary for logging (never log raw PII)
        var_summary = {}
        for var_name, value in variables.items():
            var_def = next((v for v in version.variables if v.name == var_name), None)
            if var_def and var_def.contains_pii:
                var_summary[var_name] = f"[PII - {len(value)} chars]"
            else:
                var_summary[var_name] = value[:100] + "..." if len(value) > 100 else value

        rendered = RenderedPrompt(
            template_id=template_id,
            version_id=version.id,
            rendered_at=datetime.now(),
            system_prompt=version.system_prompt,
            user_prompt=rendered_user,
            model_id=version.model_id,
            temperature=version.temperature,
            max_tokens=version.max_tokens,
            variables_injected=var_summary,
            pii_present=len(pii_vars) > 0,
            pii_variables_used=pii_vars,
            guardrails_enabled=version.guardrails_enabled,
            render_hash=hashlib.sha256(rendered_user.encode()).hexdigest()[:16],
        )

        self._render_log.append(rendered)
        return rendered

    # -- A/B Testing --------------------------------------------------------

    def create_ab_test(self, test: ABTest) -> ABTest:
        template = self.get_template(test.template_id)
        va = self._get_version(test.template_id, test.variant_a)
        vb = self._get_version(test.template_id, test.variant_b)

        if va.status not in (PromptStatus.APPROVED, PromptStatus.DEPLOYED):
            raise ValueError(f"Variant A must be approved or deployed.")
        if vb.status not in (PromptStatus.APPROVED, PromptStatus.DEPLOYED):
            raise ValueError(f"Variant B must be approved or deployed.")

        self._ab_tests.append(test)
        return test

    def _get_ab_test_version(self, template_id: str) -> Optional[PromptVersion]:
        """Check if there's an active A/B test and return the selected version."""
        active_tests = [
            t for t in self._ab_tests
            if t.template_id == template_id and t.status == "active"
        ]
        if not active_tests:
            return None

        test = active_tests[0]
        # Simple deterministic split based on render count
        total = test.total_impressions_a + test.total_impressions_b
        if total == 0 or (test.total_impressions_b / max(total, 1)) < test.traffic_split:
            test.total_impressions_b += 1
            return self._get_version(template_id, test.variant_b)
        else:
            test.total_impressions_a += 1
            return self._get_version(template_id, test.variant_a)

    # -- Helpers ------------------------------------------------------------

    def _get_version(self, template_id: str, version_id: str) -> PromptVersion:
        template = self.get_template(template_id)
        for v in template.versions:
            if v.id == version_id:
                return v
        raise KeyError(f"Version '{version_id}' not found in template '{template_id}'.")

    # -- Registry Summary ---------------------------------------------------

    def get_registry_summary(self) -> dict:
        templates = list(self._templates.values())
        all_versions = [v for t in templates for v in t.versions]

        return {
            "total_templates": len(templates),
            "total_versions": len(all_versions),
            "active_deployments": len([v for v in all_versions if v.status == PromptStatus.DEPLOYED]),
            "pending_review": len([v for v in all_versions if v.status == PromptStatus.PENDING_REVIEW]),
            "rejected": len([v for v in all_versions if v.status == PromptStatus.REJECTED]),
            "active_ab_tests": len([t for t in self._ab_tests if t.status == "active"]),
            "total_renders": len(self._render_log),
            "renders_with_pii": len([r for r in self._render_log if r.pii_present]),
            "templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "use_case": t.use_case.value,
                    "risk_tier": t.risk_tier.value,
                    "active_version": t.active_version.version if t.active_version else None,
                    "total_versions": t.version_count,
                    "approval_rate": round(t.approval_rate, 1),
                }
                for t in templates
            ],
        }


# ---------------------------------------------------------------------------
# Usage Example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    registry = PromptRegistry()

    # Register a member service response template
    template = PromptTemplate(
        id="cust_svc_response",
        name="Member Service Response",
        use_case=UseCase.CUSTOMER_SERVICE,
        risk_tier=RiskTier.TIER_2,
        owner="Digital Transformation Team",
        created_at=datetime.now() - timedelta(days=60),
        description="Generates draft responses to member inquiries in the service center.",
    )
    registry.register_template(template)

    # Create version 3.1 (currently deployed)
    v31 = PromptVersion(
        id="cust_svc_v3.1",
        template_id="cust_svc_response",
        version="3.1",
        created_at=datetime.now() - timedelta(days=30),
        created_by="Alex Kim",
        status=PromptStatus.DEPLOYED,
        system_prompt=(
            "You are a helpful member service assistant for a credit union. "
            "Answer member questions accurately and professionally. "
            "Only reference account details that are explicitly provided in the context below. "
            "Never fabricate account numbers, balances, transaction details, or interest rates. "
            "If you don't have the information to answer a question, say so and offer to "
            "connect the member with a specialist. "
            "Do not provide financial advice or make product recommendations. "
            "Do not reference competitor products or services. "
            "Maintain a warm, professional tone consistent with the credit union's member-first values."
        ),
        user_prompt_template=(
            "Member name: {{customer_name}}\n"
            "Account type: {{account_type}}\n"
            "Account context: {{account_context}}\n\n"
            "Member message: {{customer_message}}\n\n"
            "Draft a response to the member's message. Reference only the account "
            "details provided above. If the question requires information not included "
            "in the context, indicate that you'll need to look into it further."
        ),
        variables=[
            PromptVariable("customer_name", VariableType.PII,
                           "Member's full name", contains_pii=True, max_length=100),
            PromptVariable("account_type", VariableType.ACCOUNT_DATA,
                           "Account type (checking, savings, credit card, etc.)"),
            PromptVariable("account_context", VariableType.ACCOUNT_DATA,
                           "Relevant account details for this inquiry",
                           max_length=2000, contains_pii=True),
            PromptVariable("customer_message", VariableType.TEXT,
                           "The member's message", max_length=5000),
        ],
        model_id="anthropic.claude-3-sonnet",
        temperature=0.3,
        max_tokens=1024,
        use_case=UseCase.CUSTOMER_SERVICE,
        risk_tier=RiskTier.TIER_2,
        description="Production member service response prompt v3.1",
        approved_by="Maria Chen (MRM Analyst)",
        approved_at=datetime.now() - timedelta(days=28),
        deployed_at=datetime.now() - timedelta(days=27),
        deployed_by="Alex Kim",
        evaluation_score=87.3,
        bias_test_passed=True,
    )
    registry.create_version("cust_svc_response", v31)

    # Create version 3.2 (pending review — the one that almost went wrong)
    v32 = PromptVersion(
        id="cust_svc_v3.2",
        template_id="cust_svc_response",
        version="3.2",
        created_at=datetime.now() - timedelta(days=3),
        created_by="James Park",
        status=PromptStatus.PENDING_REVIEW,
        system_prompt=(
            "You are a helpful member service assistant for a credit union. "
            "Answer member questions accurately and professionally. "
            "Reference only account details provided in the context below. "
            "Never fabricate account numbers, balances, transaction details, or interest rates. "
            "When the member asks about their account, provide specific details from the context "
            "to give a personalized, helpful response. "
            "If you don't have the information to answer, say so and offer to connect with a specialist. "
            "Do not provide financial advice or make product recommendations. "
            "Maintain a warm, professional tone consistent with the credit union's member-first values."
        ),
        user_prompt_template=(
            "Member name: {{customer_name}}\n"
            "Account type: {{account_type}}\n"
            "Account context: {{account_context}}\n\n"
            "Recent transactions (last 30 days): {{recent_transactions}}\n\n"
            "Member message: {{customer_message}}\n\n"
            "Draft a personalized response referencing their specific account activity "
            "where relevant."
        ),
        variables=[
            PromptVariable("customer_name", VariableType.PII,
                           "Member's full name", contains_pii=True, max_length=100),
            PromptVariable("account_type", VariableType.ACCOUNT_DATA,
                           "Account type"),
            PromptVariable("account_context", VariableType.ACCOUNT_DATA,
                           "Account details", max_length=2000, contains_pii=True),
            PromptVariable("recent_transactions", VariableType.FINANCIAL,
                           "Recent transaction summary", max_length=3000,
                           contains_pii=True, required=False, default_value="Not available"),
            PromptVariable("customer_message", VariableType.TEXT,
                           "Customer's message", max_length=5000),
        ],
        model_id="anthropic.claude-3-sonnet",
        temperature=0.3,
        max_tokens=1024,
        use_case=UseCase.CUSTOMER_SERVICE,
        risk_tier=RiskTier.TIER_2,
        description="Added transaction context for more personalized responses",
        change_reason="Customer satisfaction scores suggested responses were too generic",
        previous_version="cust_svc_v3.1",
    )
    registry.create_version("cust_svc_response", v32)

    # Render the active version
    rendered = registry.render("cust_svc_response", {
        "customer_name": "Maria Torres",
        "account_type": "Checking",
        "account_context": "Balance: $4,523.18. Last deposit: $2,800 on 2/28. Pending: $45.99 Amazon.",
        "customer_message": "Hi, I noticed a charge I don't recognize on my account. Can you help?",
    })

    # Print results
    print("=== PROMPT REGISTRY ===\n")
    summary = registry.get_registry_summary()
    print(f"Templates: {summary['total_templates']}")
    print(f"Versions: {summary['total_versions']}")
    print(f"Active deployments: {summary['active_deployments']}")
    print(f"Pending review: {summary['pending_review']}")

    for t in summary["templates"]:
        print(f"\n  Template: {t['name']}")
        print(f"  Use case: {t['use_case']} | Risk: {t['risk_tier']}")
        print(f"  Active version: {t['active_version']}")
        print(f"  Total versions: {t['total_versions']} | Approval rate: {t['approval_rate']}%")

    print(f"\n=== RENDERED PROMPT ===\n")
    print(f"Template: {rendered.template_id}")
    print(f"Version: {rendered.version_id}")
    print(f"Model: {rendered.model_id}")
    print(f"PII present: {rendered.pii_present}")
    print(f"PII variables: {rendered.pii_variables_used}")
    print(f"Guardrails: {rendered.guardrails_enabled}")
    print(f"\nSystem prompt:\n{rendered.system_prompt[:200]}...")
    print(f"\nUser prompt:\n{rendered.user_prompt[:200]}...")
    print(f"\nVariables (redacted):")
    for k, v in rendered.variables_injected.items():
        print(f"  {k}: {v}")
