# GenAI Governance Platform -- Improvement Recommendations

Technical analysis of the current platform with actionable recommendations for hardening guardrails, modernizing infrastructure, adopting new tooling, and scaling the governance framework for multi-institution deployment.

---

## 1. Product Overview

The GenAI Governance Platform is a compliance-first governance layer for deploying generative AI in NCUA-regulated credit unions. It sits between member-facing applications (member service copilot, loan document summarizer) and the LLM provider (Claude 3 Sonnet via AWS Bedrock), enforcing prompt version control, output screening, compliance logging, and model evaluation.

**Core modules:**
- **Prompt Registry** (`src/prompt_registry.py`) -- Versioned prompt templates with approval workflows (DRAFT -> PENDING_REVIEW -> APPROVED -> DEPLOYED -> DEPRECATED), variable schema validation, PII tracking, A/B testing, and content hash integrity verification.
- **Output Guardrails** (`src/output_guardrails.py`) -- Five deterministic checks (PII detection, hallucination detection, bias screening, compliance filtering, confidence assessment) using regex and pattern matching. No LLM calls in the guardrail path. ~180ms total latency for all five checks.
- **Compliance Logger** (`src/compliance_logger.py`) -- Append-only audit trail with SHA-256 hashing, auto-generated compliance events, 7-year retention, and examiner-ready report generation. Production target: S3 with Object Lock (WORM).
- **Model Evaluator** (`src/model_evaluator.py`) -- SR 11-7 compliant evaluation framework with accuracy, groundedness, consistency, and bias evaluators. Generates model cards with validation outcomes (APPROVED / CONDITIONAL / REQUIRES_REMEDIATION / REJECTED).
- **Guardrail Versioning** (`src/guardrail_versioning.py`) -- Rule lifecycle management with approval workflows, deployment tracking, rollback, and production metrics.

**Supporting infrastructure:**
- FastAPI backend (`api/app.py`) with dashboard endpoints
- React governance dashboard (`dashboard/dashboard.jsx`) with Recharts visualizations
- LangSmith tracing integration (`langsmith/governance_tracing.py`)
- n8n compliance event routing (`n8n/compliance_event_router.json`)
- Trigger.dev monthly evaluation jobs (`trigger-jobs/model_evaluation.ts`)
- React Email alert templates (`emails/compliance_alert.tsx`)
- Supabase PostgreSQL with Row-Level Security (`supabase/migrations/001_initial_schema.sql`)
- Promptfoo red team testing (`evals/promptfoo/promptfooconfig.yaml`)

**Production metrics (Q1):** 43,800 interactions, 97.4% delivered, 2.6% blocked, 191 PII exposures caught, 538 hallucinations blocked, 0 NCUA exam findings.

---

## 2. Current Architecture Assessment

### Strengths

1. **Deterministic guardrails are the right call for regulated finance.** Every block decision is explainable to an examiner with an exact regex match. No black-box ML models in the critical path.
2. **Append-only logging with WORM target** meets FFIEC record retention expectations and provides tamper-evident audit trails.
3. **SR 11-7 model card generation** is a genuine differentiator -- most governance platforms skip regulatory documentation.
4. **Separation of concerns** is clean: prompt management, output screening, logging, and evaluation are independent modules with clear interfaces.
5. **Comprehensive test coverage** -- 68+ unit tests for guardrails, adversarial stress tests, and promptfoo red team configurations.

### Weaknesses and Gaps

1. **No input guardrails.** The platform screens outputs but not inputs. The `FUTURE_ENHANCEMENTS.md` acknowledges this gap -- prompt injection detection was deferred because a human rep reviews every draft. With self-service chatbot expansion planned, this becomes a P0 gap.

2. **PII detection is regex-only.** The patterns in `output_guardrails.py` (lines 38-72) cover standard formats (SSN, credit card, routing number, DOB, email, phone) but miss:
   - Context-dependent PII (names combined with account details)
   - Non-standard formatting (SSN as "SSN123456789" -- noted in the ARCHITECTURE.md incident scenario)
   - International formats (IBAN, BIC/SWIFT, non-US phone)
   - Addresses, employer information, beneficiary names
   - PII in non-English text

3. **Hallucination detection is pattern-based, not grounding-aware.** The `HallucinationDetector` (lines 100-164 in `output_guardrails.py`) extracts dollar amounts and percentages from outputs and checks if they appear in the input context. This catches fabricated numbers but misses:
   - Fabricated policy details or procedures
   - Incorrect product names or features
   - Temporal hallucinations (wrong dates, expired promotions)
   - Subtle numerical distortions ($4,523.18 input reported as $4,523 output)

4. **Bias detection is shallow.** The `BiasScreener` (lines 167-240) uses keyword matching for stereotypes and measures response length disparity. It does not:
   - Measure sentiment polarity across demographic groups
   - Detect tone or formality differences
   - Evaluate helpfulness or action-item density
   - Perform counterfactual fairness testing

