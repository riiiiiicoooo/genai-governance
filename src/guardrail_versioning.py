"""
Guardrail Rule Versioning — Version control for guardrail configurations.

Guardrail patterns and thresholds change over time as we detect new PII formats,
discover false positive patterns, or tighten compliance standards. This module
provides version control for guardrail configurations.

Design:
- GuardrailRuleVersion wraps check configurations (patterns, thresholds, severity)
- Version history maintained for audit trail
- Compliance logger tracks which version was active per interaction
- Ability to roll back to previous versions
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, list as List
import hashlib
import json


class GuardrailVersionStatus(Enum):
    """Status of a guardrail rule version."""
    DRAFT = "draft"                 # Being designed, not yet active
    PENDING_REVIEW = "pending_review"   # Submitted for review
    APPROVED = "approved"           # Approved, ready to deploy
    ACTIVE = "active"               # Currently enforced
    SUPERSEDED = "superseded"       # Replaced by newer version
    ROLLED_BACK = "rolled_back"     # Reverted due to issues


@dataclass
class GuardrailPattern:
    """A single pattern within a guardrail check."""
    pattern_id: str                # e.g., "ssn_dash_format"
    pattern_type: str              # e.g., "pii_detection"
    regex_pattern: str             # The actual regex to match
    description: str               # Human-readable description
    severity: str                  # "pass", "warn", "block"
    false_positive_rate: float = 0.0  # Measured false positive rate
    true_positive_rate: float = 1.0   # Measured true positive rate (sensitivity)


@dataclass
class GuardrailThreshold:
    """A threshold used in a guardrail check."""
    check_name: str                # e.g., "hallucination_check"
    parameter_name: str            # e.g., "min_grounding_confidence"
    current_value: float           # Current threshold value
    previous_value: Optional[float] = None
    change_reason: str = ""


@dataclass
class GuardrailRuleVersion:
    """A single version of guardrail rules and thresholds.

    Wraps all configuration for guardrail checks at a point in time.
    Once deployed, immutable (new changes create new versions).
    """
    version_id: str                # e.g., "GRV-001"
    version_number: str            # e.g., "1.2.3" (semantic versioning)
    created_at: datetime
    created_by: str                # Engineer or analyst who created
    status: GuardrailVersionStatus

    # Content
    patterns: List[GuardrailPattern] = field(default_factory=list)
    thresholds: List[GuardrailThreshold] = field(default_factory=list)
    description: str = ""
    change_summary: str = ""       # What changed from previous version

    # Approval
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approval_notes: str = ""

    # Deployment
    deployed_at: Optional[datetime] = None
    deployed_by: Optional[str] = None
    superseded_by: Optional[str] = None  # Next version_id if replaced
    rolled_back_at: Optional[datetime] = None
    rollback_reason: str = ""

    # Metrics (measured in production)
    interactions_processed: int = 0
    false_positives_caught: int = 0
    false_negatives_caught: int = 0
    true_positives: int = 0
    effectiveness_score: Optional[float] = None

    # Integrity
    content_hash: str = ""

    def __post_init__(self):
        """Generate content hash for integrity."""
        if not self.content_hash:
            content = json.dumps({
                "version": self.version_number,
                "patterns": [
                    {
                        "id": p.pattern_id,
                        "regex": p.regex_pattern,
                        "severity": p.severity,
                    }
                    for p in self.patterns
                ],
                "thresholds": [
                    {
                        "check": t.check_name,
                        "param": t.parameter_name,
                        "value": t.current_value,
                    }
                    for t in self.thresholds
                ],
            }, sort_keys=True)
            self.content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    @property
    def is_active(self) -> bool:
        return self.status == GuardrailVersionStatus.ACTIVE

    @property
    def is_deployable(self) -> bool:
        return self.status == GuardrailVersionStatus.APPROVED

    @property
    def effectiveness_pct(self) -> float:
        """Calculate effectiveness: (TP + TN) / Total."""
        total = self.true_positives + self.false_positives_caught + self.false_negatives_caught
        if total == 0:
            return 0.0
        # True positives + correct rejects (estimated as interactions - false positives)
        correct = self.true_positives + max(0, self.interactions_processed - self.false_positives_caught)
        return (correct / self.interactions_processed * 100) if self.interactions_processed > 0 else 0.0


@dataclass
class GuardrailVersionChange:
    """Record of what changed between two versions."""
    from_version: str              # Previous version_id
    to_version: str                # New version_id
    changed_at: datetime
    approved_by: str

    patterns_added: List[str] = field(default_factory=list)
    patterns_removed: List[str] = field(default_factory=list)
    patterns_modified: dict = field(default_factory=dict)  # {pattern_id: (old_value, new_value)}
    thresholds_changed: dict = field(default_factory=dict)  # {param_name: (old_value, new_value)}

    description: str = ""
    deployment_impact: str = ""    # Expected effect on block rate, latency, etc.


class GuardrailVersionManager:
    """Manages guardrail rule versions and history."""

    def __init__(self):
        self._versions: dict[str, GuardrailRuleVersion] = {}
        self._active_version: Optional[str] = None
        self._version_history: list[GuardrailVersionChange] = []
        self._version_counter = 0

    def create_version(
        self,
        version_number: str,
        patterns: List[GuardrailPattern],
        thresholds: List[GuardrailThreshold],
        created_by: str,
        description: str = "",
        change_summary: str = "",
    ) -> GuardrailRuleVersion:
        """Create a new guardrail rule version."""
        self._version_counter += 1
        version_id = f"GRV-{self._version_counter:04d}"

        version = GuardrailRuleVersion(
            version_id=version_id,
            version_number=version_number,
            created_at=datetime.now(),
            created_by=created_by,
            status=GuardrailVersionStatus.DRAFT,
            patterns=patterns,
            thresholds=thresholds,
            description=description,
            change_summary=change_summary,
        )

        self._versions[version_id] = version
        return version

    def get_version(self, version_id: str) -> GuardrailRuleVersion:
        """Retrieve a specific version."""
        if version_id not in self._versions:
            raise KeyError(f"Version '{version_id}' not found")
        return self._versions[version_id]

    def get_active_version(self) -> Optional[GuardrailRuleVersion]:
        """Get the currently active version."""
        if not self._active_version:
            return None
        return self._versions.get(self._active_version)

    def submit_for_review(self, version_id: str) -> GuardrailRuleVersion:
        """Submit a draft version for review."""
        version = self.get_version(version_id)
        if version.status != GuardrailVersionStatus.DRAFT:
            raise ValueError(f"Only draft versions can be submitted. Current: {version.status.value}")
        version.status = GuardrailVersionStatus.PENDING_REVIEW
        return version

    def approve_version(
        self,
        version_id: str,
        approved_by: str,
        notes: str = "",
    ) -> GuardrailRuleVersion:
        """Approve a pending version."""
        version = self.get_version(version_id)
        if version.status != GuardrailVersionStatus.PENDING_REVIEW:
            raise ValueError(f"Only pending versions can be approved. Current: {version.status.value}")

        version.status = GuardrailVersionStatus.APPROVED
        version.approved_by = approved_by
        version.approved_at = datetime.now()
        version.approval_notes = notes
        return version

    def deploy_version(self, version_id: str, deployed_by: str) -> GuardrailRuleVersion:
        """Deploy an approved version (retire current active)."""
        version = self.get_version(version_id)
        if version.status != GuardrailVersionStatus.APPROVED:
            raise ValueError(f"Only approved versions can be deployed. Current: {version.status.value}")

        # Retire current active version
        if self._active_version:
            current = self._versions[self._active_version]
            if current.status == GuardrailVersionStatus.ACTIVE:
                current.status = GuardrailVersionStatus.SUPERSEDED
                current.superseded_by = version_id

        # Activate new version
        version.status = GuardrailVersionStatus.ACTIVE
        version.deployed_at = datetime.now()
        version.deployed_by = deployed_by
        self._active_version = version_id

        return version

    def rollback_version(
        self,
        version_id: str,
        rolled_back_by: str,
        reason: str,
        target_version: str,
    ) -> GuardrailRuleVersion:
        """Rollback to a previous version."""
        current = self.get_version(version_id)
        target = self.get_version(target_version)

        if current.status != GuardrailVersionStatus.ACTIVE:
            raise ValueError("Can only rollback from active version")
        if target.status not in (GuardrailVersionStatus.APPROVED, GuardrailVersionStatus.SUPERSEDED):
            raise ValueError("Target must be approved or superseded version")

        # Mark current as rolled back
        current.status = GuardrailVersionStatus.ROLLED_BACK
        current.rolled_back_at = datetime.now()
        current.rollback_reason = reason

        # Reactivate target
        target.status = GuardrailVersionStatus.ACTIVE
        target.superseded_by = None
        self._active_version = target_version

        # Record change
        self._version_history.append(GuardrailVersionChange(
            from_version=version_id,
            to_version=target_version,
            changed_at=datetime.now(),
            approved_by=rolled_back_by,
            description=f"Rollback: {reason}",
        ))

        return target

    def record_production_metrics(
        self,
        version_id: str,
        interactions: int,
        false_positives: int,
        false_negatives: int,
        true_positives: int,
    ) -> None:
        """Update production metrics for a version."""
        version = self.get_version(version_id)
        version.interactions_processed = interactions
        version.false_positives_caught = false_positives
        version.false_negatives_caught = false_negatives
        version.true_positives = true_positives

    def list_versions(self) -> list[GuardrailRuleVersion]:
        """List all versions."""
        return list(self._versions.values())

    def get_version_history(self) -> list[GuardrailVersionChange]:
        """Get version change history."""
        return self._version_history

    def get_summary(self) -> dict:
        """Summary of guardrail versioning."""
        versions = list(self._versions.values())
        active = self.get_active_version()

        return {
            "total_versions": len(versions),
            "active_version": active.version_id if active else None,
            "active_version_number": active.version_number if active else None,
            "draft_versions": len([v for v in versions if v.status == GuardrailVersionStatus.DRAFT]),
            "pending_review": len([v for v in versions if v.status == GuardrailVersionStatus.PENDING_REVIEW]),
            "approved_versions": len([v for v in versions if v.status == GuardrailVersionStatus.APPROVED]),
            "superseded_versions": len([v for v in versions if v.status == GuardrailVersionStatus.SUPERSEDED]),
            "rolled_back_versions": len([v for v in versions if v.status == GuardrailVersionStatus.ROLLED_BACK]),
            "total_pattern_count": sum(len(v.patterns) for v in versions),
            "total_thresholds": sum(len(v.thresholds) for v in versions),
        }


# ==============================================================================
# Usage Example
# ==============================================================================

if __name__ == "__main__":
    manager = GuardrailVersionManager()

    # Create v1 with initial patterns
    patterns_v1 = [
        GuardrailPattern(
            pattern_id="ssn_dash",
            pattern_type="pii_detection",
            regex_pattern=r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b',
            description="SSN in XXX-XX-XXXX format",
            severity="block",
            true_positive_rate=0.95,
            false_positive_rate=0.02,
        ),
        GuardrailPattern(
            pattern_id="credit_card",
            pattern_type="pii_detection",
            regex_pattern=r'\b(?:4\d{3}|5[1-5]\d{2})[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
            description="Credit card number",
            severity="block",
            true_positive_rate=0.98,
            false_positive_rate=0.01,
        ),
    ]

    v1 = manager.create_version(
        version_number="1.0.0",
        patterns=patterns_v1,
        thresholds=[],
        created_by="Alex Kim",
        description="Initial guardrail patterns",
        change_summary="Initial release with PII detection",
    )
    print(f"Created v1: {v1.version_id}")

    # Submit and approve
    manager.submit_for_review(v1.version_id)
    manager.approve_version(v1.version_id, approved_by="Maria Chen", notes="Looks good")
    manager.deploy_version(v1.version_id, deployed_by="Alex Kim")
    print(f"Deployed v1")

    # Create v2 with additional pattern (SSN without dashes)
    patterns_v2 = patterns_v1 + [
        GuardrailPattern(
            pattern_id="ssn_no_dashes",
            pattern_type="pii_detection",
            regex_pattern=r'\bSSN\d{9}\b',
            description="SSN in no-separator format",
            severity="block",
            true_positive_rate=0.92,
            false_positive_rate=0.03,
        ),
    ]

    v2 = manager.create_version(
        version_number="1.1.0",
        patterns=patterns_v2,
        thresholds=[],
        created_by="Alex Kim",
        description="Added SSN no-separator pattern",
        change_summary="Detected new SSN format in production (SSN123456789)",
    )
    manager.submit_for_review(v2.version_id)
    manager.approve_version(v2.version_id, approved_by="Maria Chen")
    manager.deploy_version(v2.version_id, deployed_by="Alex Kim")
    print(f"Deployed v2")

    # Simulate production metrics
    manager.record_production_metrics(
        v2.version_id,
        interactions=10000,
        false_positives=45,
        false_negatives=12,
        true_positives=145,
    )

    # Show summary
    summary = manager.get_summary()
    print("\n=== Guardrail Versioning Summary ===")
    print(f"Total versions: {summary['total_versions']}")
    print(f"Active: {summary['active_version_number']}")
    print(f"Total patterns: {summary['total_pattern_count']}")

    active = manager.get_active_version()
    if active:
        print(f"\nActive Version: {active.version_id}")
        print(f"Status: {active.status.value}")
        print(f"Patterns: {len(active.patterns)}")
        print(f"Deployed by: {active.deployed_by}")
