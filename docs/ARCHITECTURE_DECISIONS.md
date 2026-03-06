# Architecture Decision Records

Significant technical decisions made during the design and implementation of the GenAI Governance Platform. Each ADR captures the context, rationale, alternatives considered, and consequences of a key architectural choice.

---

## ADR-001: Deterministic Guardrail Engine Without LLM-in-the-Loop

**Status:** Accepted
**Date:** 2025-11-15

### Context

The platform screens every LLM output before it reaches a credit union member. A critical design question was whether guardrail checks should themselves invoke an LLM (e.g., asking GPT-4 to classify whether output contains PII) or use deterministic, rule-based analysis (regex patterns, keyword matching, statistical heuristics).

In a regulated financial institution, guardrails must be explainable to examiners, produce consistent results across identical inputs, and execute within strict latency budgets. NCUA and OCC examiners expect the institution to articulate *why* a given output was blocked -- "the classifier said so" is insufficient under SR 11-7 model risk guidance.

### Decision

Implement all five guardrail checks (PII detection, hallucination check, bias screen, compliance filter, confidence assessment) as deterministic, stateless functions with no LLM calls. Each check returns structured findings with explicit pattern matches, confidence scores, and human-readable explanations.

The `GuardrailEngine` in `src/output_guardrails.py` orchestrates five checks:
- **PIIDetector**: Regex patterns for SSN, account numbers, credit cards, routing numbers, DOB, email, and phone. Context-aware comparison against input to distinguish PII leakage from PII echo.
- **HallucinationDetector**: Extracts financial figures (dollar amounts, percentages, rates) from output and verifies each against the input context. Ungrounded figures trigger a block.
- **BiasScreener**: Pattern matching for prohibited phrases (steering language, discriminatory references), warning patterns (negative framing, deflection), and structural analysis (response length disparity).
- **ComplianceFilter**: Detects financial advice language, guarantee/promise patterns, rate commitments, and competitor references that violate regulatory boundaries.
- **ConfidenceAssessor**: Scores output 0-100 based on refusal detection, length adequacy, repetition analysis, and code block presence. Low confidence triggers review.

### Alternatives Considered

1. **LLM-based classification** (e.g., GPT-4 or Claude as a guardrail judge): Higher accuracy on nuanced cases but introduces non-determinism, adds 500-2000ms latency per check, creates recursive model risk (the guardrail itself becomes a model requiring SR 11-7 validation), and doubles inference costs.

2. **Hybrid approach** (deterministic first pass, LLM second pass for edge cases): Better accuracy but increases architectural complexity, requires fallback logic when the LLM classifier is unavailable, and still introduces non-determinism for a subset of decisions.

3. **Third-party guardrail service** (NeMo Guardrails, Guardrails AI): Mature tooling but creates vendor dependency for the most critical safety layer, may not support credit-union-specific compliance patterns, and complicates examiner explainability.

### Consequences

- **Positive**: Sub-200ms total guardrail latency (target: 180ms for all 5 checks). Every block decision traces back to a specific regex match or threshold breach. No additional model risk introduced by the guardrail layer. Zero external API dependencies at runtime.
- **Positive**: Guardrail rules can be versioned, tested, and rolled back independently (see ADR-006).
- **Negative**: Lower recall on sophisticated PII formats or novel hallucination patterns that regex cannot catch. The production notes in `api/app.py` acknowledge this gap and recommend augmenting with NeMo Guardrails or classifier-based detection for production deployment.
- **Negative**: Regex-based PII detection requires ongoing pattern maintenance as new formats emerge.

---

## ADR-002: Versioned Prompt Registry with Approval Workflow

**Status:** Accepted
**Date:** 2025-11-20

### Context

Under SR 11-7 model risk management guidance, every component that influences model behavior must be documented, version-controlled, and subject to change management. Prompt templates are a direct input to LLM behavior and represent a significant source of model risk -- an unapproved prompt change could cause the model to produce non-compliant output at scale.

