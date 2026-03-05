# User Research: AI Governance in Credit Unions
**Research Period**: Q3 2023 (July–September)
**Conducted by**: PM team, 3 weeks
**Status**: Complete

---

## Research Objectives

Understand readiness and barriers for AI deployment in regulated financial services, specifically:
- How compliance teams currently frame AI risk
- What frameworks they lack vs. what tools they need
- How regulatory uncertainty blocks adoption despite business interest
- What examiner expectations actually are (vs. assumed)

---

## Methodology

**Sample**: 7 interviews conducted over 3 weeks
- 3 Credit Union Compliance Officers (CUs with $500M–$2.1B assets, all NCUA-insured)
- 2 CIOs/CTOs at same institutions
- 1 NCUA examiner contact (informal advisory conversation, not formal guidance)
- 1 Third-party Risk Management lead (vendor risk assessment background)

**Interview Length**: 45–60 minutes each
**Format**: Structured with 8–10 core questions; exploratory follow-ups on regulatory assumptions

**Recruiting**: Direct outreach through regional compliance networks; participants consented to aggregate findings being shared

---

## Participant Profiles

**CO-1**: Compliance Officer, $1.2B CU in Southwest region
- 9 years in credit union compliance
- Reports to Chief Risk Officer
- Manages 2 compliance staff
- Current tech stack: manual spreadsheets for audit tracking, vendor risk in Excel
- Most recent exam: 6 months prior, no AI findings

**CO-2**: Compliance Officer, $680M CU in Midwest
- 12 years compliance, 5 at current CU
- Embedded in digital transformation initiative
- Pressing leadership for AI chatbot for member support
- Vendor risk framework: custom matrix tied to NCUA guidance
- Recent exam findings: unrelated (teller reconciliation process)

**CO-3**: Compliance Officer, $2.1B CU in Southeast
- 7 years compliance background (2 at prior bank)
- Tech-forward; piloting RPA for transaction monitoring
- Leadership interested in AI-assisted underwriting
- Has relationship with NCUA field office examiner

**CIO-1 & CIO-2**: Technology leaders at CO-1 and CO-3 institutions
- CIO-1: IT director, no dedicated AI/data science team
- CIO-3: Technology VP, one data analyst on staff
- Both cited difficulty recruiting AI talent to smaller institutions

**Examiner Contact**: NCUA field examiner (Southwest region)
- Informal advisory call; not conducting official guidance session
- ~15 years examination experience across credit unions
- Recently attended NCUA training on AI risk assessment (internal)

**Vendor Risk Lead**: Former regulatory consultant, now heads third-party risk at fintech vendor
- Perspective on how CUs assess vendor AI risk
- Direct interaction with 40+ credit union procurement processes in past 2 years

---

## Key Findings

### 1. Compliance Teams Want to Say Yes But Lack a Framework for "Safe"

**Finding**: All 3 compliance officers expressed leadership pressure to enable AI capabilities (chatbots, document automation, underwriting support). None felt outright opposed to AI. However, all three independently stated they "don't have the language to approve it" — they have regulatory instinct but no control framework.

**Evidence**:
- CO-2: "Our CEO wants a chatbot for member questions. I'm not against it, but I need to know: what does it do wrong, and how do I prove we caught it?"
- CO-1: "I could write a policy, but it would just be copying language I see online. I need something that's specific to what our system actually does."
- CIO-1: "We could build this, but our board would ask our compliance officer 'Is this safe?' and we don't have an answer framework."

**Implication**: The barrier is not regulatory conservatism; it's **lack of a control taxonomy** that translates business risk into compliance risk.

---

### 2. Examiners Ask 4 Specific Questions—Always

**Finding**: Through CO-3's relationship with their NCUA examiner and the informal examiner call, we identified the precise examiner framework. Examiners consistently ask:
1. "What AI systems are you using?" (inventory)
2. "How do you control outputs?" (guardrails)
3. "Can you show me the audit trail?" (accountability)
4. "How do you test for bias?" (fairness/model risk)

**Evidence**:
- Examiner contact confirmed these 4 questions appear in recent NCUA internal guidance (not yet public)
- CO-3 proactively prepared for these questions in anticipation of next exam cycle
- All CIOs independently guessed question #1 and #3; none mentioned bias testing

**Implication**: Examiner-first design beats compliance-first design. Product must answer these 4 questions cleanly, with evidence the institution can point to.

---

### 3. Vendor Risk Frameworks Don't Cover AI—Major Operational Gap

**Finding**: All three CUs use vendor risk assessment templates based on FFIEC guidance or NCUA SR 11-7. When asked "Where in your vendor risk process do you assess AI?", all three said: "It's not there."

**Evidence**:
- CO-1 showed their vendor risk matrix (shared with permission). 47 questions on data security, disaster recovery, financial stability. Zero on model transparency, prompt audit logging, or output validation.
- Vendor Risk Lead confirmed: "I've audited 40+ vendor assessments in 2024. Less than 5 mention AI controls. Most CUs are adapting existing frameworks or asking vendors ad-hoc questions."
- CO-2: "We bought [RPA vendor] last year. I had no way to ask about their AI safety practices because our risk template didn't have a section for it."

**Implication**: Compliance teams will adopt AI governance controls faster if they're built into their existing vendor risk workflow, not as a separate module.

