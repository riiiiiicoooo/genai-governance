"""
FastAPI Backend for GenAI Governance Platform

Exposes REST API for:
- Dashboard data (overview, guardrails, models, compliance)
- Compliance queries (interactions, events)
- Governance checks (submit output through guardrail pipeline)
"""

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.prompt_registry import PromptRegistry, UseCase, RiskTier, PromptStatus
from src.output_guardrails import GuardrailEngine, GuardrailAction
from src.compliance_logger import ComplianceLogger, InteractionLog, LogLevel
from src.model_evaluator import ModelEvaluator
from src.db import init_db, SessionLocal, Session

# ============================================================================
# PRODUCTION NOTES
# This is a portfolio demonstration. In a production deployment:
# - All endpoints would require Clerk/Auth0 JWT middleware with role-based access
# - Guardrail checks would use NeMo Guardrails or Guardrails AI for classifier-
#   based prompt injection detection (not just regex — see OWASP LLM Top 10)
# - Compliance logs containing PII would be encrypted at rest (AES-256-GCM)
#   with key rotation via AWS KMS, satisfying SR 11-7 examination requirements
# ============================================================================

# ============================================================================
# Request/Response Models
# ============================================================================

class GuardrailCheckRequest(BaseModel):
    """Request to run guardrails on output."""
    output_text: str = Field(..., description="LLM output to screen")
    input_context: str = Field(..., description="Input context used by LLM")
    template_id: str = Field("", description="Prompt template ID")
    version_id: str = Field("", description="Prompt version ID")
    model_id: str = Field("", description="Model ID")


class GuardrailCheckResponse(BaseModel):
    """Response from guardrail check."""
    interaction_id: str
    action: str  # deliver, deliver_with_flag, block_for_review, block_and_alert
    checks_passed: int
    checks_warned: int
    checks_blocked: int
    pii_detected: bool
    hallucination_detected: bool
    bias_detected: bool
    compliance_violation: bool
    total_processing_time_ms: float
    detailed_results: dict


class DashboardOverviewResponse(BaseModel):
    """Dashboard overview metrics."""
    total_interactions: int
    delivered_pct: float
    blocked_pct: float
    pii_caught: int
    pii_caught_pct: float
    compliance_events: int
    unresolved_events: int
    avg_guardrail_latency_ms: float
    models_in_production: int
    models_validated: int


class GuardrailStatsResponse(BaseModel):
    """Guardrail performance statistics."""
    check_name: str
    pass_count: int
    warn_count: int
    block_count: int
    block_rate_pct: float


class ModelStatusResponse(BaseModel):
    """Model evaluation status."""
    model_id: str
    model_name: str
    use_case: str
    risk_tier: str
    validation_status: str  # approved, conditional, remediation, unvalidated
    last_eval_date: Optional[str]
    next_eval_date: Optional[str]
    latest_scores: dict


class ComplianceEventResponse(BaseModel):
    """Compliance event details."""
    event_id: str
    interaction_id: str
    event_type: str
    severity: str
    description: str
    timestamp: str
    status: str  # open, resolved
    resolution: Optional[str]


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="GenAI Governance Platform",
    description="Compliance-first governance layer for GenAI in financial services",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()

# Dependency for getting DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize modules with dependency injection for database sessions
# Note: Modules will use the session passed to them, with in-memory fallback
def get_modules(db: Session = Depends(get_db)):
    """Get initialized module instances with database session."""
    return {
        "prompt_registry": PromptRegistry(),
        "guardrail_engine": GuardrailEngine(db_session=db),
        "compliance_logger": ComplianceLogger(db_session=db),
        "model_evaluator": ModelEvaluator(db_session=db),
    }

# Global instances for routes that don't use DB (backward compatible)
prompt_registry = PromptRegistry()
guardrail_engine = GuardrailEngine()
compliance_logger = ComplianceLogger()
model_evaluator = ModelEvaluator()

# Populate with synthetic data for demo
def _init_synthetic_data():
    """Initialize with sample data for demonstration."""
    # This would normally be loaded from database
    # For demo purposes, uses in-memory data with counts
    pass

_init_synthetic_data()


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "GenAI Governance Platform",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Dashboard Endpoints
# ============================================================================

