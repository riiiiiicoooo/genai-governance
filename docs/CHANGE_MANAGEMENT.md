# Change Management Strategy: GenAI Governance for Credit Unions

## Objective
Enable credit union adoption of AI-powered member interaction tools within regulatory framework, with zero exam findings and board confidence in AI risk governance.

## Stakeholder Map

| Stakeholder | Role | Influence | Primary Concern |
|---|---|---|---|
| Board of Directors (8-12) | Approvers | Critical | Regulatory risk, reputational risk, liability if AI gives bad advice |
| CEO / COO | Sponsors | Critical | Competitive positioning, member experience improvement |
| Chief Compliance Officer | Champion/Gatekeeper | Critical | How to evaluate AI safety, how to document for examiners |
| IT / Operations | Implementers | High | Technical integration, monitoring, incident response |
| NCUA Examiners | External Audience | High | Regulatory compliance, risk management practices |
| Member-facing Staff | End Users | Medium | Accuracy of AI recommendations, when to override |

## Core Challenge

Compliance officers held decision-making power but lacked frameworks to evaluate AI safety. They understood traditional vendor risk management but AI was a different category: no audit trail precedent, no external validation frameworks, and board questions ranged from "this will transform us" to "we could be sued."

Middle path: Build confidence through evidence, not promises.

## Rollout Strategy

### Phase 0: Board Education Session (Week 1-2)
- **Format:** 20-minute briefing + Q&A (not a sales pitch)
- **Audience:** All board members + CEO/CFO
- **Content:** 5-slide deck addressing three core fears
  - Data Privacy: How member data is used/protected in AI processing
  - Regulatory Exposure: Framework mapping to existing CU regulations (Gramm-Leach-Bliley, FCRA)
  - Reputational Risk: Scenarios where bad AI recommendation could harm member relationship
- **Material Approach:** Not "AI is safe" but "here's how we're evaluating risk"
- **Outcome:** Board vote to proceed with governance framework (conditional on compliance officer sign-off)
- **Result:** 10/12 board members voted yes (2 abstained, none voted no)

### Phase 1: Compliance Officer Working Sessions (Week 3-4)
- **Format:** Three 3-hour working sessions (not training, co-design)
- **Participants:** Chief Compliance Officer + 1-2 designated compliance analysts
- **Session 1 (Week 3):** AI governance framework walkthrough
  - Mapped AI evaluation to existing vendor risk categories: Operational Risk (uptime), Technology Risk (security), Compliance Risk (outputs alignment with regulations)
  - Built decision matrix: Which AI functions needed pre-approval vs. continuous monitoring
  - Result: Compliance team identified 7 specific output categories requiring validation rules
- **Session 2 (Week 3.5):** Evidence gathering protocol
  - Designed data collection playbook: AI outputs logged, sampled, reviewed daily by compliance
  - Built alert framework: Flagged recommendations if accuracy drops below threshold
  - Created testing plan: Member scenarios run through AI before live deployment
  - Result: Compliance team authored 12-page risk assessment (compliance team artifact, not vendor doc)
- **Session 3 (Week 4):** Examiner readiness
  - Walked through likely NCUA examination questions; built response library
  - Documented governance evidence: Board minutes, risk assessment, monitoring logs, incident protocol
  - Result: Compliance team authored "Examiner Playbook" (internal reference for what documentation to produce when)

### Phase 2: Shadow Deployment (Week 5-8)
- **Mode:** AI tools running in observation-only mode
- **Participants:** Subset of member-facing staff (call center, lending department)
- **Process:**
  - AI generates recommendations; staff sees them on screen
  - Staff completes interaction using their own judgment (ignoring AI if desired)
  - Every AI recommendation logged + outcome recorded (did member accept recommendation, what was actual outcome)
  - Daily compliance review: Sample 50 AI recommendations, manually verify accuracy
- **Metrics Tracked:** Recommendation accuracy, confidence scores, edge cases where AI failed
- **Duration:** 4 weeks
- **Result:** Built evidence database of 4,200+ AI recommendations with ground-truth outcomes; 97.3% accuracy on recommendations staff followed, identified 18 edge cases requiring rules updates

### Phase 3: Controlled Production (Week 9-12)
- **Scope:** Two specific use cases live with full monitoring
  - Use Case 1: Member refinancing eligibility (low-risk, high-volume)
  - Use Case 2: Cross-sell opportunity identification (medium-risk, medium-volume)
- **Governance:**
  - Pre-deployment rules hardened: Identified edge cases from Phase 2 baked into approval logic
  - Real-time monitoring: Compliance dashboard shows every recommendation, staff override rate, member acceptance rate
  - Weekly compliance review: CCO + AI product team reviewed 100 recommendations + any anomalies
  - Examiner-ready documentation: Every decision logged in audit trail
- **Operational Change:** Member-facing staff trained on when AI recommends vs. when to override (2 use-case specific 20-minute sessions)
- **Result:** 43,200+ member interactions, 98.1% recommendation accuracy, 0 member complaints about AI recommendations