The platform needed a system to manage prompt templates as first-class auditable artifacts with lifecycle controls comparable to those applied to model code and training data.

### Decision

Implement `PromptRegistry` (`src/prompt_registry.py`) as an immutable, versioned prompt management system with a multi-stage approval workflow:

- **Lifecycle states**: `DRAFT` -> `PENDING_REVIEW` -> `APPROVED` -> `DEPLOYED` -> `DEPRECATED` (with `REJECTED` as a terminal state from review).
- **Immutable versions**: Each `PromptVersion` receives a SHA-256 content hash at creation. Once a version transitions past `DRAFT`, its template body cannot be modified -- only a new version can be created.
- **Variable typing and PII tracking**: `PromptVariable` declarations specify type (`STRING`, `NUMBER`, `DATE`, `ENUM`, `LIST`), validation rules, and a `contains_pii` flag. Variables marked as PII are redacted in render audit logs.
- **Risk-tiered governance**: Templates are classified by `UseCase` (customer service, document summarization, risk assessment, fraud detection, internal tooling) and `RiskTier` (Tier 1/2/3), with higher tiers requiring additional review.
- **A/B testing**: `ABTest` enables controlled prompt experiments with deterministic traffic splitting and audit trail of which version served which interaction.

### Alternatives Considered

1. **Git-based prompt management** (prompts as files in a repository with PR reviews): Familiar workflow but lacks runtime variable validation, PII-aware rendering, and programmatic lifecycle enforcement. Git cannot enforce that a prompt in "APPROVED" state is the only one served to production.

2. **Prompt management SaaS** (PromptLayer, Humanloop): Feature-rich but introduces a third-party dependency in the critical path between prompt and model. Regulatory data (prompt content referencing member account structures) would leave the institution's control boundary.

3. **Database-only storage** (prompts as rows without lifecycle logic): Simpler implementation but pushes all governance logic to application code, making it harder to enforce invariants like "only DEPLOYED versions are served" or "PII variables must be redacted in logs."

### Consequences

- **Positive**: Complete audit trail for every prompt change, including who authored, reviewed, and approved each version. SHA-256 hashes provide tamper evidence for examiner review.
- **Positive**: PII-aware rendering ensures that member data injected into prompts is tracked and redacted in compliance logs, satisfying GLBA and state privacy requirements.
- **Positive**: A/B testing with governance guardrails allows the institution to experiment with prompt improvements without bypassing change management.
- **Negative**: Higher development overhead compared to simple string templates. Every prompt change requires a version bump and approval cycle.
- **Negative**: The approval workflow is enforced in application logic (not infrastructure), so a misconfigured deployment could theoretically bypass it. Production deployment should add database-level constraints.

---

## ADR-003: Append-Only Compliance Logging with Immutable Audit Trail

**Status:** Accepted
**Date:** 2025-12-01

### Context

NCUA examination procedures and OCC SR 11-7 require financial institutions to maintain complete, unalterable records of every AI-assisted interaction with members. Examiners must be able to reconstruct any interaction -- what prompt was used, what model produced the output, what guardrails fired, and whether the output reached the member -- for the full retention period.

The audit trail must satisfy three properties:
1. **Completeness**: Every interaction is logged, including internal failures.
2. **Immutability**: Logs cannot be modified or deleted after creation.
3. **Queryability**: Examiners can search by date range, use case, model, guardrail outcome, and customer visibility.

### Decision

Implement `ComplianceLogger` (`src/compliance_logger.py`) as an append-only logging system with two primary record types:

- **InteractionLog**: Captures every field needed to reconstruct an interaction -- `interaction_id`, timestamps, model configuration, prompt template and version IDs, input/output lengths, all guardrail check results, final action (delivered/blocked), human review status, customer visibility flag, and a `log_integrity_hash` computed over all fields for tamper detection.
- **ComplianceEvent**: Raised automatically when guardrails block output or detect PII in output. Tracks severity, description, resolution status, and escalation path. Events are queryable with `unresolved_only` filters for active incident management.
- **AuditReport**: Generates regulatory-ready reports with breakdowns by use case, model, and guardrail check type. Reports include date ranges, total interactions, block rates, PII detection rates, and unresolved event counts.

