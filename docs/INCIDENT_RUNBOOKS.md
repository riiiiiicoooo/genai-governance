# GenAI Governance Platform — Incident Runbooks

**Last Updated:** March 2026
**Severity Levels:** P0 (guardrail fails to block PII/hallucination, regulatory violation), P1 (SLO breach), P2 (degraded performance)

---

## Incident Runbook 1: Guardrail Failure — PII or Hallucination Reaches Member

**Likelihood:** Very low (goal <1 per year; baseline target is 99.5% accuracy)
**Severity:** P0 (regulatory violation, potential harm to member)
**Detection Symptoms:** Member reports PII exposure ("AI told me my SSN back"), or audit shows output contains undetected PII/hallucination

### Detection

**Automated triggers:**
- Guardrail review finds output with PII that should have been blocked: `SSN` or `DOB` in output with `guardrail_decision = DELIVER`
- Hallucination detector (downstream) finds ungrounded financial figure in output (e.g., "You will earn 12% interest" not in input context)
- Member report: "The AI told me to invest in company X which we don't offer"

**Manual triggers:**
- Call center advisor: "The AI recommended something we don't actually provide"
- Member complaint: "The AI exposed my social security number"

### Diagnosis (First 30 minutes)

1. **Confirm guardrail failure:**
   ```sql
   SELECT * FROM interaction_audit_log
   WHERE output LIKE '%[0-9]{3}-[0-9]{2}-[0-9]{4}%'
   AND guardrail_decision = 'DELIVER'
   AND created_at > NOW() - INTERVAL '24 hours'
   ORDER BY created_at DESC;
   ```
   Find all outputs containing PII patterns that were not blocked.

2. **Identify which guardrail failed:**
   - Is PII detector working? (Check confidence scores)
   - Is hallucination detector enabled? (Check config)
   - Which specific check failed? (PII regex, ML model, compliance rule, etc.)

3. **Scope the exposure:**
   ```sql
   SELECT COUNT(*), MIN(created_at), MAX(created_at)
   FROM interaction_audit_log
   WHERE output LIKE '%[0-9]{3}-[0-9]{2}-[0-9]{4}%'
   AND guardrail_decision = 'DELIVER'
   AND created_at > NOW() - INTERVAL '7 days';
   ```
   How many members were exposed? For how long?

4. **Check if PII was from input or hallucinated:**
   - If PII was in member's input and regurgitated by LLM: PII detector should have caught it
   - If PII was hallucinated (not in input): Hallucination detector should have caught it
   - If PII was from output of another system (e.g., database lookup): Architecture issue

### Remediation (First 2 hours)

**Immediate:**
1. **Stop further exposure:**
   - If guardrail check was disabled: Re-enable immediately
   - If check is failing: Disable it and use manual review fallback
   - Example: If PII detector is broken, route all outputs to human reviewer for approval

2. **Assess member harm:**
   - Did member's PII reach external system? (e.g., was output sent to Slack, email, saved to database?)
   - Or was PII only shown to advisor on screen (contained, lower risk)?
   - Did member take action based on hallucinated advice? (e.g., invested in non-existent product)

3. **Member notification (if PII exposed to advisor):**
   - Document which member, what PII, when exposed
   - Check if notification required per privacy policy

**Within 4 hours:**
1. **Root cause analysis:**
   - Why did guardrail fail? (Check detection model performance on test cases)
   - Was check disabled? (Check deployment history)
   - Was threshold too lenient? (Check guardrail configuration vs. baseline)
   - Was model drift? (Compare model accuracy over time)

2. **Fix the guardrail:**
   - If regex pattern wrong: Update pattern and test against examples
   - If ML model accuracy dropped: Retrain on recent data or roll back to previous model
   - If check was disabled: Re-enable and test thoroughly before deploy

3. **Deploy guard:**
   - Strict deployment: Update guardrail, add it to integration tests, deploy to canary first
   - Test plan: Confirm guardrail catches the same PII pattern on test cases
   - Rollout: Deploy to production with monitoring

**Within 24 hours:**
1. **Regulatory notification:**
   - Was this a member privacy breach? → Notify state banking regulator
   - Was this a hallucination causing financial harm? → Notify NCUA compliance officer
   - Document: What happened, when, how many affected, what action taken

