"""
Compliance Logger — Complete audit trail for every GenAI interaction.

The module that produced three reports in under an hour when the OCC
examiner asked for them.

Under SR 11-7, financial institutions must maintain records of model inputs, outputs,
and decisions. For GenAI, that means logging every prompt, every
response, every guardrail result, and every human review action.

Design principles:
- Append-only: logs are immutable once written (no edits, no deletes)
- Complete: every field needed for regulatory examination
- Queryable: can answer "show me all blocked outputs in Q3" instantly
- Retention-compliant: logs retained per the credit union's record retention policy
- PII-aware: raw PII is logged but encrypted at rest, redacted in exports

In production, this writes to S3 with Object Lock (WORM compliance).
For the demo, it uses in-memory storage with the same data model.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional
from collections import defaultdict
import json
import hashlib


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LogLevel(Enum):
    """Severity level for log entries."""
    INFO = "info"            # Normal operation
    WARNING = "warning"      # Guardrail warning, non-blocking
    ALERT = "alert"          # Guardrail block, compliance concern
    CRITICAL = "critical"    # PII exposure, compliance violation, system failure


class ReviewOutcome(Enum):
    """Outcome of human review for blocked outputs."""
    APPROVED = "approved"              # Output is OK, false positive
    EDITED = "edited"                  # Output was modified and then sent
    REJECTED = "rejected"              # Output was discarded
    ESCALATED = "escalated"            # Sent to compliance for review


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class InteractionLog:
    """Complete log of a single LLM interaction.

    This is the atomic unit of the audit trail. Every interaction
    with the LLM produces exactly one InteractionLog.
    """
    # Identity
    interaction_id: str
    timestamp: datetime
    log_level: LogLevel

    # Source
    use_case: str                  # "customer_service", "document_summarization"
    application_id: str            # Which app initiated the request
    user_id: str                   # Staff member who triggered it (not the member)
    session_id: Optional[str] = None  # For multi-turn conversations

    # Model configuration
    model_id: str = ""
    template_id: str = ""
    prompt_version: str = ""
    temperature: float = 0.0
    max_tokens: int = 0

    # Input (PII fields encrypted at rest)
    input_text_hash: str = ""      # SHA-256 of the full input (for deduplication)
    input_length: int = 0
    input_contains_pii: bool = False
    input_pii_types: list[str] = field(default_factory=list)  # ["ssn", "account_number"]

    # Output
    output_text_hash: str = ""
    output_length: int = 0
    output_contains_pii: bool = False
    output_pii_types: list[str] = field(default_factory=list)

    # Guardrail results
    guardrail_action: str = ""     # "deliver", "flag", "block", "alert"
    guardrail_checks: list[dict] = field(default_factory=list)
    # [{check_name, result, confidence, findings_count}]

    # Human review (if guardrails blocked)
    human_review_required: bool = False
    human_reviewer: Optional[str] = None
    human_review_timestamp: Optional[datetime] = None
    human_review_outcome: Optional[ReviewOutcome] = None
    human_review_notes: str = ""

    # Final disposition
    final_action: str = ""         # "delivered", "delivered_edited", "blocked", "escalated"
    customer_visible: bool = False  # Did the member ultimately see this output?

    # Performance
    model_latency_ms: float = 0.0
    guardrail_latency_ms: float = 0.0
    total_latency_ms: float = 0.0

    # Integrity
    log_hash: str = ""             # Hash of the complete log entry

    def __post_init__(self):
        if not self.log_hash:
            content = json.dumps({
                "id": self.interaction_id,
                "ts": self.timestamp.isoformat(),
                "model": self.model_id,
                "input_hash": self.input_text_hash,
                "output_hash": self.output_text_hash,
                "action": self.guardrail_action,
            }, sort_keys=True)
            self.log_hash = hashlib.sha256(content.encode()).hexdigest()


@dataclass
class ComplianceEvent:
    """A compliance-relevant event that requires documentation.

    Not every interaction generates a compliance event. These are
    triggered by guardrail blocks, policy violations, or manual flags.
    """
    event_id: str
    interaction_id: str            # Links to the InteractionLog
    timestamp: datetime
    event_type: str                # "guardrail_block", "pii_exposure", "compliance_violation", "bias_flag"
    severity: LogLevel
    description: str
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    escalated_to: Optional[str] = None  # "compliance_officer", "mrm_team", "legal"


@dataclass
class AuditReport:
    """Structured report for regulatory examination."""
    report_id: str
    generated_at: datetime
    generated_by: str
    report_type: str               # "interaction_summary", "guardrail_analysis", "compliance_events"
    period_start: date
    period_end: date

    # Summary statistics
    total_interactions: int = 0
    total_delivered: int = 0
    total_blocked: int = 0
    total_flagged: int = 0
    block_rate_pct: float = 0.0
    pii_exposure_count: int = 0
    compliance_events: int = 0
    human_reviews: int = 0

    # Details
    by_use_case: dict = field(default_factory=dict)
    by_model: dict = field(default_factory=dict)
    by_guardrail: dict = field(default_factory=dict)
    notable_events: list[dict] = field(default_factory=list)

    # Document
    document_text: str = ""


# ---------------------------------------------------------------------------
# Compliance Logger
# ---------------------------------------------------------------------------

class ComplianceLogger:
    """Append-only audit trail for GenAI interactions.

    Every method that writes a log entry returns it immediately.
    Nothing is buffered. Nothing is editable after write.
    """

    def __init__(self, retention_days: int = 2555):  # ~7 years default
        self._logs: list[InteractionLog] = []
        self._events: list[ComplianceEvent] = []
        self._retention_days = retention_days
        self._event_counter = 0

    # -- Logging ------------------------------------------------------------

    def log_interaction(self, log: InteractionLog) -> InteractionLog:
        """Write an interaction log. Immutable after write."""
        self._logs.append(log)

        # Auto-generate compliance events for notable interactions
        if log.guardrail_action in ("block", "alert"):
            self._create_event(
                log.interaction_id,
                "guardrail_block",
                LogLevel.ALERT if log.guardrail_action == "alert" else LogLevel.WARNING,
                f"Output blocked by guardrails. Action: {log.guardrail_action}. "
                f"Checks: {', '.join(c.get('check_name', '') for c in log.guardrail_checks if c.get('result') != 'pass')}",
            )

        if log.output_contains_pii:
            self._create_event(
                log.interaction_id,
                "pii_in_output",
                LogLevel.ALERT,
                f"PII detected in model output: {', '.join(log.output_pii_types)}",
            )

        return log

    def _create_event(
        self, interaction_id: str, event_type: str,
        severity: LogLevel, description: str,
    ) -> ComplianceEvent:
        self._event_counter += 1
        event = ComplianceEvent(
            event_id=f"EVT-{self._event_counter:06d}",
            interaction_id=interaction_id,
            timestamp=datetime.now(),
            event_type=event_type,
            severity=severity,
            description=description,
        )
        self._events.append(event)
        return event

    def resolve_event(
        self, event_id: str, resolution: str,
        resolved_by: str,
    ) -> ComplianceEvent:
        for event in self._events:
            if event.event_id == event_id:
                event.resolution = resolution
                event.resolved_by = resolved_by
                event.resolved_at = datetime.now()
                return event
        raise KeyError(f"Event '{event_id}' not found.")

    # -- Querying -----------------------------------------------------------

    def query_interactions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        use_case: Optional[str] = None,
        guardrail_action: Optional[str] = None,
        model_id: Optional[str] = None,
        customer_visible_only: bool = False,
    ) -> list[InteractionLog]:
        """Query interaction logs with filters."""
        results = self._logs

        if start_date:
            results = [r for r in results if r.timestamp.date() >= start_date]
        if end_date:
            results = [r for r in results if r.timestamp.date() <= end_date]
        if use_case:
            results = [r for r in results if r.use_case == use_case]
        if guardrail_action:
            results = [r for r in results if r.guardrail_action == guardrail_action]
        if model_id:
            results = [r for r in results if r.model_id == model_id]
        if customer_visible_only:
            results = [r for r in results if r.customer_visible]

        return results

    def query_events(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        event_type: Optional[str] = None,
        severity: Optional[LogLevel] = None,
        unresolved_only: bool = False,
    ) -> list[ComplianceEvent]:
        results = self._events

        if start_date:
            results = [r for r in results if r.timestamp.date() >= start_date]
        if end_date:
            results = [r for r in results if r.timestamp.date() <= end_date]
        if event_type:
            results = [r for r in results if r.event_type == event_type]
        if severity:
            results = [r for r in results if r.severity == severity]
        if unresolved_only:
            results = [r for r in results if r.resolution is None]

        return results

    # -- Reporting ----------------------------------------------------------

    def generate_audit_report(
        self,
        period_start: date,
        period_end: date,
        generated_by: str = "System",
    ) -> AuditReport:
        """Generate a regulatory-ready audit report."""
        logs = self.query_interactions(period_start, period_end)
        events = self.query_events(period_start, period_end)

        delivered = [l for l in logs if l.final_action in ("delivered", "delivered_edited")]
        blocked = [l for l in logs if l.final_action in ("blocked", "escalated")]
        flagged = [l for l in logs if l.guardrail_action == "flag"]

        # By use case
        by_use_case = defaultdict(lambda: {"total": 0, "delivered": 0, "blocked": 0})
        for log in logs:
            by_use_case[log.use_case]["total"] += 1
            if log.final_action in ("delivered", "delivered_edited"):
                by_use_case[log.use_case]["delivered"] += 1
            elif log.final_action in ("blocked", "escalated"):
                by_use_case[log.use_case]["blocked"] += 1

        # By model
        by_model = defaultdict(lambda: {"total": 0, "avg_latency_ms": 0})
        for log in logs:
            by_model[log.model_id]["total"] += 1

        # By guardrail
        by_guardrail = defaultdict(lambda: {"pass": 0, "warn": 0, "block": 0})
        for log in logs:
            for check in log.guardrail_checks:
                check_name = check.get("check_name", "unknown")
                result = check.get("result", "pass")
                by_guardrail[check_name][result] = by_guardrail[check_name].get(result, 0) + 1

        # Notable events
        notable = [
            {
                "event_id": e.event_id,
                "type": e.event_type,
                "severity": e.severity.value,
                "description": e.description,
                "resolved": e.resolution is not None,
            }
            for e in events
            if e.severity in (LogLevel.ALERT, LogLevel.CRITICAL)
        ]

        report = AuditReport(
            report_id=f"RPT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            generated_at=datetime.now(),
            generated_by=generated_by,
            report_type="interaction_summary",
            period_start=period_start,
            period_end=period_end,
            total_interactions=len(logs),
            total_delivered=len(delivered),
            total_blocked=len(blocked),
            total_flagged=len(flagged),
            block_rate_pct=round(len(blocked) / max(len(logs), 1) * 100, 2),
            pii_exposure_count=len([l for l in logs if l.output_contains_pii]),
            compliance_events=len(events),
            human_reviews=len([l for l in logs if l.human_review_required]),
            by_use_case=dict(by_use_case),
            by_model=dict(by_model),
            by_guardrail=dict(by_guardrail),
            notable_events=notable,
        )

        report.document_text = self._format_report(report)
        return report

    def _format_report(self, report: AuditReport) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("GENAI COMPLIANCE AUDIT REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Report ID:    {report.report_id}")
        lines.append(f"Generated:    {report.generated_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Generated By: {report.generated_by}")
        lines.append(f"Period:       {report.period_start} to {report.period_end}")

        lines.append(f"\n--- Summary ---")
        lines.append(f"Total interactions:    {report.total_interactions:,}")
        lines.append(f"Delivered:             {report.total_delivered:,}")
        lines.append(f"Blocked:               {report.total_blocked:,} ({report.block_rate_pct}%)")
        lines.append(f"Flagged for review:    {report.total_flagged:,}")
        lines.append(f"PII detections:        {report.pii_exposure_count:,}")
        lines.append(f"Compliance events:     {report.compliance_events:,}")
        lines.append(f"Human reviews:         {report.human_reviews:,}")

        if report.by_use_case:
            lines.append(f"\n--- By Use Case ---")
            for uc, stats in report.by_use_case.items():
                lines.append(f"  {uc}: {stats['total']:,} total, {stats['delivered']:,} delivered, {stats['blocked']:,} blocked")

        if report.by_guardrail:
            lines.append(f"\n--- By Guardrail Check ---")
            for check, results in report.by_guardrail.items():
                total = sum(results.values())
                block_count = results.get("block", 0)
                lines.append(f"  {check}: {total:,} checks, {block_count:,} blocks ({round(block_count/max(total,1)*100,1)}%)")

        if report.notable_events:
            lines.append(f"\n--- Notable Events ({len(report.notable_events)}) ---")
            for event in report.notable_events[:10]:
                resolved = "✓ Resolved" if event["resolved"] else "○ Open"
                lines.append(f"  [{event['severity'].upper()}] {event['type']}: {event['description'][:80]}")
                lines.append(f"    {resolved}")

        return "\n".join(lines)

    # -- Dashboard Summary --------------------------------------------------

    def get_dashboard_summary(self, days: int = 30) -> dict:
        """Summary for the governance dashboard."""
        cutoff = date.today() - timedelta(days=days)
        logs = self.query_interactions(start_date=cutoff)
        events = self.query_events(start_date=cutoff)

        total = len(logs)

        return {
            "period_days": days,
            "total_interactions": total,
            "delivered": len([l for l in logs if l.final_action in ("delivered", "delivered_edited")]),
            "blocked": len([l for l in logs if l.final_action in ("blocked", "escalated")]),
            "block_rate_pct": round(
                len([l for l in logs if l.final_action in ("blocked", "escalated")]) / max(total, 1) * 100, 2
            ),
            "pii_detections": len([l for l in logs if l.output_contains_pii]),
            "compliance_events": len(events),
            "unresolved_events": len([e for e in events if e.resolution is None]),
            "human_reviews_pending": len([l for l in logs if l.human_review_required and not l.human_review_outcome]),
        }


# ---------------------------------------------------------------------------
# Usage Example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger = ComplianceLogger()
    today = date.today()

    # Simulate a month of interactions
    interaction_scenarios = [
        # Clean interaction — delivered
        InteractionLog(
            interaction_id="INT-000001",
            timestamp=datetime.now() - timedelta(days=15, hours=3),
            log_level=LogLevel.INFO,
            use_case="customer_service",
            application_id="secure_messaging",
            user_id="agent_12",
            model_id="claude-3-sonnet",
            template_id="cust_svc_response",
            prompt_version="v3.1",
            input_length=342,
            input_contains_pii=True,
            input_pii_types=["customer_name", "account_number"],
            output_length=189,
            guardrail_action="deliver",
            guardrail_checks=[
                {"check_name": "pii_detection", "result": "pass", "confidence": 1.0, "findings_count": 0},
                {"check_name": "hallucination_check", "result": "pass", "confidence": 0.9, "findings_count": 0},
                {"check_name": "bias_screen", "result": "pass", "confidence": 0.85, "findings_count": 0},
                {"check_name": "compliance_filter", "result": "pass", "confidence": 0.95, "findings_count": 0},
                {"check_name": "confidence_assessment", "result": "pass", "confidence": 0.92, "findings_count": 0},
            ],
            final_action="delivered",
            customer_visible=True,
            model_latency_ms=1250,
            guardrail_latency_ms=178,
            total_latency_ms=1428,
        ),
        # Hallucination caught — blocked
        InteractionLog(
            interaction_id="INT-000002",
            timestamp=datetime.now() - timedelta(days=12, hours=7),
            log_level=LogLevel.WARNING,
            use_case="customer_service",
            application_id="secure_messaging",
            user_id="agent_08",
            model_id="claude-3-sonnet",
            template_id="cust_svc_response",
            prompt_version="v3.1",
            input_length=256,
            input_contains_pii=True,
            output_length=312,
            guardrail_action="block",
            guardrail_checks=[
                {"check_name": "pii_detection", "result": "pass", "confidence": 1.0, "findings_count": 0},
                {"check_name": "hallucination_check", "result": "block", "confidence": 0.78, "findings_count": 3},
                {"check_name": "bias_screen", "result": "pass", "confidence": 0.85, "findings_count": 0},
                {"check_name": "compliance_filter", "result": "pass", "confidence": 0.95, "findings_count": 0},
                {"check_name": "confidence_assessment", "result": "warn", "confidence": 0.62, "findings_count": 1},
            ],
            human_review_required=True,
            human_reviewer="supervisor_04",
            human_review_timestamp=datetime.now() - timedelta(days=12, hours=6),
            human_review_outcome=ReviewOutcome.REJECTED,
            human_review_notes="Model fabricated account balance not in context.",
            final_action="blocked",
            customer_visible=False,
            model_latency_ms=1100,
            guardrail_latency_ms=195,
            total_latency_ms=1295,
        ),
        # PII in output — alert
        InteractionLog(
            interaction_id="INT-000003",
            timestamp=datetime.now() - timedelta(days=8, hours=2),
            log_level=LogLevel.ALERT,
            use_case="customer_service",
            application_id="secure_messaging",
            user_id="agent_15",
            model_id="claude-3-sonnet",
            template_id="cust_svc_response",
            prompt_version="v3.1",
            input_length=445,
            input_contains_pii=True,
            output_length=267,
            output_contains_pii=True,
            output_pii_types=["account_number"],
            guardrail_action="alert",
            guardrail_checks=[
                {"check_name": "pii_detection", "result": "block", "confidence": 0.88, "findings_count": 1},
                {"check_name": "hallucination_check", "result": "pass", "confidence": 0.9, "findings_count": 0},
                {"check_name": "bias_screen", "result": "pass", "confidence": 0.85, "findings_count": 0},
                {"check_name": "compliance_filter", "result": "pass", "confidence": 0.95, "findings_count": 0},
                {"check_name": "confidence_assessment", "result": "pass", "confidence": 0.88, "findings_count": 0},
            ],
            human_review_required=True,
            human_reviewer="compliance_02",
            human_review_timestamp=datetime.now() - timedelta(days=8, hours=1),
            human_review_outcome=ReviewOutcome.ESCALATED,
            human_review_notes="Account number surfaced in output. Escalating to compliance.",
            final_action="escalated",
            customer_visible=False,
            model_latency_ms=980,
            guardrail_latency_ms=165,
            total_latency_ms=1145,
        ),
        # Document summarization — clean
        InteractionLog(
            interaction_id="INT-000004",
            timestamp=datetime.now() - timedelta(days=5),
            log_level=LogLevel.INFO,
            use_case="document_summarization",
            application_id="loan_processing",
            user_id="analyst_03",
            model_id="claude-3-sonnet",
            template_id="doc_summary",
            prompt_version="v1.2",
            input_length=8200,
            input_contains_pii=True,
            output_length=450,
            guardrail_action="deliver",
            guardrail_checks=[
                {"check_name": "pii_detection", "result": "pass", "confidence": 1.0, "findings_count": 0},
                {"check_name": "hallucination_check", "result": "pass", "confidence": 0.92, "findings_count": 0},
                {"check_name": "compliance_filter", "result": "pass", "confidence": 0.95, "findings_count": 0},
                {"check_name": "confidence_assessment", "result": "pass", "confidence": 0.94, "findings_count": 0},
            ],
            final_action="delivered",
            customer_visible=False,
            model_latency_ms=2800,
            guardrail_latency_ms=210,
            total_latency_ms=3010,
        ),
    ]

    for log in interaction_scenarios:
        logger.log_interaction(log)

    # Generate audit report
    report = logger.generate_audit_report(
        period_start=today - timedelta(days=30),
        period_end=today,
        generated_by="Maria Chen (MRM Analyst)",
    )

    print(report.document_text)

    # Dashboard summary
    print(f"\n{'=' * 60}")
    print("COMPLIANCE DASHBOARD")
    print(f"{'=' * 60}")
    summary = logger.get_dashboard_summary(30)
    print(f"Interactions (30d): {summary['total_interactions']}")
    print(f"Delivered: {summary['delivered']}")
    print(f"Blocked: {summary['blocked']} ({summary['block_rate_pct']}%)")
    print(f"PII detections: {summary['pii_detections']}")
    print(f"Compliance events: {summary['compliance_events']}")
    print(f"Unresolved: {summary['unresolved_events']}")