---

### 4. PII in Prompts Is the #1 Regulatory Fear

**Finding**: When asked about specific AI risks, all three compliance officers listed PII exposure (customer account data sent to external AI systems) as their immediate concern. This isn't theoretical—members have already started pasting account info into chatbots at competitor institutions.

**Evidence**:
- CO-1: "Members will put their account number in a chatbot to ask a question. I can't prove that data stays internal. That's my nightmare."
- CO-2: "One of our peer CUs had a member paste a social security number into their [vendor] chatbot. The vendor said it wasn't stored, but who verifies that?"
- CIO-1: "Any AI system we build has to have hard constraints on what data can be sent to the model. Full stop."

**Implication**: Data isolation is table-stakes; must be explicitly visible in audit logs and dashboard. "Trust us" is not sufficient.

---

### 5. "Hallucination" Is Regulatory Jargon That Fails

**Finding**: When we used the term "hallucination," compliance officers and examiners visibly reacted with skepticism. The term is too casual for regulated risk. They prefer "inaccurate output" or "unsupported claim."

**Evidence**:
- Examiner contact: "Hallucination sounds like an error excuse. I need 'the system generated information not present in its training data' or 'output contradicted source material.' Language matters in exams."
- CO-3: "If I use 'hallucination' in a board memo, they'll think I'm not serious. I'd say 'the system can produce inaccurate responses that appear confident.'"

**Implication**: Governance product must use precise, risk-based terminology. Marketing language undermines credibility with compliance buyers.

---

### 6. Board Education Is a Prerequisite—15 Minutes, Not 60 Pages

**Finding**: All three COs mentioned they need to educate their board before governance controls can be approved. They all expressed frustration with vendor whitepapers and detailed technical docs. What works: 15-minute executive summary.

**Evidence**:
- CO-1: "I need to explain AI risk to a board of 13 people, 2 of whom have email signatures. A 60-page risk assessment doesn't work. I need 3 slides and 5 talking points."
- CO-2: "If I can't explain it in 15 minutes, I don't understand it well enough. The board won't read a document."
- CIO-3: "Our board asked 'What is AI?' last month. Now they're asking 'What is AI risk?' That's progress, but I need concise answers."

**Implication**: Product must include board-ready dashboards and executive summaries, not assume regulatory teams will translate technical outputs.

---

## Regulatory Context

**NCUA SR 11-7** (Guidance on Third-Party Relationships): Requires CUs to assess third-party AI vendor risk as part of due diligence. Exam focus: vendor transparency, data handling, output validation.

**NCUA AI Risk Webinars** (2023): Examiners emphasized need for inventory, audit trails, and testing. No prescriptive controls yet, which creates the gap we observed.

**FFIEC Guidance** (pending): Broader banking AI guidance expected Q4 2024; will likely establish baseline controls. Early movers can shape expectations.

---

## How This Shaped the Product

### Feature 1: Examiner-First Control Taxonomy
Mapped the 4 examiner questions directly into product structure:
- Inventory module: List all AI systems in use, vendor, data flows
- Guardrail controls: Template library with categories (PII, tone, accuracy, bias)
- Audit trail: Every prompt, response, and guardrail trigger logged with timestamp and user
- Testing module: Bias test templates and result tracking

### Feature 2: Vendor Risk Integration
Added AI-specific assessment to existing vendor risk workflow rather than creating separate product:
- New section in vendor risk questionnaire: 8 AI-focused questions tied to NCUA expectations
- Import vendor risk scores into governance dashboard
- Allow institutions to flag which AI systems are third-party vs. internal

### Feature 3: PII Guardrail as First Control
Made data isolation the default, most visible control:
- Regex-based detection for account numbers, SSNs, phone numbers in prompts
- Visual dashboard showing PII detection rate and false positive rate
- Exportable reports for compliance files

### Feature 4: Board-Ready Dashboards
Built executive summary that doesn't require compliance translation:
- One-page risk summary (green/yellow/red status)
- 3-minute "AI Risk for the Board" video template
- Control maturity benchmarks vs. peer institutions (anonymized)

### Feature 5: Language Precision
Replaced casual AI language with regulatory terminology:
- "Inaccurate output detection" not "hallucination prevention"
- "Model accountability" not "explainability"
- "Output validation" not "trustworthiness"

---

## What Didn't Get Built (Yet)

- **Model performance monitoring**: CUs don't have data science teams to interpret model drift. Deferred to Phase 2.
- **Bias audit templates**: Too nascent; examiners haven't yet standardized what "testing for bias" means. Waiting for FFIEC guidance.
- **Multi-institution benchmarking**: Privacy concerns about sharing control maturity data across CUs. Needs legal review.

---

## Research Quality Notes

- **Bias**: All participants were in Southwest or Midwest regions; bias toward larger CUs ($500M+). Smaller CUs (<$200M) may have different constraints (no dedicated compliance staff).
- **Examiner data**: One informal conversation, not representative of all NCUA examiners. Treated as directional, validated against available NCUA publications.
- **Timing**: July 2023; NCUA and FFIEC guidance is evolving. Product assumptions should be revisited quarterly.

---

**Next Steps**: Monitor FFIEC AI guidance publication (expected Q4 2024); re-interview 2 compliance officers to validate control framework after public guidance released.
