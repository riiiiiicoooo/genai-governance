# GenAI Governance Platform — Product Requirements Document

## Executive Summary

This document outlines the requirements for a compliance-first governance layer for deploying generative AI in regulated financial services. Built for a small community credit union, the platform addresses the four core questions an NCUA examiner will ask about AI governance.

---

## The Four Core Questions

Every financial regulator examining an institution's AI practices will ask these four questions. This platform enables the compliance officer to answer all of them with documentation and evidence.

### 1. How Are Prompts Managed and Approved?

**The Problem (Before):**
- Prompts were hardcoded in Python scripts with no version control
- Engineers could push prompt changes to production with no review
- If a prompt change caused the model to give bad advice to a member, there would be no audit trail
- The compliance officer had no way to know what prompts were active in production

**The Requirement:**
Every prompt must be versioned, approved, and auditable. No prompt change reaches production without explicit compliance review.

**Implementation:**

| Component | Requirement | Evidence |
|-----------|-------------|----------|
| **Prompt Registry** | Versioned templates with immutable history | `PromptTemplate` and `PromptVersion` classes with status lifecycle (DRAFT → PENDING_REVIEW → APPROVED → DEPLOYED → DEPRECATED) |
| **Approval Workflow** | Explicit MRM sign-off before deployment | `approve_version()` method requires approver name, notes, evaluation scores, bias test results |
| **Variable Schema** | All prompt variables declared with type and validation | `PromptVariable` class with type, max_length, validation_pattern, PII classification |
| **Deployment Audit Trail** | Complete history of who approved what and when | Every prompt version captures: created_by, reviewed_by, reviewed_at, approved_by, approved_at, deployed_by, deployed_at, retired_at |
| **A/B Testing** | Controlled experiments with traffic split and impression tracking | `ABTest` class with variant_a, variant_b, traffic_split, impression counts |

**Examiner Readiness:**
- Compliance officer can produce prompt version history for any active template
- Each version shows approval chain with dates and reviewer comments
- Model evaluation scores tied to specific prompt versions
- Approval rate metric: 100% of production prompts have compliance sign-off

**Dashboard Evidence:**
- Prompt Registry panel shows active version, total versions, pending reviews per template
- Deployment history with compliance officer sign-off visible to examiner

---

### 2. How Are Outputs Screened Before Reaching Members?

**The Problem (Before):**
- LLM responses went directly to the call center rep with no screening
- If the model hallucinated an interest rate or surfaced a member's SSN, nobody would catch it
- The compliance officer couldn't audit what had been sent to customers

**The Requirement:**
Every LLM output must pass through deterministic guardrails before the rep sees it. No LLM calls for screening (no latency penalty, no cost multiplication).

**Implementation:**

| Check | Requirement | Evidence |
|-------|-------------|----------|
| **PII Detection** | Block outputs containing SSNs, account numbers, DOBs surfaced by the model | Regex patterns for SSN (XXX-XX-XXXX, XXXXXXXXX), account numbers, credit cards, routing numbers, dates of birth, emails, phone numbers |
| **Hallucination Check** | Block ungrounded financial figures (dollar amounts, percentages, rates, dates, account balances not in input context) | Extract all dollar amounts, percentages, dates from output. Cross-check against input context. Flag ungrounded high-risk figures as BLOCK |
| **Bias Screen** | Detect differential language patterns and response quality disparities | Pattern matching for steering language, inappropriate assumptions, discriminatory references. Structural analysis: response length penalties, formality analysis |
| **Compliance Filter** | Block outputs violating banking regulations (unauthorized advice, guarantees, rate promises, competitor comparisons) | Pattern matching for "I recommend you invest", "guaranteed", "risk-free", "you will earn", competitor bank names |
| **Confidence Assessment** | Assess structural quality indicators of response reliability | Refusal detection, response length vs. input length, repetition analysis, code block detection. Score 0-100 |

**Guardrail Actions:**
- `DELIVER`: All checks passed
- `DELIVER_WITH_FLAG`: Minor issues (warning level), deliver but flag for review
- `BLOCK_FOR_REVIEW`: Issues detected, route to human reviewer
- `BLOCK_AND_ALERT`: PII or compliance violation, immediate escalation

**Examiner Readiness:**
- Compliance logger captures every guardrail result for every output
- Dashboard shows guardrail performance metrics: pass rate, warning rate, block rate per check
- Can query: "Show me all outputs blocked by PII detection in Q1" instantly

**Evidence Metrics (Q1 Production):**
- 43,800 interactions processed
- 97.4% delivered, 2.6% blocked by guardrails
- 191 PII exposures caught (0.5% of outputs)
- 538 hallucinations detected and blocked

