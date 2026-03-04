"""
Comprehensive test suite for prompt registry.

Tests for prompt versioning, approval workflow, variable injection,
PII tracking, and A/B testing.
"""

import pytest
from datetime import datetime, timedelta
from src.prompt_registry import (
    PromptRegistry, PromptTemplate, PromptVersion, PromptVariable,
    PromptStatus, UseCase, RiskTier, VariableType, ABTest
)


# ==============================================================================
# PROMPT VARIABLE TESTS
# ==============================================================================

class TestPromptVariable:
    """Test prompt variable validation and PII tracking."""

    def test_variable_creation_basic(self):
        """Create basic prompt variable."""
        var = PromptVariable(
            name="customer_name",
            variable_type=VariableType.PII,
            description="Member's full name",
            contains_pii=True,
            max_length=100
        )
        assert var.name == "customer_name"
        assert var.variable_type == VariableType.PII
        assert var.contains_pii is True

    def test_variable_with_validation_pattern(self):
        """Variable with regex validation pattern."""
        var = PromptVariable(
            name="account_number",
            variable_type=VariableType.ACCOUNT_DATA,
            description="Account number",
            validation_pattern=r'^[0-9]{10,17}$',
            max_length=17
        )
        assert var.validation_pattern is not None

    def test_variable_with_default_value(self):
        """Variable with optional default value."""
        var = PromptVariable(
            name="recent_transactions",
            variable_type=VariableType.FINANCIAL,
            description="Recent transactions",
            required=False,
            default_value="Not available"
        )
        assert var.required is False
        assert var.default_value == "Not available"

    def test_variable_pii_tracking(self):
        """PII variables properly tracked."""
        pii_var = PromptVariable(
            name="ssn",
            variable_type=VariableType.PII,
            description="Social Security Number",
            contains_pii=True
        )
        non_pii_var = PromptVariable(
            name="account_type",
            variable_type=VariableType.ACCOUNT_DATA,
            description="Account type",
            contains_pii=False
        )
        assert pii_var.contains_pii is True
        assert non_pii_var.contains_pii is False


# ==============================================================================
# PROMPT VERSION LIFECYCLE TESTS
# ==============================================================================

class TestPromptVersion:
    """Test prompt version creation and lifecycle."""

    def test_version_creation(self):
        """Create a prompt version."""
        version = PromptVersion(
            id="cust_svc_v1.0",
            template_id="cust_svc_response",
            version="1.0",
            created_at=datetime.now(),
            created_by="Alex Kim",
            status=PromptStatus.DRAFT,
            system_prompt="Be helpful and professional",
            user_prompt_template="Answer {{customer_message}}",
            variables=[
                PromptVariable("customer_message", VariableType.TEXT, "Customer's message")
            ],
            model_id="anthropic.claude-3-sonnet"
        )
        assert version.version == "1.0"
        assert version.status == PromptStatus.DRAFT
        assert version.is_deployable is False

    def test_version_immutability_hash(self):
        """Version content hash prevents tampering."""
        v1 = PromptVersion(
            id="test_v1",
            template_id="test",
            version="1.0",
            created_at=datetime.now(),
            created_by="Engineer",
            status=PromptStatus.DRAFT,
            system_prompt="Be helpful",
            user_prompt_template="Answer {{q}}",
            variables=[PromptVariable("q", VariableType.TEXT, "")],
            model_id="test-model"
        )
        hash1 = v1.content_hash
        assert hash1 is not None
        assert len(hash1) == 16  # SHA256 truncated to 16 chars

    def test_version_approval_workflow(self):
        """Version moves through approval states."""
        version = PromptVersion(
            id="test_v1",
            template_id="test",
            version="1.0",
            created_at=datetime.now(),
            created_by="Engineer",
            status=PromptStatus.DRAFT,
            system_prompt="Be helpful",
            user_prompt_template="Answer {{q}}",
            variables=[PromptVariable("q", VariableType.TEXT, "")],
            model_id="test-model"
        )
        assert version.status == PromptStatus.DRAFT

        # Submit for review
        version.status = PromptStatus.PENDING_REVIEW
        assert version.status == PromptStatus.PENDING_REVIEW
        assert version.is_deployable is False

        # Approve
        version.status = PromptStatus.APPROVED
        version.approved_by = "Maria Chen"
        version.approved_at = datetime.now()
        assert version.status == PromptStatus.APPROVED
        assert version.is_deployable is True

        # Deploy
        version.status = PromptStatus.DEPLOYED
        version.deployed_at = datetime.now()
        assert version.is_active is True

    def test_version_rejection(self):
        """Version can be rejected during review."""
        version = PromptVersion(
            id="test_v1",
            template_id="test",
            version="1.0",
            created_at=datetime.now(),
            created_by="Engineer",
            status=PromptStatus.PENDING_REVIEW,
            system_prompt="Be helpful",
            user_prompt_template="Answer {{q}}",
            variables=[PromptVariable("q", VariableType.TEXT, "")],
            model_id="test-model"
        )
        version.status = PromptStatus.REJECTED
        version.reviewer = "MRM Analyst"
        version.reviewed_at = datetime.now()
        version.review_notes = "Hallucination risk too high"
        assert version.status == PromptStatus.REJECTED