2. **Comprehensive audit:**
   - Run guardrail on all historical outputs (last 30 days)
   - Find all instances of same PII pattern or hallucination pattern
   - Determine if other members were affected

### Communication Template

**Internal (Slack #incident-ops):**
```
🚨 P0: Guardrail Failure — [PII/HALLUCINATION] Not Blocked

Timeline:
- [TIME 1]: Guardrail check failed (output delivered with [PII/HALLUCINATION])
- [TIME 2]: Issue discovered by [METHOD]
- [TIME 3]: Guardrail disabled/fixed

Scope:
- Affected members: [N]
- Exposure type: [PII type or hallucination description]
- Reach: [Advisor only / External system / Member's eyes]
- Duration: [TIME PERIOD]

Root cause: [Disabled check / Model accuracy dropped / Configuration changed]

Actions:
- [x] Guardrail disabled/fixed
- [ ] Root cause analysis
- [ ] Test cases added to prevent recurrence
- [ ] Member notification [if needed]
- [ ] Regulatory notification [if needed]

Regulatory impact: [ASSESS NOW]
On-call: [NAME]
Next: RCA at [TIME], regulatory assessment at [TIME]
```

**Member notification (if required):**
```
Subject: Important Notice — Confidentiality Incident

Dear [MEMBER],

We are writing to inform you of an incident affecting your privacy with [CREDIT UNION].

On [DATE], our AI system inadvertently shared your [INFORMATION] with a call center advisor
in a way that violated our confidentiality standards. We have immediately:
- Disabled the system feature that caused this
- Enhanced our controls to prevent this in the future
- Reviewed all interactions to determine scope

Your information was only visible to our staff member [ADVISOR NAME], and was not shared
externally or saved to any system. However, we wanted to inform you promptly.

If you have concerns, please contact our privacy officer at [CONTACT].
```

---

## Incident Runbook 2: Prompt Deployed Without Compliance Approval

**Likelihood:** Low (goal is 100% approval; deployment should be blocked if approval missing)
**Severity:** P0 (regulatory violation; unapproved prompt in production)
**Detection Symptoms:** Prompt appears in production without approval record, or advisor reports "new prompt that I didn't see reviewed"

### Detection

**Automated triggers:**
- Deployment pipeline detects prompt version in production with `approval_status != 'APPROVED'`
- Approval workflow audit shows gap: Prompt deployed at [TIME] but approval_at = NULL

**Manual triggers:**
- Compliance officer: "This prompt is in production; where's the approval?"
- NCUA examiner asks: "Show me the approval for this prompt" and we can't find it

### Diagnosis (First 30 minutes)

1. **Confirm approval is missing:**
   ```sql
   SELECT * FROM prompt_versions
   WHERE status = 'DEPLOYED'
   AND (approved_by IS NULL OR approved_at IS NULL)
   ORDER BY deployed_at DESC;
   ```

2. **Identify the gap:**
   - When was prompt deployed?
   - Who deployed it?
   - Was the approval workflow enforced? (Check deployment logs)
   - Did someone bypass the approval requirement?

3. **Assess impact:**
   - How long has unapproved prompt been in production?
   - How many members saw the prompt?
   - Was the prompt problematic (contained bias, hallucinations, etc.)?

### Remediation (First 1 hour)

**Immediate:**
1. **Rollback:**
   - Deploy previous approved version immediately
   - ```bash
     kubectl set image deployment/genai-governance \
       genai=registry/genai-governance:PREVIOUS_APPROVED_VERSION
     ```

2. **Implement approval enforcement:**
   - If deployment pipeline didn't enforce approval: Fix pipeline
   - Add gate: Deployment will not proceed if approval missing
   - Example: CI/CD check before merge
     ```yaml
     approval_required: true
     approval_gate:
       path: .github/APPROVAL
       role: compliance_officer
     ```

**Within 24 hours:**
1. **Investigate bypass:**
   - How did unapproved prompt reach production?
   - Was workflow enforced but someone manually deployed? (Manual override)
   - Was workflow skipped due to emergency? (War room override, needs documentation)

2. **Remediate:**
   - If workflow broken: Fix and re-enable
   - If manual override: Add approval retroactively + documentation
   - If emergency deployment: Create process for emergency approvals (expedited, but still documented)

3. **Regulatory notification:**
   - NCUA wants to see: Approval workflow exists and is enforced
   - Document: What happened, when, how you fixed it, how you'll prevent recurrence

### Communication Template

**Internal (Slack #incident-ops):**
```
🚨 P0: Unapproved Prompt in Production

Timeline:
- [TIME 1]: Prompt deployed
- [TIME 2]: Missing approval detected
- [TIME 3]: Previous version rolled back

Scope:
- Prompt: [NAME]
- Duration in production: [TIME]
- Members affected: [N]
- Approval bypass: [Manual override / Workflow broken / Emergency]

Root cause: [Workflow not enforced / Manual override / Other]

Actions:
- [x] Unapproved version rolled back
- [x] Previous approved version redeployed
- [ ] Deployment workflow fix verified
- [ ] Approval obtained retroactively [if needed]
- [ ] Regulatory notification [if needed]

Prevention: [Strengthen deployment gates / Add approval checksum / Other]
Regulatory impact: [ASSESS NOW]
```

---

## Incident Runbook 3: Audit Trail Corruption or Loss

**Likelihood:** Very low (goal 99.99%)
**Severity:** P1 (compliance violation; regulators lose trust in audit trail)
**Detection Symptoms:** Audit log gap (no records for time period), audit record exists in database but not in S3, or S3 Object Lock validation fails

### Detection

**Automated triggers:**
- Audit log health check finds gap: No audit entries for 1+ hour (should have ~600 at baseline)
- S3 Object Lock validation fails: Audit log objects are modifiable (should be immutable)
- Audit record mismatch: Interaction exists in PostgreSQL but not in S3

**Manual triggers:**
- Compliance officer: "I'm trying to pull audit for [DATE] and there are no records"
- NCUA examiner: "Show me audit trail for [MEMBER] on [DATE]" and we find gaps

### Diagnosis (First 30 minutes)

1. **Verify logging is working now:**
   ```sql
   SELECT COUNT(*), MAX(created_at) FROM interaction_audit_log
   WHERE created_at > NOW() - INTERVAL '5 minutes';
   ```
   If count is normal, logging is working; issue is historical.

2. **Identify the gap:**
   ```sql
   SELECT
     DATE_TRUNC('hour', created_at) as hour,
     COUNT(*) as audit_count
   FROM interaction_audit_log
   WHERE created_at > NOW() - INTERVAL '7 days'
   GROUP BY DATE_TRUNC('hour', created_at)
   ORDER BY hour DESC;
   ```
   Look for hours with 0 or very low counts.

3. **Check S3 Object Lock:**
   ```bash
   aws s3api get-object-lock-configuration \
     --bucket genai-governance-audit-logs \
     --key 2026-03-15/audit-log.json

   # Should show COMPLIANCE or GOVERNANCE mode
   ```

4. **Root cause:**
   - Is audit logging service running? (Check pod status)
   - Is S3 write failing? (Check error logs)
   - Is database running? (Check RDS)
   - Was data deleted? (Check AWS CloudTrail for DeleteObject operations)

### Remediation (First 2 hours)

1. **Restore audit logging:**
   - If service down: Restart `audit-log-processor` pod
   - If S3 write failing: Check credentials, retry
   - If database down: Restore from backup

2. **Verify audit integrity:**
   - Sample check: Pick random [DATE], verify all interactions for that date have audit records
   - S3 Object Lock: Confirm all audit objects have lock enabled

3. **Attempt recovery:**
   - Check PostgreSQL WAL for lost entries
   - If found, replay to recover

4. **Regulatory assessment:**
   - Scope: How many hours? How many interactions?
   - Can it be recovered? Or permanently lost?
   - Notification required? (Audit trail integrity is regulatory requirement)

### Communication Template

**Internal (Slack #incident-ops):**
```
🚨 P1: Audit Trail Loss/Corruption — Gap from [TIME] to [TIME]

Scope:
- Hours lost: [N]
- Estimated interactions: [N]
- Recovery status: [Recovering / Recovered / Unrecoverable]

Root cause: [Service crash / S3 write failure / Database issue / Manual deletion]

Actions:
- [x] Logging resumed
- [ ] WAL recovery attempted
- [ ] S3 Object Lock verified
- [ ] Regulatory notification assessment

Regulatory impact: [ASSESS NOW]
```