@app.get("/api/dashboard/overview", response_model=DashboardOverviewResponse, tags=["dashboard"])
async def get_dashboard_overview():
    """Get dashboard overview metrics."""
    summary = compliance_logger.get_dashboard_summary(days=30)
    guardrail_summary = guardrail_engine.get_summary()

    total = summary["total_interactions"]
    delivered = summary["delivered"]
    blocked = summary["blocked"]

    return DashboardOverviewResponse(
        total_interactions=total,
        delivered_pct=round((delivered / max(total, 1)) * 100, 1),
        blocked_pct=round((blocked / max(total, 1)) * 100, 1),
        pii_caught=summary["pii_detections"],
        pii_caught_pct=round((summary["pii_detections"] / max(total, 1)) * 100, 2),
        compliance_events=summary["compliance_events"],
        unresolved_events=summary["unresolved_events"],
        avg_guardrail_latency_ms=172,  # Synthetic
        models_in_production=2,  # Synthetic
        models_validated=2  # Synthetic
    )


@app.get("/api/dashboard/guardrails", response_model=List[GuardrailStatsResponse], tags=["dashboard"])
async def get_guardrail_stats():
    """Get guardrail performance statistics."""
    summary = guardrail_engine.get_summary()

    # Return synthetic guardrail stats
    return [
        GuardrailStatsResponse(
            check_name="pii_detection",
            pass_count=43418,
            warn_count=191,
            block_count=191,
            block_rate_pct=0.44
        ),
        GuardrailStatsResponse(
            check_name="hallucination_check",
            pass_count=42650,
            warn_count=612,
            block_count=538,
            block_rate_pct=1.23
        ),
        GuardrailStatsResponse(
            check_name="bias_screen",
            pass_count=43690,
            warn_count=98,
            block_count=12,
            block_rate_pct=0.03
        ),
        GuardrailStatsResponse(
            check_name="compliance_filter",
            pass_count=43612,
            warn_count=142,
            block_count=46,
            block_rate_pct=0.11
        ),
        GuardrailStatsResponse(
            check_name="confidence_assessment",
            pass_count=43348,
            warn_count=389,
            block_count=63,
            block_rate_pct=0.14
        ),
    ]


@app.get("/api/dashboard/models", response_model=List[ModelStatusResponse], tags=["dashboard"])
async def get_model_health():
    """Get model evaluation status."""
    eval_summary = model_evaluator.get_evaluation_summary()

    return [
        ModelStatusResponse(
            model_id="claude-3-sonnet-cust-svc",
            model_name="Member Service Copilot",
            use_case="Customer Service Response",
            risk_tier="Tier 2",
            validation_status="approved",
            last_eval_date="2026-02-28",
            next_eval_date="2026-05-28",
            latest_scores={
                "accuracy": 91.2,
                "groundedness": 96.4,
                "consistency": 85.1,
                "safety": 99.1,
                "bias": 97.3,
                "compliance": 99.2
            }
        ),
        ModelStatusResponse(
            model_id="claude-3-sonnet-loan-doc",
            model_name="Loan Document Summarizer",
            use_case="Document Summarization",
            risk_tier="Tier 3",
            validation_status="approved",
            last_eval_date="2026-02-15",
            next_eval_date="2026-05-15",
            latest_scores={
                "accuracy": 93.5,
                "groundedness": 97.8,
                "consistency": 89.7,
                "safety": 99.8,
                "bias": 99.4,
                "compliance": 99.6
            }
        ),
    ]


@app.get("/api/dashboard/events", response_model=List[ComplianceEventResponse], tags=["dashboard"])
async def get_compliance_events(
    days: int = Query(30, ge=1, le=365),
    unresolved_only: bool = False,
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0)
):
    """Get compliance events with pagination."""
    start_date = date.today()
    from datetime import timedelta
    start_date = start_date - timedelta(days=days)

    events = compliance_logger.query_events(
        start_date=start_date,
        unresolved_only=unresolved_only
    )

    paginated_events = events[offset:offset + limit]

    return [
        ComplianceEventResponse(
            event_id=event.event_id,
            interaction_id=event.interaction_id,
            event_type=event.event_type,
            severity=event.severity.value,
            description=event.description,
            timestamp=event.timestamp.isoformat(),
            status="resolved" if event.resolution else "open",
            resolution=event.resolution
        )
        for event in paginated_events
    ]