# ==============================================================================
# PROMPT TEMPLATE TESTS
# ==============================================================================

class TestPromptTemplate:
    """Test prompt template management."""

    def test_template_creation(self):
        """Create a prompt template."""
        template = PromptTemplate(
            id="cust_svc_response",
            name="Member Service Response",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Digital Transformation Team",
            created_at=datetime.now(),
            description="Generates draft responses to member inquiries"
        )
        assert template.id == "cust_svc_response"
        assert template.use_case == UseCase.CUSTOMER_SERVICE
        assert template.version_count == 0

    def test_template_version_tracking(self):
        """Template tracks all its versions."""
        template = PromptTemplate(
            id="test_template",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )

        v1 = PromptVersion(
            id="v1",
            template_id="test_template",
            version="1.0",
            created_at=datetime.now(),
            created_by="Engineer",
            status=PromptStatus.DRAFT,
            system_prompt="",
            user_prompt_template="",
            variables=[],
            model_id="test"
        )
        template.versions.append(v1)
        assert template.version_count == 1

        v2 = PromptVersion(
            id="v2",
            template_id="test_template",
            version="2.0",
            created_at=datetime.now() + timedelta(days=1),
            created_by="Engineer",
            status=PromptStatus.APPROVED,
            system_prompt="",
            user_prompt_template="",
            variables=[],
            model_id="test"
        )
        template.versions.append(v2)
        assert template.version_count == 2

    def test_template_active_version(self):
        """Template identifies active (deployed) version."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )

        v1 = PromptVersion(
            id="v1",
            template_id="test",
            version="1.0",
            created_at=datetime.now(),
            created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="",
            user_prompt_template="",
            variables=[],
            model_id="test"
        )
        template.versions.append(v1)
        assert template.active_version == v1

        # Retire v1, deploy v2
        v1.status = PromptStatus.DEPRECATED
        v2 = PromptVersion(
            id="v2",
            template_id="test",
            version="2.0",
            created_at=datetime.now() + timedelta(days=1),
            created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="",
            user_prompt_template="",
            variables=[],
            model_id="test"
        )
        template.versions.append(v2)
        assert template.active_version == v2

    def test_template_approval_rate(self):
        """Template calculates approval rate."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )

        # Draft version (not submitted)
        template.versions.append(PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DRAFT,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        ))
        # Approval rate should be 0% (draft not counted)
        assert template.approval_rate == 0.0

        # Add approved version
        template.versions.append(PromptVersion(
            id="v2", template_id="test", version="2.0",
            created_at=datetime.now() + timedelta(days=1), created_by="Eng",
            status=PromptStatus.APPROVED,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        ))
        # 1 of 1 submitted = 100%
        assert template.approval_rate == 100.0

        # Add rejected version
        template.versions.append(PromptVersion(
            id="v3", template_id="test", version="3.0",
            created_at=datetime.now() + timedelta(days=2), created_by="Eng",
            status=PromptStatus.REJECTED,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        ))
        # 1 approved, 1 rejected of 2 submitted = 50%
        assert template.approval_rate == 50.0


# ==============================================================================
# PROMPT REGISTRY TESTS
# ==============================================================================