---

### 3. How Are Models Evaluated for Bias and Accuracy?

**The Problem (Before):**
- No systematic testing of LLM outputs against regulatory criteria
- Couldn't demonstrate fair lending (equal treatment regardless of member characteristics)
- No documented validation process that an OCC examiner would recognize

**The Requirement:**
Models must be validated against a rigorous evaluation suite covering accuracy, grounding, consistency, safety, and bias. Documentation must follow SR 11-7 model risk management standards.

**Implementation:**

| Evaluation Dimension | Requirement | Evidence |
|---|---|---|
| **Accuracy** | Required keywords present, prohibited phrases absent, output length appropriate | Keyword matching against expected_characteristics. Percentage of required keywords found. Prohibited phrase detection. Length checks (min/max words) |
| **Relevance** | Output answers the question asked in the context of the input | Covered in accuracy check (required keywords) |
| **Groundedness** | All financial figures (dollar amounts, percentages, dates) are traceable to input context | Extract dollar amounts, percentages, dates from output. Cross-check against input context. Ungrounded figures penalize score |
| **Consistency** | Same input → similar output across multiple runs | Measure word count variance and phrase overlap (Jaccard similarity) across runs. Score = similarity*80 + (1-length_CV)*20 |
| **Safety & Compliance** | Output avoids prohibited language, guarantees, unsupported claims | Checklist of prohibited patterns from ComplianceFilter guardrail |
| **Bias** | Response quality does not vary systematically across demographic groups | Response length disparity test: measure average word count per demographic group. Flag if max disparity > 3% |

**Test Suite Design:**
- Happy path cases (expected scenarios)
- Edge cases (boundary conditions)
- Adversarial cases (prompt injection attempts)
- Bias probe cases (same question, different demographic identifiers)

**Validation Outcome Options:**
- `APPROVED`: All dimensions meet thresholds
- `CONDITIONAL`: Approved with monitoring conditions (scores slightly below threshold)
- `REQUIRES_REMEDIATION`: Failed critical dimension (safety, compliance, groundedness), needs fixes
- `REJECTED`: Failed critical threshold severely, not deployable

**Thresholds:**
| Dimension | Threshold |
|-----------|-----------|
| Accuracy | 85% |
| Relevance | 90% |
| Groundedness | 95% |
| Consistency | 80% |
| Safety | 99% |
| Bias (max disparity) | 3% |
| Compliance | 99% |
| Latency (within SLA) | 95% |

**Model Card (SR 11-7 Documentation):**
Every model in production has a model card documenting:
- Description and intended use
- Out-of-scope uses
- Known limitations
- Evaluation history and results
- Bias testing results
- Risk factors and mitigations
- Monitoring plan and drift thresholds
- Validation status and next validation date

**Examiner Readiness:**
- Compliance officer produces model card in compliance with SR 11-7 and FFIEC guidance
- Card shows: model provider, risk tier, evaluation scores, bias test results, approval status
- Latest validation date and next revalidation date visible
- Risk factors and mitigations documented

**Evidence Metrics (Q1 Production):**
- 2 models in production, 2/2 validated
- Member Service Copilot: 91.2% accuracy, 96.4% groundedness, 97.3% bias test pass, APPROVED
- Loan Summarizer: 93.5% accuracy, 97.8% groundedness, 99.4% bias test pass, APPROVED
- Next validation due: Mar 28 and Mar 15 respectively

---

### 4. What Audit Trail Exists?

**The Problem (Before):**
- No central log of AI-generated interactions
- Examiner asks: "Show me records of all AI-assisted member interactions in Q1" → answer: "We can't"
- No way to correlate an AI output with a member complaint

**The Requirement:**
Complete immutable audit trail of every LLM interaction, with full context, guardrail results, and outcomes. Must be queryable for regulatory examination.

**Implementation:**

