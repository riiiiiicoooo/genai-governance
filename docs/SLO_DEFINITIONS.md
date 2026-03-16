# GenAI Governance Platform — Service Level Objectives (SLOs)

**Last Updated:** March 2026
**Compliance Scope:** NCUA examination readiness, guardrail effectiveness, audit trail integrity for financial services AI

---

## Error Budget Policy

GenAI Governance operates with **zero-tolerance SLOs** for regulatory compliance (guardrail effectiveness, audit trail) and **monthly error budgets** for operational metrics (API latency, availability). The distinction reflects the core mission: every guardrail must work; every audit trail entry must exist and be immutable.

**SLO Categories:**
- **Zero-tolerance SLOs:** Guardrail effectiveness (PII blocking, hallucination detection, compliance filtering), audit trail integrity (no error budget)
- **Operational SLOs:** API latency, system availability, prompt approval workflow (monthly error budgets with burn rate alerts)

---

## SLO 1: Guardrail Blocking Accuracy (PII Detection + Hallucination Prevention)

**Service:** `guardrail-pipeline` (PII detector, hallucination checker, bias screener, compliance filter)
**Definition:** Percentage of LLM outputs where guardrails correctly block outputs containing regulated content (PII, hallucinated financial figures, bias, compliance violations) before delivering to end user.

**Target:** 99.5% (2 exposures per 1000 interactions)

**Error Budget:** None (this is non-negotiable; a single PII exposure in financial services context is regulatory violation)

**Measurement:**
- Query: `(PII_DETECTED_AND_BLOCKED + HALLUCINATION_DETECTED_AND_BLOCKED + COMPLIANCE_VIOLATION_DETECTED_AND_BLOCKED) / TOTAL_OUTPUTS_GUARDRAILED`
- Sampling: 100% of outputs in production; monthly audit against human reviewers for false negatives
- Ground truth: Manual QA review of 100 outputs/week for missed detections
- Source: `guardrail_decisions`, `output_audit_log`

**Why This Target:**
- **Regulatory requirement:** NCUA examiners expect 0% PII in customer-facing outputs; 99.5% means ~1 PII exposure per 200 outputs (at 43.8K interactions/month baseline, ~220 outputs/month contain some PII; 99.5% blocking = ~1 exposure/month in production)
- **Compliance baseline:** Financial services regulators expect "reasonable safeguards"; 99.5% is industry-standard for compliance (same as SOC 2 Type II)
- **False positive cost:** Blocking 2% of valid outputs (being too conservative) is acceptable if it means zero PII reaches customers
- **Practical tradeoff:** 99.9%+ would require such tight filters that 10%+ of legitimate outputs get blocked (unusable for customer service)

**Burn Rate Triggers (escalation rules):**
- **Any PII exposure reaches customer:** Immediate escalation to compliance officer + risk committee
- **2+ PII exposures in 7 days:** Halt all LLM interactions; full system audit of guardrails
- **Pattern of same PII type exposed:** (e.g., always missing SSN format) — emergency guardrail tuning

**Mitigations:**
- Multi-layered detection: Regex patterns (SSN format, account number format) + ML-based PII detection (names, addresses) + contextual checks
- Conservative tuning: When unsure if output is PII, block it (false positive acceptable, false negative not)
- Human review loop: Every proposed output with borderline PII risk is routed to human reviewer
- Continuous monitoring: Weekly review of false positive rate; if >5% outputs blocked (too conservative), retrain model

---

## SLO 2: Audit Trail Integrity (Immutable Compliance Log for Regulators)

**Service:** `audit-log-processor`, `compliance-logger`
**Definition:** Percentage of interactions where guardrail decision (DELIVER / BLOCK / REVIEW) is logged to immutable storage (S3 Object Lock) within 100ms. Log must include: timestamp, input prompt, output, guardrail decisions, approval status.

**Target:** 99.99% (14 events missing per million interactions at 1M baseline)

**Error Budget:** 14 events/month (at 43.8K interactions/month baseline = ~4 missing audits/month acceptable)