class TestPromptRegistry:
    """Test prompt registry core functionality."""

    def setup_method(self):
        self.registry = PromptRegistry()

    def test_register_template(self):
        """Register a template in the registry."""
        template = PromptTemplate(
            id="cust_svc",
            name="Customer Service",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        registered = self.registry.register_template(template)
        assert registered.id == "cust_svc"
        assert self.registry.get_template("cust_svc") == template

    def test_register_duplicate_template_fails(self):
        """Cannot register same template ID twice."""
        template = PromptTemplate(
            id="cust_svc",
            name="Customer Service",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        with pytest.raises(ValueError, match="already registered"):
            self.registry.register_template(template)

    def test_create_version(self):
        """Create a version under a template."""
        template = PromptTemplate(
            id="cust_svc",
            name="Customer Service",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="cust_svc_v1.0",
            template_id="cust_svc",
            version="1.0",
            created_at=datetime.now(),
            created_by="Engineer",
            status=PromptStatus.DRAFT,
            system_prompt="Be helpful",
            user_prompt_template="Answer: {{question}}",
            variables=[PromptVariable("question", VariableType.TEXT, "User question")],
            model_id="claude-3-sonnet"
        )
        created = self.registry.create_version("cust_svc", version)
        assert created.version == "1.0"
        assert template.version_count == 1

    def test_create_duplicate_version_fails(self):
        """Cannot create duplicate version number."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        v1 = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DRAFT,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        )
        self.registry.create_version("test", v1)

        # Try to create another 1.0
        v1_dup = PromptVersion(
            id="v1_dup", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DRAFT,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        )
        with pytest.raises(ValueError, match="already exists"):
            self.registry.create_version("test", v1_dup)

    def test_variable_validation_in_template(self):
        """Variables in template must be declared."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        # Template has {{question}} but no variable declared
        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DRAFT,
            system_prompt="",
            user_prompt_template="Answer: {{question}}",
            variables=[],  # Missing question variable!
            model_id="test"
        )
        with pytest.raises(ValueError, match="undeclared variables"):
            self.registry.create_version("test", version)

    def test_approval_workflow(self):
        """Move version through approval states."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DRAFT,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        )
        self.registry.create_version("test", version)

        # Submit for review
        submitted = self.registry.submit_for_review("test", "v1")
        assert submitted.status == PromptStatus.PENDING_REVIEW

        # Approve
        approved = self.registry.approve_version(
            "test", "v1",
            approved_by="Maria Chen",
            notes="Looks good",
            evaluation_score=87.5,
            bias_test_passed=True
        )
        assert approved.status == PromptStatus.APPROVED
        assert approved.evaluation_score == 87.5
        assert approved.bias_test_passed is True

    def test_deployment(self):
        """Deploy an approved version."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.APPROVED,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        )
        self.registry.create_version("test", version)

        # Deploy
        deployed = self.registry.deploy_version("test", "v1", deployed_by="Alex Kim")
        assert deployed.status == PromptStatus.DEPLOYED
        assert deployed.deployed_by == "Alex Kim"
        assert template.active_version == deployed

    def test_deploy_approved_only(self):
        """Can only deploy approved versions."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DRAFT,  # Still draft!
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        )
        self.registry.create_version("test", version)

        with pytest.raises(ValueError, match="not deployable"):
            self.registry.deploy_version("test", "v1", deployed_by="Eng")


# ==============================================================================
# PROMPT RENDERING TESTS
# ==============================================================================

class TestPromptRendering:
    """Test prompt variable injection and rendering."""

    def setup_method(self):
        self.registry = PromptRegistry()

    def test_render_simple_prompt(self):
        """Render a simple prompt with variables."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="Be helpful",
            user_prompt_template="Answer: {{question}}",
            variables=[PromptVariable("question", VariableType.TEXT, "User question")],
            model_id="test-model"
        )
        self.registry.create_version("test", version)

        rendered = self.registry.render("test", {"question": "What's my balance?"})
        assert "What's my balance?" in rendered.user_prompt
        assert rendered.user_prompt == "Answer: What's my balance?"

    def test_render_with_pii_variables(self):
        """Render with PII variables tracked."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="",
            user_prompt_template="Member: {{name}}, Account: {{account}}",
            variables=[
                PromptVariable("name", VariableType.PII, "Name", contains_pii=True),
                PromptVariable("account", VariableType.ACCOUNT_DATA, "Account", contains_pii=True),
            ],
            model_id="test-model"
        )
        self.registry.create_version("test", version)

        rendered = self.registry.render("test", {
            "name": "John Doe",
            "account": "123456789"
        })
        assert rendered.pii_present is True
        assert "name" in rendered.pii_variables_used
        assert "account" in rendered.pii_variables_used
        # PII should be redacted in the summary
        assert "[PII" in rendered.variables_injected["name"]

    def test_render_validates_required_variables(self):
        """Rendering fails if required variables not provided."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="",
            user_prompt_template="Answer: {{question}}",
            variables=[PromptVariable("question", VariableType.TEXT, "Question", required=True)],
            model_id="test-model"
        )
        self.registry.create_version("test", version)

        with pytest.raises(ValueError, match="Required variable"):
            self.registry.render("test", {})  # Missing question

    def test_render_validates_max_length(self):
        """Rendering fails if variable exceeds max length."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="",
            user_prompt_template="Answer: {{question}}",
            variables=[PromptVariable("question", VariableType.TEXT, "Question", max_length=10)],
            model_id="test-model"
        )
        self.registry.create_version("test", version)

        with pytest.raises(ValueError, match="exceeds max length"):
            self.registry.render("test", {"question": "This is a very long question that exceeds the limit"})

    def test_render_validates_regex_pattern(self):
        """Rendering fails if variable doesn't match validation pattern."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="",
            user_prompt_template="Account: {{account}}",
            variables=[PromptVariable(
                "account", VariableType.ACCOUNT_DATA, "Account",
                validation_pattern=r'^\d{10}$'  # Must be 10 digits
            )],
            model_id="test-model"
        )
        self.registry.create_version("test", version)

        with pytest.raises(ValueError, match="fails validation"):
            self.registry.render("test", {"account": "ABC123"})  # Wrong format

    def test_render_uses_default_value(self):
        """Optional variables use default value if not provided."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        version = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="",
            user_prompt_template="Context: {{context}}",
            variables=[PromptVariable(
                "context", VariableType.ACCOUNT_DATA, "Context",
                required=False, default_value="No additional context"
            )],
            model_id="test-model"
        )
        self.registry.create_version("test", version)

        rendered = self.registry.render("test", {})
        assert "No additional context" in rendered.user_prompt


# ==============================================================================
# A/B TESTING TESTS
# ==============================================================================

class TestABTesting:
    """Test A/B testing functionality."""

    def setup_method(self):
        self.registry = PromptRegistry()

    def test_create_ab_test(self):
        """Create an A/B test between two versions."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        v_a = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        )
        v_b = PromptVersion(
            id="v2", template_id="test", version="2.0",
            created_at=datetime.now() + timedelta(days=1), created_by="Eng",
            status=PromptStatus.APPROVED,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        )
        self.registry.create_version("test", v_a)
        self.registry.create_version("test", v_b)

        test = ABTest(
            id="test_001",
            template_id="test",
            variant_a="v1",
            variant_b="v2",
            traffic_split=0.5,
            start_date=datetime.now(),
            approved_by="Maria Chen"
        )
        created = self.registry.create_ab_test(test)
        assert created.traffic_split == 0.5
        assert created.status == "active"

    def test_ab_test_traffic_split(self):
        """A/B test splits traffic according to configuration."""
        template = PromptTemplate(
            id="test",
            name="Test",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        self.registry.register_template(template)

        v_a = PromptVersion(
            id="v1", template_id="test", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="A", user_prompt_template="A",
            variables=[], model_id="test"
        )
        v_b = PromptVersion(
            id="v2", template_id="test", version="2.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.APPROVED,
            system_prompt="B", user_prompt_template="B",
            variables=[], model_id="test"
        )
        self.registry.create_version("test", v_a)
        self.registry.create_version("test", v_b)

        test = ABTest(
            id="test_001",
            template_id="test",
            variant_a="v1",
            variant_b="v2",
            traffic_split=0.3,  # 30% to variant B
            start_date=datetime.now()
        )
        self.registry.create_ab_test(test)

        # Render multiple times, should get split
        versions_seen = {"v1": 0, "v2": 0}
        for _ in range(100):
            rendered = self.registry.render("test", {})
            if rendered.system_prompt == "A":
                versions_seen["v1"] += 1
            else:
                versions_seen["v2"] += 1

        # Should be roughly 70/30 split (with variance)
        ratio_b = versions_seen["v2"] / 100
        assert 0.15 < ratio_b < 0.45  # Allow for variance around 30%


# ==============================================================================
# REGISTRY SUMMARY TESTS
# ==============================================================================

class TestRegistrySummary:
    """Test registry reporting and summary."""

    def test_registry_summary_empty(self):
        """Empty registry has zero metrics."""
        registry = PromptRegistry()
        summary = registry.get_registry_summary()
        assert summary["total_templates"] == 0
        assert summary["total_versions"] == 0

    def test_registry_summary_with_templates(self):
        """Registry summary includes template metrics."""
        registry = PromptRegistry()

        t1 = PromptTemplate(
            id="t1", name="T1",
            use_case=UseCase.CUSTOMER_SERVICE,
            risk_tier=RiskTier.TIER_2,
            owner="Team",
            created_at=datetime.now(),
            description="Test"
        )
        registry.register_template(t1)

        v1 = PromptVersion(
            id="v1", template_id="t1", version="1.0",
            created_at=datetime.now(), created_by="Eng",
            status=PromptStatus.DEPLOYED,
            system_prompt="", user_prompt_template="",
            variables=[], model_id="test"
        )
        registry.create_version("t1", v1)

        summary = registry.get_registry_summary()
        assert summary["total_templates"] == 1
        assert summary["total_versions"] == 1
        assert summary["active_deployments"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