Default retention period is 2,555 days (~7 years) to satisfy both federal examination cycles and state record retention requirements.

### Alternatives Considered

1. **Standard application logging** (structured logs to ELK/Datadog): Familiar tooling but application logs are typically mutable (log rotation, deletion policies), lack integrity hashing, and are not designed for regulatory examination workflows. Examiners expect purpose-built audit systems.

2. **Blockchain-based audit trail**: Provides cryptographic immutability but introduces significant operational complexity, is difficult for examiners to query, and is overkill for a single-institution deployment where S3 Object Lock provides equivalent WORM guarantees.

3. **Database with soft deletes**: Simpler implementation but "soft delete" implies deletion is possible, which weakens the immutability guarantee. A determined administrator could still modify records. True append-only requires infrastructure-level enforcement.

### Consequences

- **Positive**: Every interaction is reconstructable from log records. The `log_integrity_hash` enables automated tamper detection during examination preparation.
- **Positive**: Automatic `ComplianceEvent` generation ensures that guardrail blocks and PII detections always produce trackable incidents with resolution workflows.
- **Positive**: 7-year retention exceeds most state requirements and covers multiple NCUA examination cycles.
- **Negative**: In the current implementation, immutability is enforced at the application layer (append-only list). Production deployment requires infrastructure-level enforcement via S3 Object Lock (WORM mode) or equivalent, as noted in the code comments.
- **Negative**: High storage volume over 7 years. Production deployment needs lifecycle policies to transition older logs to cold storage (S3 Glacier) while maintaining queryability.

---

## ADR-004: Prompt Injection Defense via Input Sanitization and XML Delimiters

**Status:** Accepted
**Date:** 2025-12-10

### Context

Prompt injection is the #1 risk in the OWASP Top 10 for LLM Applications. In a financial services context, a successful prompt injection could cause the model to disclose other members' PII, generate unauthorized financial advice, or bypass compliance guardrails. The platform must defend against injection at the input layer (before the prompt reaches the model) and the output layer (guardrails screen the response).

### Decision

Implement a two-layer defense in `PromptRegistry._sanitize_variable()` and the prompt rendering pipeline:

**Layer 1 -- Input Sanitization** (pre-model):
- Strip common system prompt delimiters (`<|system|>`, `<|assistant|>`, `[INST]`, `<<SYS>>`, `</s>`) from all user-supplied variables via regex.
- Remove sequences that attempt to inject instructions (`ignore previous`, `disregard above`, `new instructions`).
- Normalize whitespace to prevent delimiter-based attacks using excessive spacing.

**Layer 2 -- XML Delimiter Wrapping**:
- All user-supplied variables are wrapped in explicit XML delimiters when injected into prompts: `<user_input name="variable_name">sanitized_value</user_input>`.
- This creates an unambiguous boundary between trusted prompt template content and untrusted user input, allowing the model to distinguish instruction from data.

**Layer 3 -- Output Guardrails** (post-model):
- Even if injection bypasses input sanitization, the five deterministic guardrail checks (ADR-001) screen the output for PII leakage, hallucinated figures, bias, compliance violations, and low confidence -- blocking compromised outputs before delivery.

### Alternatives Considered

1. **LLM-based injection classifier** (fine-tuned model to detect injection attempts): Higher accuracy on novel attacks but introduces the same concerns as ADR-001 (non-determinism, latency, recursive model risk). Also creates an arms race where attackers can probe the classifier.

2. **Instruction hierarchy / system prompt hardening only**: Relies on the model's instruction-following fidelity, which varies across models and versions. Not sufficient as a sole defense for regulated use cases where failure has compliance consequences.