5. **Dashboard uses hardcoded synthetic data.** The `dashboard.jsx` component renders static arrays rather than fetching from the FastAPI backend. The API endpoints in `app.py` also return mostly synthetic data.

6. **CORS is wide open.** `app.py` line 20 sets `allow_origins=["*"]`. Acceptable for demo but must be locked down before any deployment.

7. **No dependency injection.** `app.py` instantiates `PromptRegistry()`, `GuardrailEngine()`, `ComplianceLogger()`, and `ModelEvaluator()` at module level. This makes testing harder and prevents configuration-driven initialization.

8. **Bug in guardrail_versioning.py.** Line 5: `from typing import Optional, list as List` -- this imports the built-in `list` function and aliases it as `List`, which shadows the typing `List`. Should be `from typing import Optional, List` or (for Python 3.11+) use built-in `list` directly in type hints.

9. **No rate limiting or authentication on API.** The FastAPI backend has no auth middleware, API key validation, or rate limiting. The `/api/governance/check` endpoint accepts arbitrary text for guardrail screening with no access control.

10. **No structured error handling.** Guardrail checks silently return passing results on exceptions rather than failing safely. The `PIIDetector.check()` method (line 79) catches all exceptions and returns `CheckResult(passed=True)`, which means a crashed PII check reports "no PII found."

---

## 3. Recommended Improvements

### 3.1 Add Input Guardrails for Prompt Injection Defense

**Why:** The platform currently has no input screening. With self-service chatbot expansion planned, members could inject instructions that manipulate model behavior. NIST AI 100-2 (Adversarial Machine Learning) and OWASP Top 10 for LLM Applications both rank prompt injection as the #1 risk.

**What to build:**

Add an `InputGuardrailEngine` in a new module `src/input_guardrails.py`:

```python
# Detection layers (all deterministic, matching the output guardrail philosophy):
# 1. Known injection pattern matching (instruction override, role-play, encoding tricks)
# 2. Structural analysis (unusual formatting, embedded system messages, delimiter abuse)
# 3. Semantic anomaly detection (input length vs. expected, keyword density)
# 4. Encoding detection (base64, ROT13, hex in user inputs)
```

**Code references:** The `evals/adversarial/guardrail_stress_test.py` already contains 35 adversarial test cases that define the attack surface. The `evals/promptfoo/promptfooconfig.yaml` has 10 jailbreak and 10 injection test cases. These should become the test suite for the input guardrails.

