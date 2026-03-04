# Enterprise GenAI Governance Platform

**Compliance-first governance layer for deploying generative AI in regulated financial services.**

Built for a small community credit union that wanted to use GenAI in their member service center and loan processing workflow but had no framework for doing it safely. The NCUA examiner had asked about their AI plans during the last exam cycle. The compliance officer had no answers. The board had approved a digital transformation budget. What they didn't have was anyone who knew how to deploy AI in a way that wouldn't create regulatory exposure.

---

## The Problem

The credit union's member service center handles thousands of calls per month -- balance inquiries, transaction disputes, loan questions, account changes. The call center runs a small team of reps with a supervisor. Turnover is high. Training a new rep takes weeks before they can handle calls independently.

The VP of Operations had seen demos of GenAI-powered call center tools. The pitch was compelling: draft responses for reps, summarize member accounts before calls, auto-classify incoming requests. She brought it to the CIO, who brought it to the board. The board approved a digital transformation budget for the year.

Here's where it stalled:

**The compliance officer raised her hand.** She'd been reading NCUA letters and FFIEC guidance. While there was no specific GenAI regulation yet, existing model risk management expectations (based on OCC SR 11-7, which NCUA follows informally) clearly applied. Any AI system that touches member interactions or lending decisions needs documentation, validation, and monitoring.

The credit union had none of that infrastructure:

- **No prompt management.** The CIO's plan was to have a developer write prompts in the application code. No versioning, no review, no approval process. If a prompt change caused the model to give bad advice to a member, there would be no record of what changed or when.

- **No output screening.** The GenAI tool drafts a response, the rep sends it. If the model hallucinated an interest rate or surfaced a member's SSN, nobody would catch it before it went out.

- **No bias testing.** Fair lending applies to any system that interacts with members, even if it's just drafting responses. The credit union couldn't demonstrate equitable treatment because they weren't measuring it.

- **No audit trail.** NCUA examiners can request records of AI-assisted interactions. The credit union had no logging. If asked "show me every AI-generated response sent to members this quarter," the answer was "we can't."

- **No model documentation.** The FFIEC's guidance on model risk management requires banks and credit unions to document what models they use, how they're validated, and how they're monitored. The compliance officer had no template for documenting an LLM.

The compliance officer's position: "I support this initiative, but I need to be able to answer the examiner's questions. Right now I can't."

The board's position: "We approved the budget. Why isn't this live yet?"

---

## What We Built

A governance layer that sits between the credit union's applications and the LLM provider. Every prompt, every response, every model interaction passes through this layer. It handles four things:

1. **Prompt management** -- versioned, approved, auditable prompt templates
2. **Output guardrails** -- real-time checks on every LLM response before the rep sees it
3. **Model evaluation** -- systematic testing across compliance-relevant dimensions
4. **Compliance logging** -- complete audit trail for examiner readiness

### Architecture

```
┌──────────────────────────────────────────────────────┐
│  Applications (Member Service Tool, Loan Processing)  │
└──────────────────────────┬───────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Prompt    │  Versioned templates, variable injection,
                    │  Registry   │  approval workflow
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Output    │  PII detection, hallucination checks,
                    │  Guardrails │  bias screening, compliance filtering
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Compliance  │  Full audit trail, examiner-ready
                    │   Logger    │  exports, retention management
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Model     │  Evaluation suites, bias measurement,
                    │  Evaluator  │  model cards for MRM documentation
                    └─────────────┘
```

### How It Works

**A member calls about a charge on their account. Here's what happens:**

1. The rep pulls up the member's account. The service tool prepares context: account type, recent transactions, membership tenure, open cases.

2. The **Prompt Registry** selects the approved prompt template ("member_service_response_v2.1"), injects the context variables, and logs the complete prompt.

3. The prompt goes to the LLM provider (the credit union uses AWS Bedrock).

4. The response comes back. Before the rep sees it, **Output Guardrails** run 5 checks:
   - **PII scan:** Does the response contain SSNs, account numbers, or member data that shouldn't be surfaced?
   - **Hallucination check:** Does the response reference rates, balances, or fees not in the input context?
   - **Bias screen:** Does the response contain language that could be discriminatory?
   - **Compliance filter:** Does the response make unauthorized claims or guarantees?
   - **Confidence assessment:** Is this a coherent, useful draft or garbage?

5. If checks pass, the draft appears in the rep's interface with a note: "AI-drafted -- review before sending." If any check fails, the draft is blocked and the rep writes their own response.