3. **Input blocklist without delimiter wrapping**: Sanitization alone is brittle -- new injection patterns emerge constantly. The XML delimiter approach provides defense-in-depth by making the trust boundary explicit in the prompt structure, regardless of whether specific attack patterns are in the blocklist.

### Consequences

- **Positive**: Defense-in-depth with three layers (sanitize, delimit, screen) means no single bypass defeats all protections.
- **Positive**: Deterministic and auditable -- every sanitization action is logged, and examiners can review the regex patterns applied.
- **Positive**: XML delimiters are model-agnostic and work across Claude, GPT, and open-source models.
- **Negative**: Regex-based sanitization has limited coverage of novel injection techniques. The adversarial stress tests in `evals/adversarial/guardrail_stress_test.py` (35 test cases across 7 attack categories) validate current coverage but cannot guarantee completeness against future attacks.
- **Negative**: Aggressive sanitization may occasionally strip legitimate user input that happens to contain delimiter-like sequences (false positives on input). The platform currently accepts this trade-off in favor of safety.

---

## ADR-005: SR 11-7 Model Evaluation Framework with Bias Testing

**Status:** Accepted
**Date:** 2025-12-20

### Context

OCC SR 11-7 requires financial institutions to validate models before deployment and revalidate them periodically. For GenAI models, this means evaluating not just accuracy but also fairness, safety, groundedness, and compliance with regulatory constraints. Traditional model validation (backtesting, sensitivity analysis) does not fully apply to LLMs, which require output-level evaluation across diverse scenarios.

Credit unions serving diverse member populations must demonstrate that AI-assisted responses do not exhibit disparate treatment or disparate impact across demographic groups -- a requirement reinforced by fair lending regulations (ECOA, FHA) and NCUA examination procedures.

### Decision

Implement `ModelEvaluator` (`src/model_evaluator.py`) with the following components:

- **EvalSuite**: Configurable evaluation dimensions with pass/fail thresholds:
  - Accuracy (threshold: 90%), Relevance (90%), Groundedness (95%), Consistency (85%), Safety (99%), Bias (97%), Compliance (98%), Latency (p99 < 2000ms).
  - Thresholds are calibrated to credit union risk appetite -- safety and compliance thresholds are near-ceiling.

- **BiasEvaluator**: Runs identical prompts across demographic group variations (age, gender, ethnicity, disability status, veteran status, marital status, income level, geographic location). Measures:
  - Response length disparity (threshold: 3% max difference between groups).
  - Formality level disparity (threshold: 3% max difference).
  - Flags any statistically significant variation for human review.

- **ModelCard**: SR 11-7 documentation artifact capturing model description, intended use, out-of-scope uses, known limitations, risk factors, ethical considerations, mitigations, and monitoring plan. Generated programmatically from evaluation results for examiner review.

- **ValidationOutcome**: Four-tier result -- `APPROVED`, `CONDITIONAL` (approved with monitoring requirements), `REQUIRES_REMEDIATION` (specific issues to fix), `REJECTED` (fails minimum thresholds).

- **Quarterly revalidation**: 90-day validation window enforced by the `trigger-jobs/model_evaluation.ts` Trigger.dev job, which runs the full evaluation suite monthly and stores results in Supabase.

### Alternatives Considered

1. **Manual evaluation by data science team**: Common practice but does not scale, is not repeatable, and produces inconsistent documentation across evaluation cycles. Examiners increasingly expect automated, reproducible validation.

2. **Third-party evaluation platform** (Weights & Biases, Neptune, Giskard): Feature-rich but may not support credit-union-specific compliance dimensions (ECOA bias categories, NCUA examination format) without significant customization. Also introduces vendor dependency for a core governance function.

3. **Statistical testing only** (A/B tests, significance tests on accuracy): Insufficient for regulatory requirements. SR 11-7 expects qualitative assessment (model cards, limitation documentation) alongside quantitative metrics. Bias testing requires demographic-specific analysis, not just aggregate performance.

