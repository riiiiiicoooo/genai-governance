# GenAI Governance Platform — Capacity Plan

**Last Updated:** March 2026
**Baseline Workload:** 43.8K interactions/month, 50 credit union members, 100 call center advisors

---

## Current State (43.8K interactions/month)

### Infrastructure

| Component | Current | Headroom | Notes |
|-----------|---------|----------|-------|
| **API servers (FastAPI)** | 2 x t3.large (2 CPU, 8GB) | ~40% CPU utilization avg | Peak hours (9am-12pm) hit 70% CPU |
| **LLM API (Claude 3.5 Sonnet)** | Token budget: 10M tokens/month from Anthropic | ~25% token capacity used | Interactions avg ~200 tokens each |
| **PostgreSQL (prompts + interactions + audit)** | 1 x r6g.large (2 CPU, 16GB) | 30% storage, 45% CPU | Prompts: 100MB; interactions: 500MB; audit: 200MB |
| **Redis cache** | 1 x r6g.large (2 CPU, 16GB) | 50% memory | Prompt cache + compliance rule cache |
| **S3 audit logs** | S3 Standard + Object Lock | Unlimited capacity | ~20MB/month growth |

### Cost

| Category | Monthly | Annual |
|----------|---------|--------|
| API servers (EC2) | $1.2K | $14K |
| LLM API (Claude tokens) | $0.8K | $10K |
| Database (RDS) | $0.8K | $10K |
| Cache (Redis) | $0.4K | $5K |
| Storage (S3 + Object Lock) | $0.2K | $3K |
| **Total** | **$3.4K** | **$42K** |

### Performance Baseline

| Metric | Value | SLO |
|--------|-------|-----|
| Guardrail latency (p95) | 320ms | 500ms ✓ |
| API availability | 99.6% | 99.5% ✓ |
| Guardrail accuracy (false negatives) | 99.2% | 99.5% ✓ |
| Guardrail false positive rate | 3.1% | <5% ✓ |
| Audit log completeness | 99.98% | 99.99% ✓ |
| Prompt approval rate | 100% | 100% ✓ |

### What Breaks First at Current Load

1. **LLM token budget** — At current usage (10M tokens/month for 43.8K interactions), token budget is used at 25% capacity; adding 100% more load would exhaust budget in 4 weeks
2. **API server CPU** — Peak morning hours hit 70% CPU; additional 50% load brings to 105% (requires autoscaling)
3. **PostgreSQL write throughput** — Audit log writes (1 write per interaction) + prompt approval writes cluster on same database; write latency can exceed 100ms under peak load
4. **S3 audit log batching** — Current implementation batches audit logs and uploads once per hour; with 5x volume, batching latency could exceed 1 hour (unacceptable for real-time audit)

---

## 2x Scenario (87.6K interactions/month)

### What Changes

- **Member base:** Credit union scales from 50 to 150+ members
- **Advisor base:** Call center expands from 100 to 250+ advisors
- **Interaction complexity:** More diverse questions (additional products, new LLM models) = longer prompts and responses
- **Compliance load:** NCUA examination may occur; audit trail must be production-ready

### Infrastructure Changes

| Component | 1x → 2x | Action | Timeline |
|-----------|---------|--------|----------|
| **API servers** | 2 → 4 instances (t3.large) | Enable autoscaling (target 60% CPU utilization) | Week 1 |
| **LLM API budget** | 10M → 20M tokens/month | Negotiate with Anthropic for volume discount (expect 10-15% price break) | Month 1 |
| **PostgreSQL** | 1 x r6g.large → 1 x r6g.xlarge (4 CPU, 32GB) | Increase capacity; add read replica for dashboard queries | Month 1 |
| **Audit logging** | Batch/hourly → Real-time streaming | Switch to Kafka-based audit log streaming (ensure real-time audit trail for regulators) | Month 2 |
| **Redis cache** | 1 x r6g.large → 1 x r6g.xlarge | Double cache size; expected hit rate improves from 70% to 80% | Month 1 |

### Cost Impact

| Category | 1x | 2x | Delta | % increase |
|----------|----|----|-------|-----------|
| Compute | $1.2K | $2.2K | +$1.0K | +83% |
| LLM API | $0.8K | $1.4K | +$0.6K | +75% (volume discount applied) |
| Database | $0.8K | $1.6K | +$0.8K | +100% |
| Cache | $0.4K | $0.7K | +$0.3K | +75% |
| Storage | $0.2K | $0.3K | +$0.1K | +50% |
| Kafka (new) | $0 | $0.5K | +$0.5K | ∞ |
| **Total** | **$3.4K** | **$6.7K** | **+$3.3K** | **+97%** |

### Performance at 2x

| Metric | 1x Baseline | 2x Expected | Status |
|--------|------------|-------------|--------|
| Guardrail latency (p95) | 320ms | 410ms | Still within SLO ✓ |
| API availability | 99.6% | 99.5% | Still within SLO ✓ |
| Guardrail accuracy | 99.2% | 99.1% | Slight degradation; acceptable |
| Audit log latency | Real-time | <100ms (Kafka) | Improved for regulatory readiness |

### What Breaks First at 2x