6. The **Compliance Logger** records everything: input, prompt template, model, raw output, guardrail results, whether the rep sent it as-is, edited it, or discarded it.

7. Monthly, the **Model Evaluator** runs test suites across both use cases. Results feed into the model risk documentation the compliance officer maintains.

---

## Modern Stack Integration

**LangSmith Tracing & Observability**

Complete observability for the governance pipeline:
- `@traceable` decorators on all governance components (prompt rendering, guardrail evaluation, compliance logging)
- Custom evaluators: guardrail accuracy (false positive/negative rates), PII detection (precision/recall), confidence calibration
- Real-time cost tracking per LLM interaction through governance layer
- Trace metadata: prompt version, guardrail version, final decision (deliver/block/warn)

**n8n Automation Workflows**

Two production workflows orchestrate compliance operations:

1. **Compliance Event Router** (`n8n/compliance_event_router.json`)
   - Supabase webhook triggers on compliance_event insert
   - Routes by severity: CRITICAL → PagerDuty + Slack + Email, WARNING → daily digest queue, INFO → logging only
   - Atomically updates notification status and dashboard metrics

2. **Daily Compliance Digest** (`n8n/daily_compliance_digest.json`)
   - Cron job at 8 AM daily
   - Queries yesterday's interactions from Supabase
   - Aggregates: total interactions, block rate, PII caught, cost, guardrail latency
   - Compares trends vs. prior period
   - Generates HTML email with React Email template
   - Stores report in audit_reports table

**Trigger.dev Scheduled Jobs**

Long-running evaluations managed by Trigger.dev:

- `trigger-jobs/model_evaluation.ts`: Monthly comprehensive model evaluation
  - Loads test case suite from guardrail_evals.py
  - Runs through governance pipeline for each model
  - Scores accuracy/bias/compliance/confidence
  - Generates model cards for MRM documentation
  - Stores results; logs completion as compliance event

**React Email Templates**

Production-ready email designs with accessibility:

- `emails/compliance_alert.tsx`: Critical event notifications with interaction details, guardrail info, recommended actions
- `emails/daily_digest.tsx`: Daily metrics summary with trends, unresolved items, quick facts, recommended actions

**Supabase Schema & RLS**

Enterprise-grade database (`supabase/migrations/001_initial_schema.sql`):
- Prompt templates with approval workflows
- Guardrail configurations and versioning
- Immutable interaction logs (append-only for compliance)
- Compliance events with severity routing
- Model evaluations and model cards
- Audit reports and dashboard metrics
- Row-level security policies:
  - Compliance officers see all records
  - Model owners see their models and interactions
  - Examiners get read-only access to audit views

**Configuration & Deployment**

- `.cursorrules`: Governance context for AI-assisted development
- `.replit` + `replit.nix`: Replit environment for cloud development
- `.env.example`: Template for all 20+ environment variables
- `vercel.json`: Deployment configuration with cron triggers for daily digest and monthly evaluation

---

## Modules

| File | Purpose |
|---|---|
| `prompt_registry.py` | Versioned prompt template management. Approval workflows, variable injection, A/B testing support. |
| `output_guardrails.py` | Real-time output screening. PII detection, hallucination detection, bias screening, compliance filtering. |
| `model_evaluator.py` | Systematic model testing. Evaluation suites, bias measurement, drift detection. Generates model risk documentation. |
| `compliance_logger.py` | Complete audit trail. Immutable interaction logs, examiner-ready exports, retention management. |
| `dashboard.jsx` | Governance dashboard. Guardrail metrics, model health, compliance status, evaluation trends. |
| `langsmith/governance_tracing.py` | LangSmith integration with @traceable decorators, custom evaluators, cost tracking. |
| `langsmith/guardrail_evals.py` | 30+ test cases across 5 guardrail types (PII, hallucination, bias, compliance, confidence) with scoring. |
| `n8n/compliance_event_router.json` | Routes compliance events by severity to PagerDuty, Slack, email. |
| `n8n/daily_compliance_digest.json` | Daily 8 AM digest: aggregates metrics, generates trends, emails compliance officer. |
| `trigger-jobs/model_evaluation.ts` | Monthly scheduled evaluation: test suite, model cards, bias detection, MRM documentation. |
| `emails/compliance_alert.tsx` | React Email: critical event alerts with interaction details and recommended actions. |
| `emails/daily_digest.tsx` | React Email: daily metrics summary with trends and open items. |
| `FUTURE_ENHANCEMENTS.md` | Enhancements scoped but not built. |

---

## Engagement & Budget