# ============================================================================
# Governance Endpoints
# ============================================================================

@app.post("/api/governance/check", response_model=GuardrailCheckResponse, tags=["governance"])
async def run_guardrail_check(request: GuardrailCheckRequest):
    """Submit output through guardrail pipeline."""
    try:
        # Run guardrails
        report = guardrail_engine.assess(
            output_text=request.output_text,
            input_context=request.input_context,
            template_id=request.template_id,
            version_id=request.version_id,
            model_id=request.model_id
        )

        # Log interaction
        log_entry = InteractionLog(
            interaction_id=report.interaction_id,
            timestamp=report.assessed_at,
            log_level=LogLevel.INFO if report.action == GuardrailAction.DELIVER else LogLevel.WARNING,
            use_case=request.template_id or "unknown",
            application_id="api",
            user_id="api-user",
            model_id=request.model_id,
            template_id=request.template_id,
            prompt_version=request.version_id,
            input_length=report.input_length,
            output_length=report.output_length,
            guardrail_action=report.action.value,
            guardrail_checks=[
                {
                    "check_name": check.check_name,
                    "result": check.result.value,
                    "confidence": check.confidence,
                    "findings_count": len(check.findings)
                }
                for check in report.checks
            ],
            final_action="delivered" if report.action == GuardrailAction.DELIVER else "blocked",
            customer_visible=(report.action == GuardrailAction.DELIVER)
        )
        compliance_logger.log_interaction(log_entry)

        return GuardrailCheckResponse(
            interaction_id=report.interaction_id,
            action=report.action.value,
            checks_passed=report.checks_passed,
            checks_warned=report.checks_warned,
            checks_blocked=report.checks_blocked,
            pii_detected=report.pii_detected,
            hallucination_detected=report.hallucination_detected,
            bias_detected=report.bias_detected,
            compliance_violation=report.compliance_violation,
            total_processing_time_ms=report.total_processing_time_ms,
            detailed_results={
                "checks": [
                    {
                        "name": check.check_name,
                        "result": check.result.value,
                        "details": check.details,
                        "findings": check.findings
                    }
                    for check in report.checks
                ],
                "block_reason": report.block_reason
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/governance/interactions", tags=["governance"])
async def query_interactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_case: Optional[str] = None,
    guardrail_action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0)
):
    """Query interaction logs with pagination."""
    from datetime import datetime
    start = datetime.fromisoformat(start_date).date() if start_date else None
    end = datetime.fromisoformat(end_date).date() if end_date else None

    logs = compliance_logger.query_interactions(
        start_date=start,
        end_date=end,
        use_case=use_case,
        guardrail_action=guardrail_action
    )

    total_count = len(logs)
    paginated_logs = logs[offset:offset + limit]

    return {
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "returned": len(paginated_logs),
        "has_more": (offset + limit) < total_count,
        "interactions": [
            {
                "interaction_id": log.interaction_id,
                "timestamp": log.timestamp.isoformat(),
                "use_case": log.use_case,
                "guardrail_action": log.guardrail_action,
                "final_action": log.final_action,
                "pii_detected": log.output_contains_pii,
                "customer_visible": log.customer_visible
            }
            for log in paginated_logs
        ]
    }


# ============================================================================
# Prompt Registry Endpoints
# ============================================================================

@app.get("/api/prompts/templates", tags=["prompts"])
async def list_prompt_templates(
    limit: int = Query(100, ge=1, le=10000),
    offset: int = Query(0, ge=0)
):
    """List all prompt templates with pagination."""
    templates = prompt_registry.list_templates()
    total_count = len(templates)
    paginated_templates = templates[offset:offset + limit]

    return {
        "total": total_count,
        "offset": offset,
        "limit": limit,
        "returned": len(paginated_templates),
        "has_more": (offset + limit) < total_count,
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "use_case": t.use_case.value if t.use_case else None,
                "risk_tier": t.risk_tier.value if t.risk_tier else None,
                "active_version": t.active_version.version if t.active_version else None,
                "total_versions": t.version_count,
                "approval_rate": t.approval_rate
            }
            for t in paginated_templates
        ]
    }


@app.get("/api/prompts/registry-summary", tags=["prompts"])
async def get_registry_summary():
    """Get prompt registry summary."""
    return prompt_registry.get_registry_summary()


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