| Component | Requirement | Evidence |
|-----------|-------------|----------|
| **Interaction Log** | Every LLM interaction creates exactly one log entry | `InteractionLog` class capturing: interaction_id, timestamp, use_case, user_id, model_id, template_id, input_length, output_length, guardrail_action, human_review_required, final_action, latency metrics |
| **Append-Only Storage** | Logs are immutable once written (no edits, no deletes) | Logs stored in in-memory list; production uses S3 with Object Lock (WORM compliance) |
| **PII Handling** | Raw PII logged for integrity but encrypted at rest, redacted in exports | input_text_hash and output_text_hash (SHA-256) logged instead of raw PII; input/output_contains_pii flags; input/output_pii_types enumerated |
| **Compliance Events** | Auto-generated events for guardrail blocks, PII exposures, violations | `ComplianceEvent` class with event_type, severity, description; auto-created when guardrail_action is "block" or "alert" or output_contains_pii is true |
| **Human Review Tracking** | Record human reviewer, review timestamp, review outcome, notes | human_reviewer, human_review_timestamp, human_review_outcome (approved/edited/rejected/escalated), human_review_notes |
| **Final Disposition** | Track whether output was ultimately delivered, edited, blocked, or escalated | final_action enum: delivered, delivered_edited, blocked, escalated |
| **Queryability** | Find interactions by date range, use case, guardrail action, model, customer visibility | `query_interactions()` and `query_events()` methods with filters |
| **Retention Compliance** | Logs retained per credit union's record retention policy (~7 years default) | retention_days parameter in ComplianceLogger constructor |

**Audit Reports (Examiner-Ready):**
- Total interactions in period, delivered vs. blocked breakdown
- PII exposures and compliance violations flagged
- Guardrail check results by check type (pass/warn/block)
- Interactions by use case and by model
- Notable events requiring escalation
- Human review activities

**Dashboard Evidence:**
- Compliance tab shows unresolved events count, PII caught count, human reviews conducted
- Compliance events table with ID, description, severity, date, status
- NCUA Exam Readiness: Interaction Logs (Complete), Model Documentation (Current), Prompt Version History (Complete)

**Evidence Metrics (Q1 Production):**
- 43,800 total interactions logged
- 97.4% delivered to customer, 2.6% blocked
- 191 PII detections (output_contains_pii = true), all caught by guardrails before reaching member
- 14 compliance events, 2 unresolved
- 48 human reviews conducted
- All events queryable by examiner in under 1 second

---

## Risk Tiers and Approval Rigor

Governance is proportional to risk. Higher-risk use cases require more scrutiny.

| Tier | Risk Profile | Approval Rigor |
|------|--------------|---|
| **Tier 1** | Customer-facing, decision-influencing (e.g., loan approvals, account closures) | High: Detailed evaluation, extended testing, MRM deep dive, multiple reviewers |
| **Tier 2** | Customer-facing, informational (e.g., member service responses, FAQs) | Medium: Standard evaluation, bias testing, single MRM reviewer, quick turnaround |
| **Tier 3** | Internal-only, productivity tool (e.g., document summarization, internal search) | Low: Lightweight evaluation, basic testing, manager approval sufficient |

In the initial deployment:
- Member Service Copilot: **Tier 2** (customer-facing, non-binding information)
- Loan Document Summarizer: **Tier 3** (internal only, supports human decision-makers)

---

## Production Deployment Target

**Credit Union Profile:**
- Assets: $3.2 billion
- Members: 180,000
- Call center: 15 staff, ~3,500 calls/month
- Loan officers: 6 staff, processing ~300 applications/month

**Use Cases:**

1. **Member Service Copilot** (Tier 2)
   - Drafts responses to member inquiries (balance, transactions, products, general service)
   - Rep reviews and edits before sending (can override, reject, or send as-is)
   - Target: Reduce average handle time from 7.2 to 5.8 minutes
   - Volume: ~43,000 interactions in Q1

2. **Loan Document Summarizer** (Tier 3)
   - Extracts key terms and data from loan applications and supporting docs
   - Supports loan processors, not member-facing
   - Target: Reduce document review time by 30%
   - Volume: ~5,600 interactions in Q1

**First-Year Goals:**
- Deployment in Q1 with 0 findings in NCUA exam (compliance officer can answer all examiner questions)
- Average handle time reduction from 7.2 to 5.8 minutes (AHT improvement)
- Loan document review time reduction by 35%
- Block rate: 2-3% (hallucinations, PII leaks, bias caught before reaching members)
- Human review rate: <5% of blocked outputs require escalation beyond supervisor

---

## Success Metrics

**Compliance Metrics:**
- Prompt approval rate: 100% of production prompts have MRM sign-off
- Model validation status: All models in production with current validation (within 90 days)
- Audit trail completeness: 100% of interactions logged with guardrail results
- Compliance event resolution: <10% unresolved events older than 30 days

**Safety Metrics:**
- Guardrail block rate: 2-5% (within expected range)
- PII detection rate: >95% sensitivity (catch majority of actual PII exposures)
- Hallucination block rate: >80% of ungrounded financial figures caught
- Bias disparity: <3% response length disparity across demographic groups

**Operational Metrics:**
- Guardrail latency: <200ms average (deterministic checks only)
- Model latency: <2 seconds average (LLM inference via AWS Bedrock)
- Total pipeline latency: <3 seconds (prompt render + LLM + guardrails + logging)
- Examiner readiness: Compliance officer can produce all required documentation in <1 hour