**Libraries to evaluate:**
- **rebuff** (https://github.com/protectai/rebuff) -- Open-source prompt injection detection with heuristic, LLM-based, and vector similarity detection. Can run the heuristic layer deterministically.
- **LLM Guard** by Protect AI (https://github.com/protectai/llm-guard, v0.3.x) -- Comprehensive input/output scanner with prompt injection, toxicity, ban topics, invisible text, and code detection scanners. Python-native, runs locally, supports custom scanners.
- **Vigil** (https://github.com/deadbits/vigil-llm) -- Lightweight prompt injection scanner using YARA rules and embedding similarity. The YARA-rule approach aligns with the platform's deterministic philosophy.

**Priority:** P0. Prerequisite for self-service chatbot expansion.

---

### 3.2 Upgrade PII Detection with Microsoft Presidio

**Why:** The current regex-based PII detection covers 7 entity types. Microsoft Presidio supports 30+ entity types out of the box, handles context-dependent detection (e.g., a name next to an account number is higher risk than a name alone), and supports custom recognizers for domain-specific patterns like Symitar member IDs.

**What to do:**

Replace the regex patterns in `PIIDetector` (lines 38-72 of `output_guardrails.py`) with Presidio's `AnalyzerEngine`:

```python
# pip install presidio-analyzer presidio-anonymizer
# Presidio v2.2.x (latest stable)

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern

analyzer = AnalyzerEngine()

# Add custom recognizer for credit union member IDs
member_id_pattern = Pattern(name="member_id", regex=r"\bMEM-\d{8}\b", score=0.85)
member_id_recognizer = PatternRecognizer(
    supported_entity="MEMBER_ID",
    patterns=[member_id_pattern]
)
analyzer.registry.add_recognizer(member_id_recognizer)

# Analyze text -- returns scored entities with context
results = analyzer.analyze(text=output_text, language="en",
                           entities=["CREDIT_CARD", "US_SSN", "US_BANK_NUMBER",
                                     "PHONE_NUMBER", "EMAIL_ADDRESS", "PERSON",
                                     "MEMBER_ID"])
```

**Why Presidio over regex:**
- NLP-backed entity recognition (spaCy models) catches PII that regex misses
- Context scoring: "John" alone scores low; "John, account 1234567890" scores high
- Pre-built recognizers for US financial entities (SSN, ITIN, bank account, routing number, credit card with Luhn validation)
- Custom recognizer API for credit-union-specific patterns
- Anonymization engine for redacting PII in audit exports (examiner reports)
- Apache 2.0 license, actively maintained by Microsoft, production-grade

**Integration point:** Keep the existing regex patterns as a fast pre-filter. Run Presidio as a second pass on outputs that pass the regex layer. This preserves the <200ms latency target for 95% of outputs while catching edge cases.

**Priority:** P1. Addresses known false-negative risk documented in `ARCHITECTURE.md` incident scenario.

---

### 3.3 Add Grounding-Aware Hallucination Detection

**Why:** The current `HallucinationDetector` only checks whether dollar amounts and percentages in the output appear in the input context. It cannot detect fabricated procedures, incorrect product names, or subtle numerical distortions.

**What to build:**

Layer grounding verification on top of the existing pattern matching:

1. **Factual claim extraction:** Parse output for verifiable claims (amounts, dates, product names, policy statements, contact information).
2. **Source attribution scoring:** For each claim, compute a similarity score against the input context using lightweight text matching (TF-IDF or BM25, not embeddings -- keeps it deterministic and fast).
3. **Confidence thresholds by claim type:** Financial figures require exact match (current behavior). Dates require fuzzy match (within 1 day). Product names require substring match. Policy statements require high TF-IDF similarity to source.

**Libraries to consider:**
- **sentence-transformers** (https://github.com/UKPLab/sentence-transformers, v3.x) -- For semantic similarity when deterministic matching is insufficient. Use a small model like `all-MiniLM-L6-v2` (80MB, ~5ms inference) as an optional second pass.
- **rank-bm25** (https://github.com/dorianbrown/rank_bm25) -- Pure Python BM25 implementation for fast, deterministic document-to-claim similarity scoring without ML models.
- **spaCy** (v3.7+) with `en_core_web_sm` -- Named entity recognition for extracting verifiable entities (ORG, MONEY, DATE, PERCENT) from both input and output, then cross-referencing.

**Code reference:** The `HallucinationDetector._extract_dollar_amounts()` and `_extract_percentages()` methods (lines 115-140) should be extended with spaCy NER for broader entity extraction.

**Priority:** P1. Hallucination is the highest-volume guardrail trigger (538 blocks in Q1, 1.23% of outputs).

---

### 3.4 Implement Structured LLM Output with Pydantic Models

**Why:** The current pipeline sends freeform prompts and receives unstructured text responses. This makes guardrail validation harder -- every check must parse natural language. Structured output constrains the LLM response format, making validation deterministic and enabling type-safe downstream processing.

**What to do:**

Use Pydantic models to define expected output schemas. Both Anthropic and AWS Bedrock support structured/constrained output formats:

```python
from pydantic import BaseModel, Field
from typing import Literal

class MemberServiceResponse(BaseModel):
    greeting: str = Field(max_length=100)
    response_body: str = Field(max_length=2000)
    sources_referenced: list[str] = Field(
        description="Context items referenced in the response"
    )
    confidence: Literal["high", "medium", "low"]
    contains_financial_figures: bool
    figures_cited: list[str] = Field(
        default_factory=list,
        description="All dollar amounts or percentages mentioned"
    )
```

**Benefits for guardrails:**
- `contains_financial_figures` + `figures_cited` makes hallucination checking trivial (compare `figures_cited` against input context)
- `sources_referenced` enables automated grounding verification
- `confidence` gives the model a structured way to express uncertainty
- Schema validation catches malformed responses before guardrail checks run
- Reduces false positives from guardrails misinterpreting response structure

**Libraries:**
- **instructor** (https://github.com/jxnl/instructor, v1.x) -- Pydantic-based structured output extraction for LLM APIs. Supports Anthropic, OpenAI, AWS Bedrock. Handles retries on schema validation failures.
- **outlines** (https://github.com/dottxt-ai/outlines, v0.1.x) -- Structured generation with constrained decoding. More relevant for self-hosted models but the grammar-based approach is worth evaluating.

**Priority:** P1. Reduces guardrail complexity and false positive rate.

---

### 3.5 Replace In-Memory Storage with Production-Ready Persistence

**Why:** All four core modules use in-memory storage (`self._templates = {}`, `self._logs = []`, etc.). The `ARCHITECTURE.md` describes S3 Object Lock as the production target for compliance logs, and Supabase as the database, but the Python modules have no database integration.

**What to do:**

1. **Add a repository pattern** to decouple storage from business logic:

```python
# src/repositories/base.py
from abc import ABC, abstractmethod

class InteractionLogRepository(ABC):
    @abstractmethod
    async def append(self, log: InteractionLog) -> str: ...
    @abstractmethod
    async def query(self, filters: dict) -> list[InteractionLog]: ...
    @abstractmethod
    async def get_by_id(self, interaction_id: str) -> InteractionLog | None: ...

# src/repositories/supabase.py
class SupabaseInteractionLogRepository(InteractionLogRepository):
    def __init__(self, supabase_client):
        self.client = supabase_client
    # ... Supabase-specific implementation

# src/repositories/memory.py
class InMemoryInteractionLogRepository(InteractionLogRepository):
    # Current implementation, used for tests and demos
```

2. **Wire up Supabase** using the existing schema in `supabase/migrations/001_initial_schema.sql`. The tables (`interaction_logs`, `compliance_events`, `prompt_templates`, `prompt_versions`, `guardrail_configs`, `model_evaluations`) already exist in the migration.

3. **Add S3 Object Lock writes** for the compliance logger. Each interaction log should be written to both Supabase (for queryability) and S3 (for WORM immutability).

**Libraries:**
- **supabase-py** (https://github.com/supabase/supabase-py, v2.x) -- Official Python client for Supabase, supports async operations, RLS-aware queries.
- **boto3** (already in `requirements.txt` at v1.34.17) -- S3 Object Lock API via `put_object_retention()` and `put_object_legal_hold()`.

**Priority:** P0. Required for any real deployment. The current in-memory storage loses all data on restart.

---

### 3.6 Harden the FastAPI Backend

**Why:** The API layer (`api/app.py`) has no authentication, no rate limiting, open CORS, no structured error handling, and returns synthetic data. This is the primary attack surface for the governance platform.

**What to do:**

1. **Add authentication middleware** using Supabase Auth (JWT validation):

```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    # Verify JWT against Supabase
    # Extract user role (compliance_officer, model_owner, examiner, admin)
    # Return user context
    ...
```

2. **Lock down CORS** to specific origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://governance.creditunion.local", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

3. **Add rate limiting** with `slowapi` (https://github.com/laurentS/slowapi, v0.1.x):

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/governance/check")
@limiter.limit("60/minute")
async def check_output(request: Request, payload: GovernanceCheckRequest):
    ...
```

4. **Add dependency injection** using FastAPI's `Depends()` system instead of module-level instances:

```python
def get_guardrail_engine(config: Settings = Depends(get_settings)) -> GuardrailEngine:
    return GuardrailEngine(config=config)

@app.post("/api/governance/check")
async def check_output(
    payload: GovernanceCheckRequest,
    engine: GuardrailEngine = Depends(get_guardrail_engine),
    logger: ComplianceLogger = Depends(get_compliance_logger),
):
    ...
```

5. **Fix error handling** -- guardrail check failures should fail closed (block), not fail open (pass):

```python
# Current (DANGEROUS -- fail open):
except Exception:
    return CheckResult(passed=True)

# Fixed (fail closed):
except Exception as e:
    logger.error(f"Guardrail check failed: {e}")
    return CheckResult(
        passed=False,
        severity="block",
        details=f"Guardrail check error: {type(e).__name__}. Failing closed."
    )
```

**Priority:** P0. Security hardening is non-negotiable before deployment.

---

### 3.7 Connect Dashboard to Live API Data

**Why:** The `dashboard.jsx` component renders hardcoded arrays (`guardrailTrends`, `modelPerformance`, etc.) instead of fetching from the backend. The FastAPI endpoints exist but return synthetic data. For a governance dashboard to be examiner-ready, it must show real data.

**What to do:**

1. Add React Query (TanStack Query) for data fetching with caching and automatic refresh:

```jsx
import { useQuery } from '@tanstack/react-query';

function useGuardrailMetrics(period) {
  return useQuery({
    queryKey: ['guardrails', period],
    queryFn: () => fetch(`/api/dashboard/guardrails?period=${period}`).then(r => r.json()),
    refetchInterval: 60000, // Refresh every minute
  });
}
```

2. Update FastAPI endpoints to query Supabase views instead of returning synthetic data. The `supabase/migrations/001_initial_schema.sql` already defines a `dashboard_metrics` table and `examiner_audit_view`.

3. Add WebSocket support for real-time compliance event notifications:

```python
# FastAPI WebSocket for live compliance events
@app.websocket("/ws/events")
async def compliance_events_ws(websocket: WebSocket):
    await websocket.accept()
    # Subscribe to Supabase realtime channel for compliance_events
    ...
```

**Priority:** P2. Important for production credibility but functional without it.

---

### 3.8 Improve Bias Detection with Quantitative Metrics

**Why:** The current `BiasScreener` uses keyword matching for stereotypes and response length comparison. Industry best practice (per NIST AI 100-1 and the EU AI Act's fairness requirements) calls for multi-dimensional bias measurement.

**What to build:**

Extend `BiasScreener` with quantitative fairness metrics:

1. **Sentiment polarity analysis** -- Measure average sentiment score per demographic group using a lightweight classifier. Flag if sentiment disparity exceeds threshold.
2. **Readability scoring** -- Measure Flesch-Kincaid readability score per group. Flag if readability disparity suggests differential language complexity.
3. **Action item density** -- Count actionable recommendations per group. Flag if one group consistently receives fewer concrete next steps.
4. **Counterfactual fairness testing** -- For paired test cases (same question, different demographic context), measure cosine similarity of responses. Low similarity indicates differential treatment.

**Libraries:**
- **TextBlob** (https://github.com/sloria/TextBlob) -- Simple sentiment analysis (polarity + subjectivity) suitable for batch bias evaluation. Lightweight, no GPU required.
- **textstat** (https://github.com/textstat/textstat, v0.7.x) -- Readability scoring (Flesch-Kincaid, Gunning Fog, SMOG) for measuring language complexity disparity.
- **Fairlearn** by Microsoft (https://github.com/fairlearn/fairlearn, v0.10.x) -- Fairness assessment toolkit with demographic parity, equalized odds, and bounded group loss metrics. Designed for ML systems but applicable to LLM evaluation.

**Code reference:** The `BiasEvaluator` in `model_evaluator.py` (lines 200-245) already measures response length disparity. These additional metrics should be added to the same evaluator.

**Priority:** P2. Strengthens fair lending documentation for NCUA examiners.

---

### 3.9 Add Guardrail Performance Monitoring and Drift Detection

**Why:** Guardrail effectiveness can degrade over time as new attack patterns emerge, model behavior shifts, or PII formats change. The platform needs automated detection of guardrail drift, not just model drift.

**What to build:**

1. **Guardrail metrics collection** -- Track per-check precision and recall over time using a labeled sample:
   - Sample 1% of PASS results for human review (false negative detection)
   - Track all BLOCK results for human override patterns (false positive detection)
   - Compute weekly precision/recall per check type

2. **Anomaly detection on block rates** -- Alert when block rate deviates significantly from historical baseline:
   - PII detection block rate jumps from 0.4% to 2% (possible new PII format)
   - Hallucination block rate drops from 1.2% to 0.1% (possible check failure)
   - Compliance filter block rate spikes (possible model behavior change)

3. **Pattern coverage reporting** -- For regex-based checks, report which patterns matched and which never matched. Patterns that never match may be obsolete; new patterns may be needed.

**Libraries:**
- **WhyLabs / LangKit** (https://github.com/whylabs/langkit, v0.0.x) -- LLM telemetry toolkit by WhyLabs that computes text quality metrics (toxicity, sentiment, relevance, similarity) and integrates with WhyLabs for drift monitoring. Provides `TextMetricCalculators` for batch analysis.
- **Evidently AI** (https://github.com/evidentlyai/evidently, v0.5.x) -- ML monitoring with data drift, target drift, and model performance reports. Supports text data profiling and custom metric computation.

**Priority:** P2. Essential for ongoing governance but not blocking initial deployment.

---

### 3.10 Add End-to-End Encryption for Audit Trail Integrity

**Why:** The compliance logger computes SHA-256 hashes of input/output text but does not chain hashes or sign entries. An attacker with database access could delete and re-insert entries without detection. Blockchain-style hash chaining provides tamper-evident logging.

**What to build:**

```python
class TamperEvidentLogger:
    def __init__(self):
        self._previous_hash = "GENESIS"

    def log(self, interaction: InteractionLog) -> str:
        # Chain hash includes previous entry's hash
        entry_data = f"{self._previous_hash}|{interaction.interaction_id}|{interaction.timestamp}"
        entry_hash = hashlib.sha256(entry_data.encode()).hexdigest()
        interaction.chain_hash = entry_hash
        interaction.previous_hash = self._previous_hash
        self._previous_hash = entry_hash
        return entry_hash

    def verify_chain(self, logs: list[InteractionLog]) -> bool:
        """Verify no entries have been tampered with or deleted."""
        prev = "GENESIS"
        for log in logs:
            expected = hashlib.sha256(
                f"{prev}|{log.interaction_id}|{log.timestamp}".encode()
            ).hexdigest()
            if log.chain_hash != expected:
                return False
            prev = log.chain_hash
        return True
```

Additionally, consider signing each log entry with an asymmetric key (the private key held by a Hardware Security Module or AWS KMS) so that even the application cannot forge entries after the fact.

**Priority:** P3. Defense-in-depth for audit trail integrity, complementary to S3 Object Lock.

---

## 4. New Technologies and Trends

### 4.1 Guardrails AI (guardrails-ai/guardrails)

**What it is:** An open-source Python framework for adding structural, type, and quality guarantees to LLM outputs. Provides a `Guard` class that wraps LLM calls with validators that check output quality, format, and safety.

**Why it matters for this platform:** The current guardrail engine is hand-built with custom regex patterns. Guardrails AI provides a plugin ecosystem of 50+ validators (PII detection, toxicity, profanity, hallucination, competitor mentions, reading level) that can be composed declaratively. This would allow the compliance team to configure guardrails without writing Python.

**How to integrate:** Use Guardrails AI validators alongside the existing custom checks:
```python
from guardrails import Guard
from guardrails.hub import DetectPII, ToxicLanguage, CompetitorCheck

guard = Guard().use_many(
    DetectPII(pii_entities=["SSN", "CREDIT_CARD", "US_BANK_NUMBER"]),
    ToxicLanguage(threshold=0.8),
    CompetitorCheck(competitors=["Chase", "Wells Fargo", "Bank of America"]),
)
```

**Link:** https://github.com/guardrails-ai/guardrails

---

### 4.2 NVIDIA NeMo Guardrails

**What it is:** An open-source toolkit by NVIDIA for adding programmable guardrails to LLM-based applications. Uses Colang (a domain-specific language) to define conversational safety policies as dialogue flows.

**Why it matters:** NeMo Guardrails provides a layer above individual check functions. It models safety policies as conversation-level rules, enabling multi-turn safety enforcement (e.g., "if the user asks about rates and then asks to 'ignore' the previous response, block the second message"). The platform's current guardrails operate on individual outputs without conversational context.

**How to integrate:** Use Colang to define credit-union-specific safety policies:
```colang
define user ask for rate guarantee
  "what rate will I definitely get"
  "can you guarantee me this rate"
  "promise me this rate"

define flow rate guarantee
  user ask for rate guarantee
  bot respond with cannot guarantee rates
  bot suggest speaking with loan officer
```

**Link:** https://github.com/NVIDIA/NeMo-Guardrails

---

### 4.3 Microsoft Presidio for PII Detection

**What it is:** An SDK for PII detection and anonymization, combining NLP models (spaCy), regex patterns, and context-aware scoring. Supports 30+ entity types, custom recognizers, and multiple languages.

**Why it matters:** As detailed in Section 3.2, the current regex-only PII detection misses context-dependent PII and non-standard formats. Presidio's context scoring (a name near an account number scores higher than a name alone) is specifically designed for financial services use cases.

**Version:** v2.2.x (latest stable as of early 2025)
**Link:** https://github.com/microsoft/presidio

---

### 4.4 LLM Guard by Protect AI

**What it is:** A comprehensive input/output scanner for LLM interactions. Provides scanners for prompt injection, PII leakage, toxicity, ban topics, invisible text, code detection, and more. Runs locally without external API calls.

**Why it matters:** LLM Guard directly addresses the platform's input guardrail gap (Section 3.1). Its `PromptInjection` scanner uses a fine-tuned DeBERTa model that detects injection attempts with higher accuracy than regex patterns. The scanner runs in ~50ms, fitting within the platform's latency budget.

**Key scanners relevant to this platform:**
- `PromptInjection` -- Detects injection in user inputs
- `BanTopics` -- Blocks requests about forbidden topics
- `Toxicity` -- Detects hate speech and toxic content
- `Invisible Text` -- Detects unicode tricks used for prompt injection
- `Regex` -- Custom pattern matching (can port existing patterns)
- `Anonymize` / `Deanonymize` -- PII handling with presidio integration

**Version:** v0.3.x
**Link:** https://github.com/protectai/llm-guard

---

### 4.5 OWASP Top 10 for LLM Applications (2025)

**What it is:** The OWASP Foundation published the Top 10 security risks for LLM-based applications, updated for 2025. This has become the standard reference for LLM security assessments.

**Why it matters:** The platform's adversarial testing (`evals/promptfoo/promptfooconfig.yaml`) covers several OWASP categories but not all. The current guardrail framework should be mapped to the OWASP Top 10:

| OWASP LLM Risk | Platform Coverage | Gap |
|---|---|---|
| LLM01: Prompt Injection | Not covered (output only) | P0 -- add input guardrails |
| LLM02: Insecure Output Handling | Partially (PII, compliance) | Need XSS/injection check on rendered output |
| LLM03: Training Data Poisoning | N/A (using Bedrock) | Provider responsibility |
| LLM04: Model Denial of Service | Not covered | Add token budget limits |
| LLM05: Supply Chain | Partially (Bedrock abstraction) | Document model provenance in model cards |
| LLM06: Sensitive Information Disclosure | Covered (PII detection) | Strengthen with Presidio |
| LLM07: Insecure Plugin Design | N/A (no plugins) | -- |
| LLM08: Excessive Agency | N/A (read-only copilot) | Document in risk assessment |
| LLM09: Overreliance | Partially (confidence score) | Add citation requirements |
| LLM10: Model Theft | N/A (using Bedrock) | Provider responsibility |

**Link:** https://owasp.org/www-project-top-10-for-large-language-model-applications/

---

### 4.6 EU AI Act Compliance Considerations

**What it is:** The EU AI Act (entered into force August 2024, with phased enforcement through 2027) establishes risk-based regulation for AI systems. While the credit union is US-based (NCUA-regulated), the EU AI Act's framework is influencing US regulatory expectations, and NCUA examiners are increasingly aware of global AI governance standards.

**Why it matters:** The EU AI Act requires high-risk AI systems to have:
- Risk management systems (the platform provides this)
- Data governance (partially covered by PII detection)
- Technical documentation (model cards address this)
- Record-keeping (compliance logger handles this)
- Transparency and user information (not currently addressed)
- Human oversight (rep review workflow satisfies this)
- Accuracy, robustness, and cybersecurity (partially covered)

**What to add:** Even though EU compliance is not legally required:
- Add transparency notices in LLM-generated content ("This response was drafted with AI assistance")
- Document data governance procedures for training/fine-tuning data
- Add cybersecurity risk assessment to model cards
- Include the platform in the institution's broader AI inventory

---

### 4.7 NIST AI Risk Management Framework (AI RMF 1.0)

**What it is:** NIST's framework for managing risks from AI systems, organized around four functions: Govern, Map, Measure, and Manage. Published January 2023, with the companion Generative AI Profile (NIST AI 600-1) published July 2024 specifically for GenAI risks.

**Why it matters:** FFIEC and NCUA are expected to align future AI guidance with NIST AI RMF. The platform should proactively map its controls to NIST AI RMF functions:

- **Govern:** Prompt approval workflows, guardrail versioning, compliance officer oversight
- **Map:** Model cards with intended use, out-of-scope uses, risk factors
- **Measure:** Evaluation framework with accuracy, groundedness, bias, compliance dimensions
- **Manage:** Guardrail engine with automated blocking, compliance event routing, incident response

The NIST AI 600-1 Generative AI Profile adds specific risks (hallucination, CBRN information, data privacy) that the platform partially addresses.

**Link:** https://www.nist.gov/artificial-intelligence/executive-order-safe-secure-and-trustworthy-artificial-intelligence

---

### 4.8 Agentic AI Governance (Emerging Trend)

**What it is:** As LLM applications evolve from simple prompt-response copilots to multi-step agentic workflows (tool use, function calling, autonomous decision-making), governance frameworks must evolve to handle:
- **Action authorization** -- Which tools/APIs can the agent invoke?
- **Multi-step audit trails** -- Logging not just input/output but intermediate reasoning steps
- **Guardrails on tool calls** -- Screening function call parameters, not just text output
- **Budget/scope limits** -- Preventing runaway agent loops

**Why it matters:** The credit union's roadmap includes self-service chatbot (per `FUTURE_ENHANCEMENTS.md`), which may evolve into an agentic system (balance lookups, transaction disputes, appointment scheduling). The governance framework should be designed to accommodate agentic patterns.

**What to build:**
- Add a `ToolCallGuardrail` that validates function call names and parameters before execution
- Extend the compliance logger to capture multi-step traces (conversation-level logging, not just interaction-level)
- Add token budget enforcement per conversation session
- Design approval workflows for new tool/API integrations

**Libraries:**
- **LangGraph** by LangChain (https://github.com/langchain-ai/langgraph) -- Framework for building stateful, multi-actor LLM applications with built-in checkpointing and human-in-the-loop patterns.
- **CrewAI** (https://github.com/crewAIInc/crewAI) -- Multi-agent orchestration with role-based access control and task delegation patterns.

---

### 4.9 Continuous Red Teaming and Automated Adversarial Testing

**What it is:** Moving beyond static test suites to continuous, automated adversarial testing that discovers new attack vectors as they emerge. This includes automated prompt fuzzing, mutation testing of guardrail rules, and integration with threat intelligence feeds.

**Why it matters:** The platform has excellent static adversarial tests (35 cases in `guardrail_stress_test.py`, 45 in `promptfooconfig.yaml`) but these tests are fixed. New jailbreak techniques emerge regularly. Continuous red teaming automates the discovery of novel bypasses.

**Tools:**
- **Promptfoo** (already integrated, https://github.com/promptfoo/promptfoo) -- Extend the existing configuration with promptfoo's built-in red team plugin (`redteam` strategy) which generates adversarial inputs automatically using an attacker LLM.
- **Garak** by NVIDIA (https://github.com/NVIDIA/garak, v0.9.x) -- LLM vulnerability scanner that probes for prompt injection, data leakage, hallucination, toxicity, and more. Runs automated attack campaigns and generates vulnerability reports. Purpose-built for LLM red teaming.
- **PyRIT** by Microsoft (https://github.com/Azure/PyRIT) -- Python Risk Identification Toolkit for generative AI. Supports multi-turn attack strategies, scoring with content safety classifiers, and automated report generation.

**Priority:** P2. Strengthens ongoing security posture.

---

### 4.10 Observability and Cost Management

**What it is:** As LLM usage scales, comprehensive observability (latency, token usage, cost, error rates) and cost management (budget alerts, token optimization, model routing) become critical.

**Why it matters:** The platform integrates LangSmith for tracing (`langsmith/governance_tracing.py`) but lacks cost enforcement. At 43,800 interactions/quarter with Claude 3 Sonnet via Bedrock, costs are manageable. Scaling to 5+ use cases or switching to more expensive models requires cost governance.

**Tools to evaluate:**
- **Helicone** (https://github.com/Helicone/helicone) -- Open-source LLM observability platform with cost tracking, latency monitoring, rate limiting, and caching. Acts as a proxy between the application and LLM provider.
- **OpenLLMetry** (https://github.com/traceloop/openllmetry) -- OpenTelemetry-based instrumentation for LLM applications. Provides standardized traces, metrics, and logs for LLM calls. Integrates with existing observability stacks (Datadog, Grafana, New Relic).
- **Portkey** (https://github.com/Portkey-ai/gateway) -- AI gateway with automatic retries, fallbacks, load balancing, budget management, and caching. Supports 200+ LLM providers.

---

## 5. Priority Roadmap

### P0 -- Must Fix Before Any Deployment

| Item | Effort | Description |
|------|--------|-------------|
| **Production persistence** (3.5) | 2-3 weeks | Replace in-memory storage with Supabase repositories and S3 Object Lock for compliance logs |
| **API security hardening** (3.6) | 1-2 weeks | Authentication, rate limiting, CORS lockdown, fail-closed error handling, dependency injection |
| **Input guardrails** (3.1) | 2-3 weeks | Prompt injection detection for self-service chatbot expansion. Evaluate LLM Guard or rebuff for injection detection |
| **Fix guardrail_versioning.py bug** | 1 hour | Change `from typing import Optional, list as List` to `from typing import Optional, List` on line 5 |
| **Fix fail-open error handling** | 2 hours | Change all guardrail `except Exception: return CheckResult(passed=True)` to fail closed |

**Total P0 effort:** 5-8 weeks

### P1 -- Critical Improvements for Production Quality

| Item | Effort | Description |
|------|--------|-------------|
| **Presidio PII detection** (3.2) | 1-2 weeks | Add Microsoft Presidio as second-pass PII detection, keep regex as fast pre-filter |
| **Grounding-aware hallucination detection** (3.3) | 2-3 weeks | Add claim extraction and source attribution scoring using spaCy NER and BM25 |
| **Structured LLM output** (3.4) | 1-2 weeks | Define Pydantic models for each use case output format, integrate with instructor library |
| **OWASP Top 10 gap analysis** (4.5) | 1 week | Map all guardrails to OWASP LLM risks, document gaps, prioritize missing coverage |

**Total P1 effort:** 5-8 weeks

### P2 -- Operational Excellence

| Item | Effort | Description |
|------|--------|-------------|
| **Live dashboard** (3.7) | 2-3 weeks | Connect React dashboard to Supabase via FastAPI, add TanStack Query, real-time WebSocket events |
| **Enhanced bias detection** (3.8) | 2 weeks | Add sentiment, readability, action-item density metrics. Integrate textstat and Fairlearn |
| **Guardrail drift monitoring** (3.9) | 2 weeks | Track precision/recall over time, anomaly detection on block rates, pattern coverage reporting |
| **Continuous red teaming** (4.9) | 1-2 weeks | Integrate Garak or PyRIT for automated adversarial testing on a weekly schedule |
| **NIST AI RMF mapping** (4.7) | 1 week | Document platform controls against NIST AI RMF functions and NIST AI 600-1 GenAI Profile |

**Total P2 effort:** 8-11 weeks

### P3 -- Strategic Enhancements

| Item | Effort | Description |
|------|--------|-------------|
| **Hash-chained audit trail** (3.10) | 1 week | Add tamper-evident hash chaining to compliance logger for defense-in-depth |
| **Agentic governance patterns** (4.8) | 3-4 weeks | Tool call guardrails, multi-step traces, token budgets for future chatbot/agent use cases |
| **Cost management** (4.10) | 1-2 weeks | Integrate Helicone or OpenLLMetry for cost tracking, budget alerts, and usage analytics |
| **NeMo Guardrails evaluation** (4.2) | 1-2 weeks | Evaluate Colang for conversation-level safety policies beyond per-output checks |
| **EU AI Act alignment** (4.6) | 1 week | Add transparency notices, data governance documentation, cybersecurity risk assessment to model cards |
| **Multi-institution tenancy** | 4-6 weeks | If productizing: add organization-scoped data isolation, per-tenant guardrail configs, usage-based billing |

**Total P3 effort:** 11-17 weeks

---

## Summary

The GenAI Governance Platform has a strong foundation: deterministic guardrails, SR 11-7 model cards, append-only audit trails, and a clean modular architecture. The critical gaps are operational (in-memory storage, no API security, no input guardrails) rather than architectural. Addressing the P0 items transforms this from a portfolio demonstration into a deployable governance layer. The P1 improvements (Presidio PII, grounding-aware hallucination detection, structured output) meaningfully reduce false negative rates in the guardrail pipeline. P2 and P3 items position the platform for scale, ongoing compliance, and evolution toward agentic AI governance.

Total estimated effort across all priorities: 29-44 weeks.
Recommended Phase 1 (P0 + P1): 10-16 weeks, ~$35-55k at typical consulting rates.