**Measurement:**
- Query: `(AUDITED_INTERACTIONS) / TOTAL_INTERACTIONS`
- Sampling: 100% of interactions; daily verification that all S3 audit objects exist and are locked
- Validation: Random sample (100/day) to verify audit record matches interaction (no data corruption)
- Source: `interaction_audit_log`, S3 audit bucket

**Why This Target:**
- **Regulatory requirement:** NCUA requires immutable audit trails of all AI decisions; missing audit entries are compliance failure
- **Forensic value:** If regulator asks "Show me all interactions for this member on this date," we need 99.99%+ completeness or regulators lose confidence
- **Practical impact:** At 43.8K interactions/month, 99.99% means ~4 missing audit records/month; defensible to regulators as "due diligence"

**Burn Rate Triggers:**
- **Audit logging latency > 500ms:** Watch alert; may indicate S3 write delays
- **24-hour gap in audit logs:** Critical alert; immediate escalation to compliance
- **S3 Object Lock validation fails:** Critical; audit logs are not actually immutable

**Mitigations:**
- Dual write: Audit events written to PostgreSQL (for fast query) + S3 (immutable backup)
- S3 Object Lock: COMPLIANCE mode (nobody can delete) for >90 days
- Local buffer: If S3 write fails, buffer in PostgreSQL with retry; eventually consistent
- Daily validation: Automated job confirms all interactions have corresponding audit entries

---

## SLO 3: Prompt Approval Workflow Completion (Compliance Approval Chain)

**Service:** `prompt-workflow-manager`
**Definition:** Percentage of new or modified prompts where approval is obtained before deployment to production. Approval chain: DRAFT → PENDING_REVIEW → APPROVED → DEPLOYED.

**Target:** 100.0% (zero prompts reach production without compliance sign-off)

**Error Budget:** None (this is non-negotiable; unapproved prompts in production is regulatory violation)

**Measurement:**
- Query: `(PROMPTS_APPROVED_BEFORE_DEPLOY) / TOTAL_PROMPTS_DEPLOYED`
- Sampling: 100% of prompts; real-time validation at deploy time (block deploy if approval missing)
- Source: `prompt_versions`, `prompt_approvals`

**Why This Target:**
- **Regulatory requirement:** NCUA wants to know "How do you control what the AI says to members?" Answer: Versioning + approval workflow
- **Compliance evidence:** Examiners can ask "Show me this prompt's approval chain" and see: who reviewed, when, what evaluation scores, what bias tests passed
- **Audit trail:** Every prompt version captures created_by, reviewed_by, reviewed_at, approved_by, approved_at, deployed_by, deployed_at

**Burn Rate Triggers:**
- **Any prompt deploys without approval:** Immediate rollback + incident
- **Approval workflow disabled or bypassed:** Halt all deployments; investigate and fix

**Mitigations:**
- Enforcement at deploy time: Deployment pipeline checks that all prompts have approval before going live
- Immutable history: Once a prompt is approved, approval cannot be revoked or hidden
- Role-based access: Only compliance officers can approve; engineers cannot approve their own prompts

---

## SLO 4: Guardrail Latency (Detection Doesn't Slow Down User Experience)

**Service:** `guardrail-pipeline`
**Definition:** Percentage of LLM outputs where guardrail evaluation (PII detection + hallucination check + bias screen + compliance filter) completes in ≤ 500ms (p95 latency).

**Target:** 98.0% (max p95 latency 500ms)

**Error Budget:** 36 hours/month (at 43.8K interactions/month baseline)

**Measurement:**
- Query: `(GUARDRAIL_LATENCY_P95 <= 500ms) * 100`
- Includes: All four guardrail checks (sequential or parallel)
- Excludes: LLM inference time (pre-guardrail)
- Source: `guardrail_metrics`

**Why This Target:**
- **User experience:** Call center reps are waiting for guidance while member is on the phone; >500ms latency is noticeable (call center SLA is typically <1 second response time)
- **Guardrail complexity:** Four parallel checks (PII, hallucination, bias, compliance) each taking 100-150ms = 150-200ms total with caching, up to 400-500ms on cache misses
- **LLM context:** LLM inference takes 1-3 seconds; guardrails add <500ms, so total latency is 2-4 seconds (acceptable for member-facing interaction)

