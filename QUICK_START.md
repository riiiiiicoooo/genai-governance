# Quick Start: Modern Tooling Setup

## Overview

The GenAI Governance Platform now includes production-grade modern infrastructure integrating LangSmith, n8n, Trigger.dev, React Email, Supabase, and Vercel.

## File Locations

```
genai-governance/
├── .cursorrules                          # Cursor IDE context
├── .replit                               # Replit configuration
├── replit.nix                            # Nix environment
├── .env.example                          # Environment template
├── vercel.json                           # Vercel deployment config
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql        # Database schema (11 tables + RLS)
├── langsmith/
│   ├── governance_tracing.py             # LangSmith integration (@traceable)
│   └── guardrail_evals.py                # 30+ test cases
├── n8n/
│   ├── compliance_event_router.json      # Webhook → PagerDuty/Slack/Email
│   └── daily_compliance_digest.json      # Daily 8 AM digest
├── trigger-jobs/
│   └── model_evaluation.ts               # Monthly evaluation (Trigger.dev)
├── emails/
│   ├── compliance_alert.tsx              # React Email: critical alerts
│   └── daily_digest.tsx                  # React Email: daily digest
└── README.md                             # Updated with modern stack section
```

## Setup Steps

### 1. Environment Configuration

```bash
# Copy template to local
cp .env.example .env.local

# Fill in:
SUPABASE_URL=https://[YOUR_PROJECT].supabase.co
SUPABASE_ANON_KEY=your_key
SUPABASE_SERVICE_ROLE_KEY=your_key

LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=genai-governance

AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_key

PAGERDUTY_API_KEY=your_key
SLACK_BOT_TOKEN=your_token
RESEND_API_KEY=your_key

COMPLIANCE_ALERT_EMAIL=compliance@yourorg.com
COMPLIANCE_DIGEST_EMAIL=compliance@yourorg.com

TRIGGER_API_KEY=your_key
N8N_API_KEY=your_key
```

### 2. Database Setup (Supabase)

```bash
# Create new Supabase project
# In Supabase dashboard:
# 1. Create new project
# 2. Go to SQL Editor
# 3. Paste contents of supabase/migrations/001_initial_schema.sql
# 4. Run all SQL
```

This creates:
- 11 tables (prompts, guardrails, interactions, compliance, evaluations, audit, metrics)
- Row-level security policies
- Triggers for automation
- Views for examiner reports
- Indexes for performance

### 3. LangSmith Integration

```python
# Import and use
from langsmith.governance_tracing import (
    trace_governance_pipeline,
    trace_llm_call,
    trace_guardrail_evaluation,
    cost_tracker
)

# Your code automatically instrumented with traces
@traceable(name="my_operation")
def my_governance_operation():
    pass
```

**Test Cases:**
```python
from langsmith.guardrail_evals import evaluation_dataset

# Get test cases by type
pii_cases = evaluation_dataset.get_test_cases_by_type("pii_detection")

# Get by difficulty
hard_cases = evaluation_dataset.get_test_cases_by_difficulty("hard")

# Export for evaluation
json_data = evaluation_dataset.export_to_json()
```

### 4. n8n Workflows

```bash
# Setup n8n instance
# Install n8n globally or use Docker

# In n8n UI:
# 1. Create new workflow
# 2. Import from JSON:
#    - n8n/compliance_event_router.json
#    - n8n/daily_compliance_digest.json
# 3. Configure credentials:
#    - Supabase (service role key)
#    - PagerDuty API
#    - Slack webhook
#    - Resend API

# Configure Supabase webhook:
# 1. In Supabase: Database > Webhooks
# 2. Create webhook on compliance_events table
# 3. INSERT event
# 4. URL: https://your-n8n.com/webhook/compliance-events
```

**Event Router Flow:**
```
Supabase: compliance_events INSERT
    ↓
n8n webhook trigger
    ↓
Check severity:
    CRITICAL → PagerDuty + Slack + Email
    WARNING → Queue for digest
    INFO → Log only
```

**Daily Digest Flow:**
```
8 AM cron trigger
    ↓
Query yesterday's interactions
    ↓
Aggregate metrics + trends
    ↓
Generate HTML email
    ↓
Send via Resend + store in audit_reports
```

### 5. Trigger.dev Job

```bash
# Setup Trigger.dev
# npm install @trigger.dev/sdk@latest

# Configure in Trigger.dev dashboard:
# 1. Create project
# 2. Set API key in .env
# 3. Deploy trigger-jobs/model_evaluation.ts

# Job runs on: 1st of month at 2 AM
# Steps: Load tests → Evaluate models → Generate cards → Log results
```

### 6. React Email Templates