### Team & Timeline

| Role | Allocation | Duration |
|------|-----------|----------|
| Lead PM (Jacob) | 15 hrs/week | 12 weeks |
| Lead Developer (US) | 35 hrs/week | 12 weeks |
| Offshore Developer(s) | 1 × 35 hrs/week | 12 weeks |
| QA Engineer | 15 hrs/week | 12 weeks |

**Timeline:** 12 weeks total across 3 phases
- **Phase 1: Discovery & Design** (2 weeks) — NCUA compliance requirements mapping, AI use case inventory, guardrail framework design, prompt library architecture
- **Phase 2: Core Build** (7 weeks) — Prompt management system, output screening pipeline, audit logging, model evaluation framework, compliance dashboard
- **Phase 3: Integration & Launch** (3 weeks) — LangSmith integration, staff training materials, NCUA exam documentation, pilot with member services team

### Budget Summary

| Category | Cost | Notes |
|----------|------|-------|
| PM & Strategy | $33,300 | Discovery, specs, stakeholder management |
| Development (Lead + Offshore) | $89,460 | Core platform build |
| AI/LLM Token Budget | $2,400/month | Claude Haiku for guardrail screening ~3M tokens/month |
| Infrastructure | $3,840/month | Supabase Pro, n8n, Trigger.dev, Vercel, misc |
| **Total Engagement** | **$130,000** | Fixed-price, phases billed at milestones |
| **Ongoing Run Rate** | **$650/month** | Infrastructure + AI tokens + 2hrs support |

---

## Client Context

**Credit union profile:**
- Small community credit union, NCUA-insured
- Small IT department: CIO, a couple of developers, infrastructure and helpdesk staff
- No data science team. No AI experience prior to this engagement.
- Core banking: Symitar (Jack Henry). Call center: Genesys Cloud.
- Compliance team: 1 compliance officer handling multiple functions (also covers BSA, vendor management)

**Regulatory situation:**
- NCUA is their primary regulator
- NCUA hasn't issued formal GenAI-specific guidance but has informally indicated that FFIEC model risk management principles apply
- Examiner specifically asked "what's your plan for AI governance?" during the prior exam cycle
- The compliance officer had no answer beyond "we're working on it"
- No consent orders or enforcement actions, but the examiner's question made it clear this was on their radar

**GenAI use cases:**

1. **Member service copilot** -- draft responses for call center reps. Rep reviews and edits before sending. Covers balance inquiries, transaction disputes, product questions, and general service requests. Target: reduce average handle time by 20-25%.

2. **Loan document summarizer** -- extract key terms, conditions, and data points from loan applications and supporting documents. Used by loan processors, not member-facing.

**Before this platform:**
- 2 GenAI use cases prototyped by a developer using OpenAI's API directly
- Neither could go to production because the compliance officer couldn't document the risk controls
- No prompt versioning -- prompts were hardcoded strings in a Python script
- No output monitoring of any kind
- No audit trail
- No way to answer the NCUA examiner's questions about AI governance
- Months of development work stuck behind compliance sign-off
- Board getting impatient about the digital transformation budget sitting unspent

**After deployment (first quarter in production):**
- 2 use cases deployed to production (compliance officer signed off)
- 43,000+ LLM interactions processed through the governance layer
- 2.6% of outputs blocked by guardrails before reaching the rep
- 0.5% of member service outputs contained PII that would have been surfaced without screening
- Average handle time dropped from 7.2 to 5.8 minutes (on track for target)
- Loan document review time reduced by ~35%
- 0 findings related to AI in the next NCUA exam
- Examiner noted the governance framework positively in the exam report
- Compliance officer can now produce examiner-ready documentation in under an hour
- Model risk documentation passed internal audit review

---

## How Governance Actually Works in Practice

**The prompt change that almost went wrong:**

Week 2 of production. The developer wants to improve response quality for balance inquiries. He updates the system prompt: "When the member asks about their balance, provide the exact current balance and recent transactions." Sounds reasonable. Problem: the context injected into the prompt only includes the last 5 transactions. The model would fill in "recent transactions" by hallucinating plausible-looking entries that don't exist.

Without the prompt registry, that change goes straight to production. The developer pushes code, reps start getting responses with fake transaction details, a member notices their statement doesn't match, calls back angry, and the supervisor escalates. With the registry, the change triggers a review. The compliance officer runs it through the evaluation suite and catches the hallucination risk in testing. The developer revises the prompt: "Reference only the transactions listed in the context below." Fixed before it was ever a problem.