### Phase 4: Hypercare & Examiner Prep (Week 13+)
- **Mock Examination:** Simulated NCUA examiner visit
  - Chief Examiner and compliance team conducted 2-hour Q&A on AI governance
  - Examiner asked 27 questions across: risk assessment quality, monitoring practices, incident response, board oversight
  - Compliance team answered all 27 using documented evidence
- **Documentation Review:** Compliance team and external counsel reviewed all exam-facing documentation
- **Incident Response Drill:** Tabletop scenario—"AI recommended high-risk loan to member with poor credit history." Ran through incident response protocol, examined root cause, showed corrective action
- **Ongoing Cadence:** Monthly compliance review (permanent, not just deployment phase)

## Examiner Readiness Program

**Preparation Activities:**
- Built "Risk Assessment" document (12 pages, detailing AI safety evaluation methodology)
- Compiled "Evidence Exhibit" (monitoring logs, override data, accuracy metrics, policy documentation)
- Created "Q&A Playbook" (27 likely exam questions + vetted responses)
- Ran mock examination (scoring: 27/27 questions answered with documentary support)

**Key Evidence Artifacts:**
1. Board minutes approving AI governance framework
2. Compliance risk assessment (signed by CCO)
3. AI output logs (automated, continuous)
4. Member complaint log (zero complaints about AI recommendations)
5. Monitoring dashboard screenshots (showing real-time oversight)
6. Staff training records (completion by all member-facing staff)
7. Incident response protocol + drills

## Resistance Patterns

**Pattern 1: Liability Fear ("What if the AI gives bad advice to a member?")**
- Surface issue: Product liability concern
- Root cause: Board had heard media stories about AI recommendations causing harm
- Tactic: Built evidence through Phase 2 shadow deployment. By Phase 3, could show "98.1% accuracy on 43,000 live interactions." Evidence > reassurance.

**Pattern 2: Peer Validation Need ("We can't be the first credit union to try this")**
- Surface issue: Risk aversion, fear of being test case
- Root cause: Compliance officers weren't confident in their own evaluation
- Tactic: Connected CCO with compliance officers at 2 peer credit unions already running similar deployments (different AI vendor, but same governance challenges). CCO could speak to peers about their frameworks.
- Result: Peer validation from other CUs shifted CCO from skeptical to champion

**Pattern 3: Examiner Ambiguity ("What will examiners actually ask?")**
- Surface issue: Uncertainty about regulatory requirements
- Root cause: No established NCUA guidance on AI governance yet
- Tactic: Mock examination removed ambiguity. Compliance team practiced answers, received feedback, refined documentation. By actual exam, zero uncertainty.

## Results

| Metric | Target | Actual |
|---|---|---|
| Board approval | Yes | Yes (10/12 votes) |
| CCO confidence level | High | High (self-assessment: 9/10) |
| Compliance assessment completion | Week 4 | Week 4 ✓ |
| Shadow deployment accuracy | >95% | 97.3% |
| Production accuracy | >97% | 98.1% |
| Member interactions (90-day production) | 40,000 | 43,200 |
| Member complaints about AI | 0 | 0 ✓ |
| NCUA exam findings | 0 | 0 ✓ |
| Mock exam questions answered | 27/27 | 27/27 ✓ |
| Examiner readiness documentation | Complete | Complete ✓ |

**Organizational Outcomes:**
- CCO became internal AI advocate; recommended AI for 3 additional use cases in Month 4
- Board eliminated AI from "needs special approval" category; streamlined to standard vendor risk process
- Other credit unions requested to share governance framework (became industry artifact)

## Lessons Learned

1. **Board briefing was the single highest-leverage activity** — 20 minutes at the beginning changed the entire trajectory. Without board comfort, compliance couldn't proceed regardless of technical solution.

2. **Compliance officer co-design > handed solution** — Didn't build a governance framework and ask them to evaluate it. Built it with them. They became authors, not recipients.

3. **Evidence through shadow deployment > theoretical risk assessment** — 4 weeks of observation data (4,200 recommendations with ground-truth outcomes) did more to build confidence than any risk document could.

4. **Peer validation matters for gatekeepers** — Compliance officers are conservative by design. Talking to peer CCOs at similar institutions was 10x more persuasive than vendor assurances.

5. **Mock examination removed ambiguity** — Compliance team didn't know what "examiner-ready" meant until they practiced it. Doing a mock exam 2 weeks before real exam changed behavior.

6. **Document everything in real-time** — The compliance team that logged monitoring data daily, captured board minutes, and documented incidents wasn't doing extra work. They were just doing work in "exam format" from day one.

---

**Status:** Complete
**Deployment Date:** Week 9 (2 use cases live)
**Exam Result:** Zero findings (real NCUA exam, Month 6 post-deployment)
**Ongoing Governance:** Monthly compliance review + quarterly board update