```tsx
// Critical alerts
import { COMPLIANCE_ALERT_EMAIL } from "emails/compliance_alert"

const html = COMPLIANCE_ALERT_EMAIL({
  eventType: "guardrail_block",
  severity: "critical",
  eventTitle: "PII Detected in Output",
  description: "Response contained SSN",
  guardrailTriggered: {
    checkType: "pii_detection",
    reason: "Social Security Number pattern detected",
    confidence: 0.99
  },
  recommendedAction: "Review guardrail sensitivity settings",
  dashboardUrl: "https://...",
  eventDetailsUrl: "https://..."
})

// Daily digest
import { DAILY_DIGEST_EMAIL } from "emails/daily_digest"

const html = DAILY_DIGEST_EMAIL({
  date: "2024-03-04",
  summary: {
    totalInteractions: 2154,
    deliveredCount: 2088,
    blockedCount: 41,
    warnedCount: 25,
    blockRate: 1.90,
    piiCaught: 5,
    avgLatencyMs: 145,
    totalCostUSD: 23.45
  },
  trends: {
    interactions: { direction: "up", changePercent: 12.3 },
    blockRate: { direction: "down", changeDiff: -0.5 }
  },
  unresolvedCritical: 0,
  unresolvedWarnings: 2,
  dashboardUrl: "https://..."
})
```

### 7. Vercel Deployment

```bash
# Push to GitHub
git add .
git commit -m "Add modern tooling infrastructure"
git push

# In Vercel:
# 1. Import project from GitHub
# 2. Set environment variables (from .env)
# 3. Deploy
# 4. Cron jobs automatically configured:
#    - Daily digest: 8 AM (0 8 * * *)
#    - Model eval: 1st at 2 AM (0 2 1 * *)
```

## Key Integrations

### LangSmith Observability
- Full pipeline tracing with @traceable decorators
- Custom evaluators: accuracy, PII detection, confidence calibration
- Cost tracking with real AWS Bedrock pricing
- Trace metadata includes guardrail decisions

### n8n Automation
- Event-driven: compliance events trigger routing
- Scheduled: daily 8 AM digest
- Multi-channel: PagerDuty, Slack, email, Supabase
- No-code/low-code: JSON workflows

### Trigger.dev Jobs
- Scheduled: monthly on 1st at 2 AM
- Long-running: 10-30 minutes for full evaluation
- Steps: test cases → model evaluation → model cards
- Error handling: partial completion with logging

### Supabase Database
- Immutable audit logs (append-only)
- RLS policies for role-based access
- Triggers for metric aggregation
- Views for examiner reports

### React Email
- Professional HTML templates
- Severity-based styling
- Trend indicators and alerts
- Mobile responsive

## Monitoring & Debugging

### LangSmith Dashboard
```
https://smith.langchain.com
```
- View all traces
- Analyze custom evaluator results
- Monitor cost per model
- Review guardrail accuracy

### n8n Dashboard
```
http://localhost:5678 (local)
https://your-n8n-instance.com (cloud)
```
- View workflow execution history
- Debug integration issues
- Edit workflows

### Supabase Dashboard
```
https://supabase.co/dashboard
```
- Query interaction logs
- View compliance events
- Check dashboard metrics
- Test RLS policies

### Trigger.dev Dashboard
```
https://trigger.dev/dashboard
```
- View job execution history
- Check run logs
- Monitor scheduled jobs

## Common Tasks

### Run Model Evaluation Manually

```bash
# Trigger.dev API
curl -X POST https://trigger.dev/api/runs \
  -H "Authorization: Bearer $TRIGGER_API_KEY" \
  -d '{"taskId":"model-evaluation-job"}'
```

### Query Compliance Events

```sql
SELECT * FROM compliance_events
WHERE severity = 'critical' AND resolved = false
ORDER BY created_at DESC;
```

### Check Block Rate

```sql
SELECT
  DATE(created_at) as date,
  COUNT(*) as total,
  SUM(CASE WHEN guardrail_decision = 'block' THEN 1 ELSE 0 END) as blocked,
  ROUND(100.0 * SUM(CASE WHEN guardrail_decision = 'block' THEN 1 ELSE 0 END) / COUNT(*), 2) as block_rate
FROM interaction_logs
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

### Test Guardrail Evaluators

```python
from langsmith.guardrail_evals import evaluation_dataset

dataset = evaluation_dataset
stats = dataset.get_statistics()
print(f"Total test cases: {stats['total_test_cases']}")
print(f"By type: {stats['by_type']}")
```

## Troubleshooting

### n8n Webhook Not Triggering
- Check Supabase webhook configuration
- Verify URL and event type
- Test with manual insert into compliance_events

### Email Not Sending
- Verify Resend API key in .env
- Check email address format
- Review Resend dashboard for delivery logs

### Model Evaluation Job Not Running
- Check Trigger.dev API key
- Verify cron schedule (0 2 1 * *)
- Review job logs in Trigger.dev dashboard

### LangSmith Traces Not Appearing
- Verify LANGSMITH_API_KEY in .env
- Check LANGSMITH_PROJECT name
- Ensure @traceable decorators are on functions

### Database Schema Issues
- Re-run migration from `001_initial_schema.sql`
- Check RLS policies with `SELECT * FROM pg_policies`
- Verify service role key has permissions

## Documentation

- **MODERN_STACK_SUMMARY.md**: Detailed architecture and integration guide
- **.cursorrules**: AI-assisted development context
- **README.md**: Updated with modern stack section
- **supabase/migrations/001_initial_schema.sql**: Schema documentation in comments

## Next Steps

1. Set up environment variables
2. Create Supabase project and run migration
3. Configure n8n workflows
4. Deploy to Vercel
5. Test webhook integration
6. Monitor first daily digest run
7. Review first monthly evaluation

All files are production-ready and follow best practices for compliance, security, and observability in regulated financial services.
