# GenAI Governance Platform — Deployment Guide

## Table of Contents

1. [Production Topology](#production-topology)
2. [Deployment Steps](#deployment-steps)
3. [Day-to-Day Compliance Officer Workflow](#day-to-day-compliance-officer-workflow)
4. [Monitoring Setup](#monitoring-setup)
5. [Incident Response](#incident-response)

---

## Production Topology

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    AWS Region (us-east-1)               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Application Tier (Compute)                      │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  Load Balancer (ALB)                             │  │
│  │  ├─ genai-governance.creditunion.local:443      │  │
│  │  └─ Health check: /health                        │  │
│  └──────────────────────────────────────────────────┘  │
│           │                                            │
│  ┌────────▼──────────────────────────────────────────┐ │
│  │  ECS Fargate (Containerized Python App)           │ │
│  │  ├─ Task definition: genai-governance:1.0        │ │
│  │  ├─ Replica count: 2-5 (auto-scaling)            │ │
│  │  ├─ CPU: 512 (0.5 vCPU)                          │ │
│  │  └─ Memory: 1024 MB                              │ │
│  │      │ Runs:                                      │ │
│  │      ├─ FastAPI app (port 8000)                 │ │
│  │      ├─ PromptRegistry (in-memory + RDS sync)   │ │
│  │      ├─ GuardrailEngine (deterministic)         │ │
│  │      ├─ ComplianceLogger (RDS + S3 writer)      │ │
│  │      └─ ModelEvaluator (weekly batch via Lambda) │ │
│  └────────┬───────────────────────────────────────────┘ │
│           │                                            │
├───────────┼────────────────────────────────────────────┤
│           │  Data Tier                               │
│  ┌────────▼────────────────────────────────────────┐ │
│  │  RDS PostgreSQL (genai-governance-db)           │ │
│  │  ├─ Multi-AZ (high availability)                │ │
│  │  ├─ Encryption: KMS customer-managed key        │ │
│  │  └─ Tables:                                      │ │
│  │     ├─ prompt_versions (immutable after INSERT) │ │
│  │     ├─ interaction_logs (append-only)           │ │
│  │     ├─ compliance_events                        │ │
│  │     └─ model_evaluations                        │ │
│  └────────┬───────────────────────────────────────────┘ │
│           │                                            │
│  ┌────────▼────────────────────────────────────────┐ │
│  │  S3 Bucket (genai-governance-logs)              │ │
│  │  ├─ Object Lock: Compliance mode (WORM)        │ │
│  │  ├─ Retention: 7 years (custom policy)         │ │
│  │  ├─ Encryption: S3-managed + KMS optional      │ │
│  │  ├─ Versioning: Enabled (immutability backup)  │ │
│  │  └─ Folder structure:                           │ │
│  │     ├─ /2026-01/interactions/INT-*.json        │ │
│  │     ├─ /2026-01/events/EVT-*.json              │ │
│  │     └─ /2026-01/reports/AUDIT-*.txt            │ │
│  └──────────────────────────────────────────────────┘ │
│           │                                            │
├───────────┼────────────────────────────────────────────┤
│           │  External Services                        │
│  ┌────────▼────────────────────────────────────────┐ │
│  │  AWS Bedrock (Model Access)                     │ │
│  │  ├─ Model: claude-3-sonnet-20240229            │ │
│  │  ├─ IAM auth (no API keys in application)      │ │
│  │  └─ Rate limit: 100 requests/minute (soft)     │ │
│  └──────────────────────────────────────────────────┘ │
│           │                                            │
│  ┌────────▼────────────────────────────────────────┐ │
│  │  Genesys Cloud (Call Center Integration)        │ │
│  │  ├─ API: /agents/{id}/screen-pop               │ │
│  │  ├─ Auth: OAuth 2.0                            │ │
│  │  └─ Data: AI draft response + guardrail flag   │ │
│  └──────────────────────────────────────────────────┘ │
│           │                                            │
│  ┌────────▼────────────────────────────────────────┐ │
│  │  Symitar (Core Banking)                         │ │
│  │  ├─ API: /accounts/{id}                        │ │
│  │  ├─ Auth: SOAP + mutual TLS                    │ │
│  │  └─ Data: Member account context                │ │
│  └──────────────────────────────────────────────────┘ │
│                                                     │
├─────────────────────────────────────────────────────┤
│  Monitoring & Alerting Tier                         │
│  ├─ CloudWatch Dashboards                          │
│  ├─ CloudWatch Alarms → SNS → Email + PagerDuty    │
│  ├─ X-Ray (distributed tracing)                    │
│  ├─ CloudTrail (audit logging)                     │
│  └─ VPC Flow Logs                                  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Network Diagram

```
Internet Gateway
  │
ALB (genai-governance.creditunion.local)
  │
  └── Public Subnet (NAT Gateway)
       │
       └── Private Subnet (ECS Fargate)
            │
            ├─→ RDS Proxy → RDS PostgreSQL (private subnet)
            ├─→ S3 Gateway Endpoint → S3 (HTTPS)
            └─→ Bedrock Endpoint → AWS Bedrock
```

### Auto-Scaling Configuration

```
ECS Auto-scaling Policy
├─ Metric: CPU Utilization
│  ├─ Target: 70%
│  ├─ Scale Up: If avg CPU >85% for 2 minutes
│  ├─ Scale Down: If avg CPU <30% for 10 minutes
│  └─ Min replicas: 2 (high availability)
│     Max replicas: 5 (cost control)
│
└─ Metric: Request Count
   ├─ Target: 1000 requests/replica/minute
   └─ Adjust task count accordingly
```

---

## Deployment Steps

### Prerequisites

**AWS Account Requirements:**
- VPC configured with public + private subnets
- NAT Gateway for private subnet internet access
- RDS subnet group created
- S3 bucket creation permissions
- Bedrock model access enabled (claude-3-sonnet)

**Tools Required:**
```bash
# On deployment machine
aws-cli v2.x
docker
kubectl (if using EKS instead of ECS)
python 3.11+
terraform (for infrastructure as code)
```

**Credentials:**
```bash
# AWS credentials (via IAM role recommended)
export AWS_PROFILE=creditunion-prod

# Genesys OAuth
GENESYS_CLIENT_ID=xxxxx
GENESYS_CLIENT_SECRET=xxxxx

# Symitar SOAP credentials
SYMITAR_USERNAME=xxxxx
SYMITAR_PASSWORD=xxxxx
```

### Step 1: Prepare Application Code

```bash
# Clone repository
git clone https://github.com/creditunion/genai-governance.git
cd genai-governance

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Check code quality
black src/ --check
flake8 src/

# Build container image
docker build -t genai-governance:1.0 \
  --build-arg PYTHON_VERSION=3.11 \
  .

# Tag for ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.us-east-1.amazonaws.com

docker tag genai-governance:1.0 \
  123456789.dkr.ecr.us-east-1.amazonaws.com/genai-governance:1.0

# Push to ECR
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/genai-governance:1.0
```

### Step 2: Create AWS Infrastructure

```bash
# Using Terraform (provided in terraform/ directory)
cd terraform/

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -out=tfplan

# Apply (creates RDS, S3, ECS, monitoring)
terraform apply tfplan

# Outputs:
# - RDS endpoint: genai-governance-db.xxxxxx.us-east-1.rds.amazonaws.com
# - S3 bucket: genai-governance-logs-123456
# - ALB DNS: genai-governance-alb-123456.us-east-1.elb.amazonaws.com
# - ECS cluster: genai-governance-prod
```

### Step 3: Initialize RDS Database

```bash
# Connect to RDS (via bastion host or RDS Proxy)
psql -h genai-governance-db.xxxxxx.us-east-1.rds.amazonaws.com \
     -U admin \
     -d genai_governance

# Run schema initialization
\i db/schema.sql

# Verify tables created
\dt
# Should show:
# - prompt_templates
# - prompt_versions
# - interaction_logs
# - compliance_events
# - model_evaluations

# Create indexes (performance)
\i db/indexes.sql

# Set up automated backups
BACKUP DATABASE genai_governance
  TO DISK = '/backups/'
  WITH INIT, COMPRESSION
```

### Step 4: Deploy ECS Service

```bash
# Register ECS task definition
aws ecs register-task-definition \
  --cli-input-json file://ecs/task-definition.json \
  --region us-east-1

# Create ECS service
aws ecs create-service \
  --cluster genai-governance-prod \
  --service-name genai-governance \
  --task-definition genai-governance:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=genai-governance,containerPort=8000"

# Verify service launched
aws ecs describe-services \
  --cluster genai-governance-prod \
  --services genai-governance \
  --region us-east-1
# Status should be: ACTIVE, runningCount: 2
```

### Step 5: Configure Monitoring & Alerting

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name genai-governance \
  --dashboard-body file://monitoring/dashboard.json

# Create alarms
aws cloudwatch put-metric-alarm \
  --alarm-name genai-pii-detection-high \
  --alarm-description "PII detection rate >2%" \
  --metric-name PIIBlockRate \
  --namespace GenAIGovernance \
  --statistic Average \
  --period 3600 \
  --threshold 2.0 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789:genai-alerts

# Similar for other critical metrics
```

### Step 6: Integration Testing

```bash
# Test Genesys Cloud integration
curl -X POST https://genai-governance.creditunion.local/test/genesys \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -d '{"member_id":"12345","question":"What is my balance?"}'
# Expected: 200 OK with draft response + guardrail flags

# Test Symitar integration
curl -X GET https://genai-governance.creditunion.local/test/symitar \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -d '{"member_id":"12345"}'
# Expected: 200 OK with member account context

# Test guardrails with synthetic data
curl -X POST https://genai-governance.creditunion.local/test/guardrails \
  -H "Content-Type: application/json" \
  -d '{
    "output": "Your SSN is 123-45-6789",
    "input_context": "Member balance inquiry"
  }'
# Expected: 200 OK with block reason: PII detected

# Test compliance logger
curl -X GET https://genai-governance.creditunion.local/api/compliance/interactions \
  -H "Authorization: Bearer $COMPLIANCE_TOKEN" \
  -d '{"date_start":"2026-03-01","date_end":"2026-03-31","limit":10}'
# Expected: 200 OK with recent interaction logs
```

### Step 7: Compliance Officer Training (1-2 hours)

**Topics:**
1. Dashboard navigation and interpretation
2. How to query interaction logs
3. How to interpret guardrail reports
4. Model evaluation cycles and what scores mean
5. Compliance event investigation procedure
6. Emergency contact procedures
7. How to prepare for NCUA examination

**Hands-On Training:**
```bash
# Show dashboard
open https://genai-governance.creditunion.local

# Query interactions
governance_cli query interactions \
  --date-start 2026-03-01 \
  --date-end 2026-03-31 \
  --use-case customer_service \
  --guardrail-action block \
  --limit 20

# Generate audit report
governance_cli report \
  --period monthly \
  --month March \
  --format pdf

# View model card
governance_cli show model-card \
  --model-id claude-3-sonnet-cust-svc
```

### Step 8: Go-Live

**Pre-Go-Live Checklist:**

```
Readiness Checklist (Day Before Go-Live)
├─ [ ] All tests passing (100% pass rate)
├─ [ ] RDS backup verified (restore test successful)
├─ [ ] S3 Object Lock enabled and tested
├─ [ ] Monitoring dashboards configured and visible
├─ [ ] Alarms configured for all critical metrics
├─ [ ] Genesys integration tested with sample data
├─ [ ] Symitar integration tested with sample data
├─ [ ] Guardrails tested with synthetic malicious inputs
├─ [ ] Compliance officer training completed
├─ [ ] Incident response procedures reviewed
├─ [ ] On-call rotation established
├─ [ ] Communication plan sent to leadership
└─ [ ] Legal review of governance controls completed
```

**Go-Live Process:**

```
T-00:00 (Start of go-live window: 7am)
├─ Compliance officer online
├─ On-call engineer online
├─ Genesys call center staff briefed
└─ All monitoring dashboards open

T+01:00 (1 hour in)
├─ Light member service requests flowing
├─ Check: Interaction log rate nominal
├─ Check: Guardrail latency <200ms
├─ Check: No errors in logs
└─ If issues: Escalate to incident response

T+04:00 (4 hours in)
├─ Normal call volume
├─ Check: 50-100 interactions processed
├─ Check: Block rate 2-3% (expected)
├─ Check: Zero false negatives observed
└─ Status: HEALTHY

T+08:00 (End of day)
├─ ~500 interactions processed
├─ Generate daily compliance report
├─ Compliance officer reviews results
├─ Sign-off email sent to CIO
└─ Status: GO-LIVE SUCCESSFUL
```

---

## Day-to-Day Compliance Officer Workflow

### Morning Standup (9am, 10 minutes)

**Dashboard Review:**
```
1. Open https://genai-governance.creditunion.local
2. Check Overview tab:
   - This week's interactions: Should be growing
   - Block rate: Should be 2-3%
   - PII caught: Should be >0 (vigilant detection)
   - Unresolved events: Should be 0 (good response time)
3. Check Model Health tab:
   - Both models: Should show "approved"
   - Next validation dates: Should be future dates
   - If any model shows "conditional": Investigate why
4. If any red indicators: Escalate immediately
```

**Morning Checklist:**
```
☐ Dashboard: No critical alerts (red indicators)
☐ Overnight: Any critical incidents? (check email/PagerDuty)
☐ Open events: Still same as yesterday? (if count increased, investigate)
☐ Model scores: Any drift since last check? (scores should be stable ±1-2%)
```

### Weekly Tasks

**Monday Morning: Evaluation Run Review (30 minutes)**

```
1. Wait for automated evaluation run to complete (2am-2:30am, Mon)
2. 8am: Check SNS notification (should be "evaluation complete" if all passed)
3. If SNS says FAILED:
   - Login to AWS console
   - View CloudWatch logs: /ecs/genai-governance
   - Look for error in ModelEvaluator
   - Call engineering lead to investigate
4. If SNS says PASSED:
   - Open governance_cli to view results:
     governance_cli show eval-run --model=claude-3-sonnet-cust-svc
   - Review dimension scores:
     - Accuracy, Groundedness, Safety, Compliance: Should be ≥95%
     - Consistency, Relevance: Should be ≥85%
   - Review bias results:
     - Response length disparity: Should be <3%
     - Formality disparity: Should be <3%
   - If all PASS: Status GREEN, no action needed
   - If any CONDITIONAL: Make a note, discuss in weekly meeting
   - If any FAIL: Escalate immediately to MRM analyst
```

**Wednesday: Compliance Event Triage (1 hour)**

```
1. Query all unresolved events since last Wednesday:
   governance_cli query events \
     --start-date 7-days-ago \
     --unresolved-only \
     --limit 100
2. For each event:
   a. Read description + timestamp + severity
   b. Investigate root cause:
      - Query the corresponding interaction
      - Check guardrail results
      - Verify if true positive or false alarm
   c. Take action:
      - If false alarm: Mark as resolved, document finding
      - If operator error: Resolve, note training opportunity
      - If system issue: Create ticket for engineering
      - If compliance concern: Escalate to MRM
3. Update event status:
   governance_cli resolve-event \
     --event-id EVT-XXXXX \
     --resolution "PII false positive: SSN was in input context" \
     --resolved-by "Maria Chen"
4. Report summary to director
```

**Friday: Monthly Report Prep (2 hours)**

```
1. End-of-month audit report (automated):
   governance_cli report \
     --period monthly \
     --month March \
     --format pdf \
     --output audit_report_march_2026.pdf
2. Review key metrics:
   - Total interactions: Should show month-over-month growth
   - Block rate: Should be stable (±0.5%)
   - PII detections: Should be consistent
   - Compliance events: Should be decreasing over time (more refinement)
3. Create summary email for board:
   - Headline metrics (total interactions, block rate, PII caught)
   - Notable events (any critical issues?)
   - Model status (all validated, next validation dates)
   - Outlook for next month
4. File report in shared drive (audit trail)
```

### Monthly Tasks

**First Friday: Compliance Meeting (1.5 hours)**

**Attendees:**
- Compliance Officer (Maria Chen)
- MRM Analyst (Senior analyst from Risk Management)
- Engineering Lead (Digital Transformation Team)
- Call Center Supervisor (Operations perspective)

**Agenda:**
```
1. Performance metrics (15 minutes)
   - Review audit report
   - Block rates per guardrail check
   - PII detection trend
   - Human review statistics
2. Model evaluation results (20 minutes)
   - Latest eval run scores
   - Any regressions or improvements?
   - Bias test results
   - If any conditional approvals: discuss remediation
3. Compliance events deep dive (20 minutes)
   - Major events from past month
   - Root cause analysis
   - Remediation taken
   - Systemic issues vs isolated incidents
4. Guardrail effectiveness (15 minutes)
   - Are guardrails catching what they should?
   - False positive rate acceptable?
   - Any new patterns to add?
   - Pattern library review/update
5. Roadmap for next month (10 minutes)
   - Any planned prompt changes?
   - New use cases in pipeline?
   - Evaluation improvements?
6. Action items (5 minutes)
```

**Output:**
- Meeting notes filed
- Action items tracked in project management system
- Any required guardrail pattern updates submitted to engineering

### Quarterly Tasks

**End of Quarter: Board Update (1 hour presentation + Q&A)**

**Attendees:**
- Board compliance committee
- CIO
- Chief Risk Officer
- CFO (for financial impact discussion)
- Compliance Officer

**Presentation:**
```
Slide 1: GenAI Governance Governance Platform - Q1 Performance Review

Slide 2: Key Metrics
- 43,800 interactions processed in Q1
- 97.4% delivered, 2.6% blocked by guardrails
- 191 PII exposures detected and prevented
- 14 compliance events, all resolved
- 0 findings in areas covered by governance

Slide 3: Guardrail Performance
- PII detection: 0.4% block rate (vigilant)
- Hallucination: 1.23% block rate (catches fabrications)
- Bias screen: 0.03% block rate (low false positive)
- Compliance filter: 0.11% block rate
- Confidence: 0.14% block rate
- Overall block rate: 2.6% (within target 2-5%)

Slide 4: Model Validation
- Member Service Copilot: 91.2% accuracy, 96.4% groundedness, APPROVED
- Loan Summarizer: 93.5% accuracy, 97.8% groundedness, APPROVED
- Bias testing: Both models <3% demographic disparity
- Next validation: May 2026 (quarterly schedule)

Slide 5: Compliance Readiness
- NCUA exam readiness: COMPLETE
- Prompt version history: 8 versions, full approval chain
- Model documentation: SR 11-7 compliant model cards
- Audit trail: 43,800 interactions fully logged, queryable
- Can answer all examiner questions in <1 hour

Slide 6: Business Impact
- Member service AHT: 7.2 → 5.8 minutes (19.4% improvement)
- Agent satisfaction: "Saves time without quality degradation"
- Loan document review: 30% time reduction
- Member experience: No complaints related to AI

Slide 7: Risk Assessment
- Current risk posture: LOW
- Controls are working effectively
- Monitoring is continuous
- Remediation response: <4 hours on average

Slide 8: Next Steps
- Continue weekly monitoring
- Expand to 1-2 additional use cases in Q2
- Deeper bias testing (demographic data collection planned)
- Annual vendor audit of AWS Bedrock service
```

**Questions Expected:**
- "What if an AI-generated response causes a member complaint?"
  - Answer: "We can produce the exact interaction, guardrail results, and human review outcome within 5 minutes"
- "How do we know the guardrails are working?"
  - Answer: "We validate guardrails through test cases and measure false positive/negative rates monthly"
- "What happens if the AI model starts behaving badly?"
  - Answer: "Weekly evaluations with drift detection would catch >5% score drop. We can roll back or adjust guardrails within 4 hours"
- "Is this expensive?"
  - Answer: "Total operational cost: $8k/month (RDS $2k + S3 $1k + Bedrock $3k + ECS $2k). ROI from AHT reduction: $200k/year"

### Incident Response (On-Call Rotation)

**On-Call Schedule:**
```
Primary (5pm-9am overnight + weekends):
- Week 1-2: Maria Chen (Compliance Officer)
- Week 3-4: Joe Park (Senior MRM Analyst)

Secondary (backup):
- Always: Alex Kim (Engineering Lead)

PagerDuty escalation:
- SEV1 (Critical): 5 min page + call
- SEV2 (High): 15 min page + call
- SEV3 (Medium): Email notification
```

**Incident Types & Responses:**

**SEV1: PII Exposure in Production**

```
Trigger: SNS alert "PII_EXPOSURE_DETECTED"

Immediate Actions (0-15 min):
1. On-call compliance officer receives PagerDuty alert
2. Immediately check dashboard: How many interactions affected?
3. Is guardrail blocking preventing delivery to member? (YES: good)
4. Or did PII reach a member? (Escalate to CRITICAL)
5. Call engineering lead
6. Query affected interactions:
   governance_cli query interactions \
     --start-date 1-hour-ago \
     --pii-exposed true \
     --limit 100

Investigation (15-60 min):
1. Which PII type? (SSN, account number, phone, etc.)
2. Why wasn't guardrail catching it?
3. Which guardrail pattern failed?
4. Is this a known pattern or new variant?

Remediation (60-120 min):
1. If new pattern:
   a. Add regex pattern to PIIDetector
   b. Test pattern on test cases
   c. Deploy hotfix to production
   d. Retro-scan last 24h for similar cases
2. If known pattern failed:
   a. Debug why detection failed
   b. Check guardrail latency (was it rushed?)
   c. Update pattern for edge case
   d. Deploy fix
3. Post-incident:
   a. Write incident report
   b. File ticket for pattern library review
   c. Schedule pattern review meeting

Communication:
- Immediate: Alert CEO + CRO (if member contacted)
- 1 hour: Incident report to legal
- 4 hours: Root cause analysis to MRM
- Next day: Post-mortem with engineering
```

**SEV2: Model Hallucination High Rate**

```
Trigger: SNS alert "HALLUCINATION_BLOCK_RATE_HIGH" (>5%)

Immediate Actions (0-30 min):
1. Check dashboard: Is block rate actually high or sensor glitch?
2. Query recent hallucination blocks:
   governance_cli query interactions \
     --start-date 4-hours-ago \
     --check-type hallucination \
     --result block \
     --limit 50
3. Pattern analysis: What types of hallucinations?
   - Dollar amounts? Dates? Percentages?
   - Consistent pattern or random?
4. Call engineering lead

Investigation (30-120 min):
1. Root cause hypothesis:
   - Did prompt change? (check version history)
   - Did model update? (check Bedrock version)
   - Did input context change? (check call center process)
   - New type of member question triggering hallucination?
2. Impact assessment:
   - Are false positive blocks (guardrail too aggressive)?
   - Or true hallucinations (model behaving badly)?
3. Quick fix (if false positives):
   a. Adjust hallucination detector thresholds
   b. Test on recent interactions
   c. Deploy immediately
4. Long-term fix (if model issue):
   a. Schedule urgent eval run
   b. If model scores down: Contact AWS Bedrock support
   c. Prepare for model rollback if needed

Communication:
- Immediate: Alert engineering + MRM analyst
- 30 min: Update to compliance officer
- 2 hours: Initial assessment to CIO
```

**SEV3: Compliance Event Backlog**

```
Trigger: SNS alert "UNRESOLVED_EVENTS_HIGH" (>10 or >7 days old)

Action (within business hours):
1. Triage unresolved events:
   governance_cli query events \
     --unresolved-only \
     --order-by timestamp asc
2. Age analysis:
   - <1 day old: Quick action, should be resolved
   - 1-7 days old: Investigate cause of delay
   - >7 days old: Escalate to MRM lead
3. Root cause analysis:
   - Are they false positives? (low risk, quick resolve)
   - Are they legitimate issues? (medium risk, needs investigation)
   - Are they system bugs? (high risk, needs engineering)
4. Create action plan per event
5. Update event status when actions taken
```

---

## Monitoring Setup

### CloudWatch Dashboard Configuration

```
Dashboard: genai-governance (https://console.aws.amazon.com/cloudwatch/...)

Metrics Section 1: Interaction Volume
├─ Interactions per minute (line chart, 1-day view)
├─ Interaction trend (7-day view)
└─ Forecast: Expected interactions next 7 days

Metrics Section 2: Guardrail Performance
├─ Block rate % (target: 2-5%)
├─ PII detection count (target: <1% of volume)
├─ Hallucination blocks (target: <2% of volume)
├─ Avg guardrail latency (target: <200ms)
└─ Failed guardrail checks (target: 0)

Metrics Section 3: Model Health
├─ Model evaluation status (shows APPROVED/CONDITIONAL/REMEDIATION)
├─ Latest eval scores (heatmap by dimension)
├─ Model latency (target: <2 seconds)
└─ Drift detection (if score down >5%: RED alert)

Metrics Section 4: Compliance
├─ Compliance events (count, severity breakdown)
├─ Event resolution time (avg hours to resolve)
├─ Unresolved events (target: 0)
└─ Human review backlog (count pending)

Metrics Section 5: Infrastructure
├─ ECS CPU utilization (target: 50-70%)
├─ ECS memory utilization (target: 50-70%)
├─ RDS connections (target: <50% of max)
├─ S3 API latency (target: <100ms)
└─ Bedrock API latency (target: <2 seconds)

Metrics Section 6: Security
├─ Unauthorized API calls (target: 0)
├─ S3 object access anomalies (target: 0)
├─ Database connection failures (target: 0)
└─ CloudTrail events (audit trail completeness)
```

### Alert Configuration

```
Alert: pii-detection-high
├─ Metric: PII block rate (%)
├─ Threshold: >2.0%
├─ Statistic: Average
├─ Period: 1 hour
├─ Evaluation: Must breach 1 time
├─ Action: SNS → Compliance officer email + PagerDuty
└─ Description: "PII detection rate unusually high, investigate pattern"

Alert: hallucination-blocks-high
├─ Metric: Hallucination block count
├─ Threshold: >5% of interactions
├─ Statistic: Sum
├─ Period: 4 hours
├─ Evaluation: Must breach 2 times
├─ Action: SNS → Engineering + Compliance
└─ Description: "Hallucination blocks elevated, may indicate model drift"

Alert: model-evaluation-failed
├─ Metric: Evaluation run status
├─ Threshold: Status = FAILED or REMEDIATION
├─ Statistic: N/A (discrete metric)
├─ Period: N/A (triggered immediately)
├─ Evaluation: Any breach
├─ Action: SNS → MRM analyst + Compliance officer
└─ Description: "Model evaluation failed, immediate review required"

Alert: unresolved-events-aging
├─ Metric: Unresolved event age (hours)
├─ Threshold: >168 hours (7 days)
├─ Statistic: Maximum
├─ Period: 24 hours
├─ Evaluation: Once per day
├─ Action: Email → Compliance officer
└─ Description: "Event aging beyond 7 days, follow-up needed"

Alert: guardrail-latency-high
├─ Metric: Guardrail processing time (ms)
├─ Threshold: >300ms
├─ Statistic: Average
├─ Period: 1 hour
├─ Evaluation: Must breach 2 times
├─ Action: SNS → Engineering (low priority, not critical)
└─ Description: "Guardrail latency elevated, investigate regex performance"

Alert: database-connection-pool-high
├─ Metric: RDS connections
├─ Threshold: >40 (of 50 available)
├─ Statistic: Average
├─ Period: 5 minutes
├─ Evaluation: Must breach 3 times
├─ Action: SNS → Engineering + Ops
└─ Description: "Database connections near limit, may need connection pooling review"

Alert: bedrock-rate-limit-exceeded
├─ Metric: Bedrock throttling count
├─ Threshold: >0
├─ Statistic: Sum
├─ Period: 1 hour
├─ Evaluation: Once breach
├─ Action: SNS → Engineering
└─ Description: "Bedrock rate limit hit, may need quota increase or traffic backpressure"
```

### Log Analysis (CloudWatch Logs Insights)

**Query: Find all PII blocks in last 24 hours**
```sql
fields @timestamp, interaction_id, pii_type, output_snippet
| filter guardrail_action = "block" and check_name = "pii_detection"
| stats count() as pii_block_count by pii_type
| sort pii_block_count desc
```

**Query: Average latency by use case**
```sql
fields @timestamp, use_case, total_latency_ms
| stats avg(total_latency_ms) as avg_latency_ms, max(total_latency_ms) as max_latency_ms by use_case
| sort avg_latency_ms desc
```

**Query: Compliance events from last 7 days**
```sql
fields @timestamp, event_id, event_type, severity, status
| filter event_type in ["guardrail_block", "pii_in_output", "compliance_violation"]
| stats count() as event_count, earliest(@timestamp) as first_event by event_type, severity
```

---

## Incident Response Procedures

### Incident Severity Definitions

| Severity | Condition | Response Time | Team |
|----------|-----------|---|---|
| **SEV1 - CRITICAL** | PII exposed to member OR model completely unusable OR compliance violation in progress | <15 min | Compliance officer + Engineering + MRM |
| **SEV2 - HIGH** | Guardrail block rate anomalies OR model evaluation failed OR unplanned downtime | <30 min | Engineering + Compliance officer |
| **SEV3 - MEDIUM** | Latency elevated OR event backlog OR pattern library needs update | <2 hours | Engineering (compliance officer informed) |
| **SEV4 - LOW** | Dashboard availability issue OR non-critical monitoring gap | <1 business day | Ops team |

### Incident Command Structure

**For SEV1 (Critical Incidents):**

```
Incident Commander: Engineering Lead (Alex Kim)
├─ Declares incident, sets duration/scope expectations
├─ Orders a standup conference bridge (PagerDuty)
└─ Designates communications lead

Communications Lead: Compliance Officer (Maria Chen)
├─ Updates status every 15 minutes
├─ Prepares external communications (CEO/Board if needed)
└─ Documents timeline for post-mortem

Technical Lead: Senior Engineer
├─ Investigates root cause
├─ Coordinates engineering response
├─ Recommends rollback vs fix forward

Compliance Lead: MRM Analyst
├─ Assesses regulatory implications
├─ Determines if member notification needed
├─ Prepares documentation for examiners
```

### Post-Incident Review (24 hours after resolution)

**Attendees:**
- Everyone involved in incident response
- Manager of incident commander
- Compliance officer

**Meeting Agenda:**
```
1. Timeline: What happened and when
2. Root cause: Why did it happen?
3. Impact: How many members affected? What data exposed?
4. Detection: How long until we noticed?
5. Resolution: How did we fix it?
6. Prevention: How do we prevent recurrence?
7. Follow-up: What tickets need to be filed?
8. Communication: How do we inform the board/examiners?
```

**Output:**
- Incident report (filed in audit trail)
- Root cause analysis
- Action items for prevention
- Update to playbooks if needed

---

## Compliance Officer Playbooks

### Playbook: Responding to NCUA Examination Request

**Trigger:** Email from NCUA examiner requesting GenAI documentation

**Timeline:**
- T+0: Request received
- T+1 hour: Verify it's legitimate (contact NCUA supervisory office)
- T+4 hours: Gather documentation, compile report
- T+1 day: Provide to examiner

**Documentation Checklist:**
```
☐ Model cards (SR 11-7 format)
  ├─ Model ID, provider, use case, risk tier
  ├─ Description, intended use, out-of-scope uses
  ├─ Validation test suites and results
  ├─ Bias testing results
  └─ Risk factors and mitigations

☐ Prompt registry documentation
  ├─ All prompt versions (active and deprecated)
  ├─ Version history with approval chain
  ├─ Change reasons documented
  └─ Approval sign-off from compliance officer

☐ Interaction logs (sample)
  ├─ 30-day sample of interactions
  ├─ Guardrail results for each
  ├─ Blocked outputs with reasoning
  └─ Human review outcomes

☐ Compliance event log
  ├─ All events from past 12 months
  ├─ Severity and resolution status
  ├─ Remediation actions taken
  └─ Effectiveness of controls

☐ Model evaluation history
  ├─ Monthly evaluation runs
  ├─ Dimension scores over time
  ├─ Any regressions detected
  └─ Validation outcome timeline

☐ Guardrail pattern library
  ├─ All PII detection patterns (with explanation)
  ├─ Hallucination detection approach
  ├─ Bias screening indicators
  ├─ Compliance violation patterns
  └─ Sensitivity/specificity analysis (false positive rate)

☐ Incident reports
  ├─ Any PII exposures (detection + prevention)
  ├─ Model behavior anomalies
  ├─ Guardrail failures
  └─ Root cause analyses and remediation

☐ Risk assessment
  ├─ Risk factors documented
  ├─ Mitigations in place
  ├─ Residual risk
  └─ Monitoring plan
```

**Command:**
```bash
# Generate complete examination documentation package
governance_cli export exam-documentation \
  --period 12-months \
  --include-models true \
  --include-prompts true \
  --include-interactions true \
  --include-events true \
  --redact-pii true \
  --format pdf \
  --output ncua-exam-documentation-2026.pdf
```

### Playbook: Adding a New Guardrail Pattern

**Scenario:** Compliance officer notices new PII pattern in blocks that doesn't match current patterns

**Steps:**

1. **Analyze** (15 min)
   - What is the pattern? (e.g., "account number format changed at Symitar")
   - How many instances? ("3 recent interactions")
   - Did guardrails catch it? ("No, false negative")
   - How risky is this data? ("High, could allow fraud")

2. **Design** (15 min)
   - Create regex pattern
   - Test on historical data
   - Measure sensitivity (catch rate) and specificity (false positive rate)
   - Example:
     ```python
     # New account format: ACH prefix + 10 digits
     "account_ach_format": {
       "pattern": r'\bACH\d{10}\b',
       "description": "ACH account identifier",
       "severity": "block",
     }
     ```

3. **Test** (30 min)
   - Run pattern on test cases
   - Verify false negative rate (should be 0)
   - Verify false positive rate (should be <0.1%)
   - Document performance metrics

4. **Deploy** (15 min)
   - Update PIIDetector.PATTERNS in production code
   - Push to GitHub
   - File PR for code review
   - After approval, merge to main
   - Trigger new deployment to ECS (or wait for next scheduled deployment)

5. **Validate** (24 hours)
   - Monitor block rate for new pattern
   - Should see blocks on similar patterns in production
   - If no blocks appear, verify pattern is actually firing
   - Check false positive rate (should be low)

6. **Document** (30 min)
   - Update pattern library documentation
   - Add explanation of why pattern was added
   - Update guardrail guidelines
   - File in audit trail

---