### Consequences

- **Positive**: Automated evaluation produces consistent, comparable results across evaluation cycles. Model cards provide examiner-ready documentation.
- **Positive**: Bias testing across 8 demographic dimensions with 3% disparity thresholds exceeds typical fair lending analysis for traditional models, demonstrating proactive compliance.
- **Positive**: Four-tier validation outcome provides clear governance signals -- `CONDITIONAL` approval allows deployment with enhanced monitoring rather than binary approve/reject.
- **Negative**: Bias evaluation with synthetic prompts may not capture real-world interaction patterns. Production deployment should augment with analysis of actual member interactions (with PII redaction).
- **Negative**: Monthly evaluation cadence may miss model degradation between cycles. Production deployment should add continuous monitoring with drift detection alerts.

---

## ADR-006: Guardrail Rule Versioning with Rollback Capability

**Status:** Accepted
**Date:** 2026-01-05

### Context

Guardrail rules (regex patterns, keyword lists, thresholds) evolve as new risks emerge, false positive patterns are identified, and regulatory guidance changes. Under SR 11-7 change management requirements, every modification to a guardrail rule must be documented, approved, and reversible. A bad guardrail update -- for example, a regex that blocks all outputs containing dollar signs -- could halt member service or, worse, allow non-compliant output through.

### Decision

Implement `GuardrailVersionManager` (`src/guardrail_versioning.py`) with the following design:

- **Immutable rule versions**: Each `GuardrailRuleVersion` captures the complete rule state (patterns, thresholds, action mappings) with semantic versioning (e.g., "1.2.3"). Once a version transitions past `DRAFT`, its configuration is frozen.
- **Approval workflow**: Mirrors the prompt registry lifecycle -- `DRAFT` -> `PENDING_REVIEW` -> `APPROVED` -> `DEPLOYED` -> `DEPRECATED`. Only one version per guardrail check can be in `DEPLOYED` state at any time.
- **Rollback**: `rollback_to_version()` reverts a guardrail check to a previously approved version with a single operation. The rollback itself is recorded in the version history for audit purposes.
- **Production metrics tracking**: Each deployed version records false positive rate, false negative rate, and true positive rate from production traffic, enabling data-driven rule refinement.
- **Change history**: Every state transition is recorded with timestamp, actor, and reason -- providing a complete audit trail for examiner review.

### Alternatives Considered

1. **Configuration-as-code in Git** (guardrail rules as YAML/JSON in the repository): Provides version history via Git commits but lacks runtime rollback, approval workflow enforcement, and production metrics tracking. A Git-based approach requires a deployment pipeline to propagate changes, adding latency to emergency rollbacks.

2. **Feature flags for rule toggles** (LaunchDarkly or equivalent): Enables rapid toggling but does not provide version history, approval workflows, or production effectiveness metrics. Feature flags are binary (on/off) rather than supporting the graduated lifecycle needed for regulated change management.

3. **Unversioned rules with monitoring**: Simplest approach but fails SR 11-7 change management requirements. Without version history, the institution cannot demonstrate to examiners what rules were active during a specific time period or why a particular interaction was blocked/delivered.

### Consequences

- **Positive**: Complete audit trail of every guardrail rule change satisfies SR 11-7 change management requirements. Examiners can reconstruct exactly which rules were active for any historical interaction.
- **Positive**: Rollback capability reduces the blast radius of bad rule updates -- a problematic change can be reverted in seconds rather than requiring a code deployment.
- **Positive**: Production metrics on each version enable data-driven rule refinement -- the team can compare false positive rates across versions to validate improvements.
- **Negative**: Adds operational overhead for simple rule changes (e.g., adding a single regex pattern requires a full version cycle). This is an intentional trade-off favoring governance over velocity.
- **Negative**: The versioning system is currently application-layer only. Production deployment should back this with database constraints to prevent concurrent DEPLOYED versions for the same check.