1. **LLM token budget becomes expensive** — 20M tokens/month at bulk rates is $1.4K/month; adding more models or longer conversations could require 30M tokens/month ($2.1K/month)
2. **PostgreSQL write contention** — Interaction+audit writes cluster on same database; write latency exceeds 200ms during peak hours
3. **Audit log volume exceeds batch size** — Batching every interaction for audit creates 87.6K audit records/month; streaming (Kafka) needed for near-real-time audit trail
4. **Cache effectiveness drops** — More diverse prompts and members means cache hit rate drops from 70% to 60%; guardrail evaluation has more cache misses, latency increases

### Scaling Triggers for 2x

- **LLM token daily spend > $50:** Negotiate for lower per-token pricing or consider smaller model fallback
- **API server CPU > 70% for sustained period:** Autoscale (+2 instances)
- **PostgreSQL write latency > 150ms:** Shard writes (separate table for hot data vs. archive)
- **Audit log streaming latency > 500ms:** Increase Kafka consumer parallelism
- **Cache hit rate < 60%:** Review prompt caching strategy; may need to increase cache TTL or implement intelligent eviction

---

## 10x Scenario (438K interactions/month)

### Market Reality at 10x

- **Member base:** 500+ credit union members (at scale, serving many regional credit unions)
- **Advisor base:** 1000+ call center advisors across multiple credit unions
- **Prompt diversity:** Specialized prompts per credit union (compliance rules vary by institution)
- **Regulatory load:** NCUA examinations now routine; audit trail must support forensic analysis

### What's Fundamentally Broken at 10x

1. **LLM token cost explodes** — 438K interactions * ~200 tokens avg = 87.6M tokens/month. At $0.01 per 1K tokens (bulk pricing), cost is $876/month. But inference time and higher-quality models might require 300+ tokens/interaction, pushing to 130M tokens = $1.3K/month in LLM alone. **Uneconomical; need to reduce token per interaction or use smaller, cheaper models.**

2. **Audit trail volume becomes unwieldy** — 438K interactions/month = 14.6K interactions/day = 600+ interactions/hour. Storing full audit trail (prompt, response, guardrail decisions) for each interaction with high-resolution metadata requires 1GB+ per month. At 10x volume, 10GB/month. Querying this in real-time for regulatory investigations becomes slow.

3. **Prompt management complexity** — 500+ credit unions, each with 5-10 custom prompts = 2500-5000 active prompts. Current prompt registry (single table) scales poorly. Need to partition by credit union or implement versioning/archival strategy.

4. **Guardrail latency math doesn't work** — 438K interactions/month with 4-check guardrail pipeline running in parallel (each 100-150ms) = sequential latency would be 500-600ms baseline. Adding any additional checks (new compliance rule, new model) breaches SLO.

### Architectural Changes Needed for 10x

| Problem | 1x/2x Solution | 10x Solution |
|---------|---|---|
| **LLM cost** | Pay-per-token for Claude 3.5 Sonnet | Fine-tune smaller model (Llama 3.1 70B or similar) for credit union domain; use for 70% of interactions; Claude only for complex reasoning |
| **Audit trail scalability** | Single PostgreSQL table + S3 backup | Partitioned audit table (by date/credit_union_id); cold storage (S3 Glacier) for >90 days; query via data warehouse (Snowflake/BigQuery) |
| **Prompt management** | Single registry table | Multi-tenant prompt system; partition by credit_union_id; versioning with soft deletes |
| **Guardrail latency** | Sequential checks | Pre-computed guardrail masks (combine rules offline); apply masks in 50ms instead of running full checks |
| **Regulatory compliance** | Batch audit export | Real-time audit with immutable event log (Kafka); queryable by regulator in minutes |

### Cost at 10x (Realistic Projection)

| Category | 1x | 10x | Ratio |
|----------|----|----|-------|
| Compute (API servers) | $1.2K | $8K | 6.7x |
| LLM API (fine-tuned model) | $0.8K | $3K | 3.75x |
| Database (partitioned, warehoused) | $0.8K | $10K | 12.5x |
| Cache | $0.4K | $3K | 7.5x |
| Storage (audit + cold archive) | $0.2K | $5K | 25x |
| Kafka (real-time audit) | $0 | $2K | ∞ |
| Data warehouse (Snowflake) | $0 | $10K | ∞ |
| **Total** | **$3.4K** | **$41K** | **12x** |

**Cost scales super-linearly (12x cost for 10x volume) due to compliance complexity and data warehouse costs.**

---

## Capacity Planning Roadmap

| Quarter | Trigger Level | Action | Investment |
|---------|---|---|---|
| Q2 2026 | Monitor 2x | Pre-stage 2x infrastructure; negotiate LLM pricing | $1K infrastructure |
| Q3 2026 | Approach 2x (70K interactions/month) | Activate API autoscaling; implement Kafka audit streaming | $4K infrastructure + 150 eng hours |
| Q4 2026 | Hit 2x (87.6K interactions/month) | Full 2x operational; audit trail production-ready for NCUA | Ongoing ops |
| Q1 2027 | Plan 5x (220K interactions/month) | Fine-tuned model evaluation; database sharding POC | 300 eng hours |
| Q2 2027+ | 5x+ territory | Execute 10x roadmap; multi-tenant architecture; data warehouse | $25K infra + 1000 eng hours over 6 months |