**Burn Rate Triggers:**
- **p95 latency > 1 second (2x target):** High burn; indicates guardrail checks are slow (may need optimization)
- **p50 latency > 300ms:** Normal burn; monitor for trend
- **Cache hit rate < 80%:** Watch alert; guardrail cache should be warmer

**Mitigations:**
- Parallel guardrail evaluation: Run all four checks concurrently, not sequentially
- Prompt caching: PII patterns, compliance rules are cached
- Lazy evaluation: Skip expensive checks if earlier checks already blocked output

---

## SLO 5: System Availability (API Responsiveness)

**Service:** `genai-governance-platform` (aggregate)
**Definition:** Percentage of 1-minute windows where ≥99% of interaction requests receive a response (guardrail decision) within 10 seconds.

**Target:** 99.5% (3.6 hours downtime/month)

**Error Budget:** 3.6 hours/month

**Measurement:**
- Query: `(MINUTES_WITH_99PCT_SUCCESS) / TOTAL_MINUTES`
- Sampling: 1-minute windows; rolling 24h average
- Source: API request metrics

**Why This Target:**
- **Operational reality:** Call center SLAs typically require <1 second response time; our 10-second timeout allows for LLM latency (3-5s) + guardrails (0.5s) + network (0.5s)
- **99.5% availability:** Allows 1-2 brief outages per month (30-min each); acceptable for internal compliance tool
- **Financial services SLA:** 99.5% is minimum for financial services IT systems

**Burn Rate Triggers:**
- **Error rate > 2% (burn rate > 10x):** Page on-call; likely LLM API issue or database unavailable
- **Error rate > 1%:** High burn; investigate
- **Timeout rate > 5% (requests taking >10s):** Watch alert; LLM or guardrail latency degradation

**Mitigations:**
- Multi-region LLM endpoints: Use regional LLM providers (Claude via Anthropic, GPT-4 via OpenAI); automatic regional failover
- Circuit breaker on LLM calls: Fail fast if LLM is slow; return cached guidance instead of waiting
- Degraded mode: If guardrails slow, cache results from previous calls for same member context

---

## SLO 6: Guardrail False Positive Rate (Conservative but Not Excessive)

**Service:** `guardrail-pipeline`
**Definition:** Percentage of outputs blocked by guardrails that were actually appropriate to deliver (false positives). Target: < 5%.

**Target:** < 5.0% false positive rate (95% accuracy)

**Error Budget:** None (false positives hurt user experience; monitor continuously)

**Measurement:**
- Quarterly human review: 100-200 blocked outputs reviewed by compliance officer + call center manager
- Validation: "Was this output appropriately blocked, or was it a false positive?"
- Source: Manual audit of `guardrail_decisions` where decision = 'BLOCK'

**Why This Target:**
- **User experience:** >5% false positives means advisors are frustrated with system (too many legitimate outputs blocked)
- **Practical impact:** At 43.8K interactions/month with 2.6% block rate (~1140 blocked outputs), 5% false positive = ~57 false positives/month; acceptable
- **Regulatory angle:** NCUA doesn't care about false positives (better to over-block than under-block); we limit to 5% so call center remains usable

**Burn Rate Triggers:**
- **False positive rate > 10%:** Guardrails are too conservative; retrain or adjust thresholds
- **False positive rate trending upward:** May indicate model drift or training data shift

**Mitigations:**
- Quarterly tuning: Based on blocked output review, adjust thresholds to reduce false positives
- Feedback loop: Advisors can appeal blocked outputs; appeals feed back into model retraining
- Human review tier: Outputs blocked by borderline rules go to human reviewer before being delivered

---

## Error Budget Consumption Practices

1. **Daily compliance review:** Zero-tolerance SLOs (guardrail accuracy, audit trail) reviewed every morning
2. **Weekly executive review:** Report to CRO (Chief Risk Officer) on SLO status, guardrail effectiveness
3. **Quarterly audit:** NCUA-ready audit of prompt versions, approvals, guardrail decisions
4. **Post-incident RCA:** Every guardrail miss or audit gap triggers 24-hour RCA and fix