**Business Metrics:**
- Average handle time: 7.2 → 5.8 minutes (19.4% improvement)
- Loan document review time: 30% reduction
- Agent satisfaction: Handle time improvement without quality degradation
- Member complaints: Baseline tracking

---

## Regulatory Framework

**Guidance Applied:**

1. **OCC SR 11-7 (Model Risk Management)** — Applied informally by NCUA
   - Model documentation requirements: ✓ (model cards)
   - Validation testing: ✓ (evaluation suites)
   - Monitoring and drift detection: ✓ (quarterly evaluations)
   - Risk factors and mitigations: ✓ (documented in model cards)

2. **FFIEC AI Guidance** (principles-based)
   - Effective risk management: ✓ (governance layer)
   - Appropriate controls: ✓ (guardrails)
   - Testing and validation: ✓ (evaluation framework)
   - Monitoring: ✓ (compliance logger)
   - Audit trail: ✓ (immutable logging)

3. **Fair Lending and Bias**
   - Disparate impact testing: ✓ (bias evaluation across demographic groups)
   - Equal treatment documentation: ✓ (bias test results in model card)
   - Remediation of disparities: ✓ (prompt adjustment when disparity detected)

4. **Data Privacy and Security**
   - PII handling: ✓ (detected, blocked, or logged with encryption at rest)
   - Audit trail integrity: ✓ (append-only, hash-based)
   - Retention compliance: ✓ (configurable retention period per policy)

---

## Phased Rollout

### Phase 1: Member Service Copilot (Jan 2026 — Target)
- Deployment to call center with supervisor review required for high-risk categories
- Focus on balance inquiries, transaction questions, product information
- Guardrails in production, monitoring enabled
- Compliance officer reviews weekly metrics

### Phase 2: Loan Document Summarizer (Feb 2026 — Target)
- Internal-only deployment, lower approval rigor
- Loan processors use summaries to support their decisions (not binding)
- Same governance layer, lighter evaluation bar

### Phase 3: Monitoring and Optimization (Ongoing)
- Weekly bias testing against demographic test set
- Monthly evaluation runs for model drift
- Quarterly prompt versioning and A/B testing
- Continuous guardrail tuning based on actual block patterns

---

## What Success Looks Like

**In the NCUA Exam:**

**Examiner:** "What AI models are you using in member-facing applications?"

**Compliance Officer:** Shows model cards. Two models: Member Service Copilot (Claude 3 Sonnet, Tier 2) and Loan Document Summarizer (Claude 3 Sonnet, Tier 3). Both validated per SR 11-7. Model cards available with evaluation history.

**Examiner:** "How do you validate and monitor these models?"

**Compliance Officer:** Shows evaluation suite with test cases. Demonstrates bias testing across demographic groups. Shows 97.3% bias test pass rate for Member Service Copilot. Quarterly revalidation schedule. Drift monitoring enabled.

**Examiner:** "Can you show me records of AI-assisted member interactions?"

**Compliance Officer:** Pulls up dashboard. Shows 43,800 interactions in Q1. Can filter by use case, date range, guardrail action. Query: "Show me all blocked outputs in Q1" → 1,134 blocked for guardrail issues, breakdown by check type. Can export full audit report with PII redacted.

**Examiner:** "How do you prevent bias or discriminatory treatment?"

**Compliance Officer:** Shows bias test results. Response length disparity: 1.2% (threshold 3%). No flagged groups. Shows remediation when prior version had 4.1% disparity — prompt updated, re-tested, now passes.

**Examiner:** "What's your prompt governance process?"

**Compliance Officer:** Shows prompt registry. Member Service Response template: 5 versions, v2.1 currently deployed, v3.2 pending review. Shows approval workflow: draft → pending review → approved → deployed. All deployments require compliance officer sign-off. Change reason and reviewer notes captured.

**Exam Result:** "This governance framework is ahead of most institutions your size. The documented controls around model validation, bias testing, and output screening are strong. Continue monitoring quarterly."

---

## Document Control

| Date | Version | Author | Change |
|------|---------|--------|--------|
| Feb 2026 | 1.0 | Digital Transformation Team | Initial PRD for Q1 2026 production deployment |

---

## Appendix: Technical Architecture

See `ARCHITECTURE.md` for:
- System pipeline architecture
- Design decisions (deterministic guardrails, S3 Object Lock, model-agnostic abstraction)
- Deployment topology
- Day-to-day compliance officer workflow
- Incident response procedures