**The bias finding that nobody expected:**

Month 2. The model evaluator runs monthly bias testing on the member service copilot. The test set uses the same inquiry with different member profiles. The evaluator detects that responses to members with accounts under $5,000 are shorter and less detailed than responses to members with accounts over $50,000. The model was providing better service to wealthier members.

Not discriminatory in a legal sense (account balance isn't a protected class), but it violated the credit union's core principle of equal member service. The cooperative charter means every member gets the same quality of service regardless of their balance. The team adjusted the system prompt to explicitly instruct consistent response quality regardless of account size, and re-tested until the disparity dropped below threshold.

The compliance officer included this finding and remediation in the model risk documentation. The examiner later noted it as an example of effective model monitoring.

**The exam that proved the system worked:**

NCUA exam, first cycle after deployment. The examiner asks three questions about AI:
1. "What AI models are you using in member-facing applications?"
2. "How do you validate and monitor these models?"
3. "Can you show me records of AI-assisted member interactions?"

The compliance logger produces all three answers in under an hour. Model cards for both use cases with validation results. Interaction logs with guardrail outcomes. Prompt version history with the approval chain. The compliance officer walks the examiner through the governance dashboard live.

The examiner's feedback: "This is ahead of where most institutions your size are. Keep documenting."

A year ago, the same examiner's question got a blank stare. Now it gets a live dashboard.

---

## Technical Notes

- Python 3.11+, React with Recharts
- Designed for AWS deployment (Bedrock for LLM access, S3 for log storage)
- No direct LLM dependencies -- the governance layer is model-agnostic
- Guardrail checks use regex, pattern matching, and statistical methods (not additional LLM calls)
- PII detection uses regex patterns for financial services PII (SSN, account numbers, routing numbers, DOB)
- Compliance logger uses append-only storage pattern for audit integrity
- In production, logs stored in S3 with Object Lock for retention compliance
- All modules include synthetic data for portfolio demonstration

---

## PM Perspective

Hardest decision: Rule-based guardrails vs. LLM-as-a-judge for output screening. LLM-based screening would catch more edge cases, but the compliance officer was adamant: "I need to explain every blocked output to the examiner." Rule-based screening with explicit pattern matching (PII regex, prohibited term lists, confidence thresholds) was explainable. We compromised — rule-based for PII/compliance screening (deterministic, auditable), with a Claude Haiku classifier as a secondary check for hallucination and bias that flagged for human review rather than auto-blocking.

Surprise: The credit union's IT team was terrified of AI, not excited. They'd seen the headlines about ChatGPT hallucinations and expected regulators to penalize them. The breakthrough was building the "Model Card" documentation system — a standardized template showing exactly what each AI feature does, what data it accesses, and what guardrails protect it. The compliance officer took those model cards into the NCUA exam and the examiner called them "best practice." That single deliverable sold the entire engagement.

Do differently: Would have started with the audit trail before the guardrails. We built the screening pipeline first, then the logging system. But the compliance officer's #1 question from week one was "can you prove what the AI said to our members?" Starting with comprehensive audit logging would have given them confidence earlier and reduced the resistance we faced in the first month.

---

## Business Context

**Market:** 4,700+ credit unions in the US (NCUA), with ~2,800 between $100M-$10B in assets actively evaluating AI tools for member services. Compliance-first AI governance is a prerequisite for adoption in regulated financial services.

**Unit Economics:**

| Metric | Before | After |
|--------|--------|-------|
| Annual compliance cost | $85,000/year | Automated governance |
| Compliance review time | 120+ hours | Continuous monitoring |
| Annual savings | — | $60,000 |
| Risk avoided | — | $250K+ exam findings |
| Platform cost (build) | — | $130,000 |
| Platform cost (monthly) | — | $650 |
| Payback period | — | 8 months |
| 3-year ROI | — | 5x |

**Pricing:** If productized for credit unions and community banks, $1,500-3,000/month based on asset size and AI use case count, targeting $5-8M ARR at 300 institutions.

---

## About This Project

This was built for a small community credit union (NCUA-regulated, ~200K members) that needed a governance framework before expanding AI-assisted member services.

**Role & Leadership:**
- Led discovery with compliance officers, member services leads, and IT to map AI use cases and regulatory requirements
- Designed the prompt management and output screening architecture ensuring NCUA/FFIEC compliance
- Made technology decisions on guardrail approach (rule-based screening vs. LLM-based classification)
- Established metrics framework for guardrail effectiveness, handle time impact, and examination readiness
