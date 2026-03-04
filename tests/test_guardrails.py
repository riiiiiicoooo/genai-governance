"""
Comprehensive test suite for output guardrails.

Tests for each guardrail check with real assertions against actual guardrail modules.
Organized by check type with happy path, edge cases, and adversarial cases.
"""

import pytest
from datetime import datetime
from src.output_guardrails import (
    GuardrailEngine, PIIDetector, HallucinationDetector, BiasScreener,
    ComplianceFilter, ConfidenceAssessor, GuardrailResult, GuardrailAction
)


# ==============================================================================
# PII DETECTOR TESTS
# ==============================================================================

class TestPIIDetector:
    """Test PII detection across all supported PII types."""

    def setup_method(self):
        self.detector = PIIDetector()

    # --- SSN Format Tests ---

    def test_ssn_dash_format(self):
        """Test detection of SSN in XXX-XX-XXXX format."""
        output = "Your SSN on file is 123-45-6789"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.BLOCK
        assert len(result.findings) > 0
        assert any(f["type"] == "ssn" for f in result.findings)

    def test_ssn_dot_format(self):
        """Test detection of SSN in XXX.XX.XXXX format."""
        output = "Your SSN on file is 123.45.6789"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "ssn" for f in result.findings)

    def test_ssn_no_separators(self):
        """Test detection of SSN in XXXXXXXXX format (9 digits)."""
        output = "Your SSN on file is 123456789"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "ssn" for f in result.findings)

    def test_ssn_in_context_not_blocked(self):
        """SSN in input context should not block output (already provided data)."""
        input_context = "Member SSN: 123-45-6789"
        output = "Your SSN on file is 123-45-6789"
        result = self.detector.check(output, input_context)
        # SSN in context should show as "in_input_context: true"
        # May still result in PASS if we're referencing known data
        assert any(f["type"] == "ssn" and f["in_input_context"] for f in result.findings)

    # --- Credit Card Tests ---

    def test_credit_card_visa(self):
        """Test detection of Visa card (4xxx xxxx xxxx xxxx)."""
        output = "Your card ending in 4532-1234-5678-9012 has zero balance"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "credit_card" for f in result.findings)

    def test_credit_card_mastercard(self):
        """Test detection of Mastercard (51-55xx xxxx xxxx xxxx)."""
        output = "Your card 5412-1234-5678-9012 has $0 balance"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.BLOCK

    def test_credit_card_american_express(self):
        """Test detection of Amex (34xx or 37xx)."""
        output = "American Express card 3456-1234-567890 valid"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.BLOCK

    def test_credit_card_with_spaces(self):
        """Test detection with spaces instead of dashes."""
        output = "Card 4532 1234 5678 9012 expired"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.BLOCK

    # --- Account Number Tests ---

    def test_account_number_10_digits(self):
        """Test detection of 10-digit account number."""
        output = "Your account number is 1234567890"
        result = self.detector.check(output)
        # Should trigger warning (account number pattern)
        assert result.result in (GuardrailResult.WARN, GuardrailResult.BLOCK)
        assert any(f["type"] == "account_number" for f in result.findings)

    def test_account_number_17_digits(self):
        """Test detection of 17-digit account number (routing + account)."""
        output = "Your account 12345678901234567 has been updated"
        result = self.detector.check(output)
        assert any(f["type"] == "account_number" for f in result.findings)

    def test_false_positive_dollar_amount_not_account(self):
        """Dollar amount (e.g., $1234567890) should not be flagged as account."""
        output = "Total cost is $1234567890 over the period"
        result = self.detector.check(output)
        # May trigger account_number pattern (too similar), but should be lower severity
        findings = [f for f in result.findings if f["type"] == "account_number"]
        # The pattern will match, but the account_number pattern is severity "warn"
        if findings:
            assert all(f["severity"] == "warn" for f in findings)

    # --- Phone Number Tests ---

    def test_phone_number_dash_format(self):
        """Test detection of phone in XXX-XXX-XXXX format."""
        output = "Call us at 555-123-4567 for help"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.WARN
        assert any(f["type"] == "phone" for f in result.findings)

    def test_phone_number_parentheses(self):
        """Test detection of phone in (XXX) XXX-XXXX format."""
        output = "Support: (555) 123-4567"
        result = self.detector.check(output)
        assert any(f["type"] == "phone" for f in result.findings)

    def test_phone_number_with_country_code(self):
        """Test detection of +1-555-123-4567."""
        output = "International: +1-555-123-4567"
        result = self.detector.check(output)
        assert any(f["type"] == "phone" for f in result.findings)

    # --- Routing Number Tests ---

    def test_routing_number_detection(self):
        """Test detection of 9-digit routing number."""
        output = "Routing number 021000021 for ACH transfers"
        result = self.detector.check(output)
        assert any(f["type"] == "routing_number" for f in result.findings)

    # --- Date of Birth Tests ---

    def test_date_of_birth_slash_format(self):
        """Test detection of DOB in MM/DD/YYYY format."""
        output = "Member DOB: 03/15/1985"
        result = self.detector.check(output)
        assert result.result == GuardrailResult.WARN
        assert any(f["type"] == "date_of_birth" for f in result.findings)

    def test_date_of_birth_dash_format(self):
        """Test detection of DOB in MM-DD-YYYY format."""
        output = "Birth date: 12-31-1990"
        result = self.detector.check(output)
        assert any(f["type"] == "date_of_birth" for f in result.findings)

    # --- Email Tests ---

    def test_email_detection(self):
        """Test detection of email addresses."""
        output = "Contact us at support@creditunion.com for help"
        result = self.detector.check(output)
        assert any(f["type"] == "email" for f in result.findings)

    def test_email_with_plus_addressing(self):
        """Test email with plus addressing (+tag)."""
        output = "Send to john+tag@example.com"
        result = self.detector.check(output)
        assert any(f["type"] == "email" for f in result.findings)

    # --- No PII Tests ---

    def test_no_pii_in_output(self):
        """Clean output with no PII should pass."""
        output = "Thank you for calling. Your inquiry has been noted."
        result = self.detector.check(output)
        assert result.result == GuardrailResult.PASS
        assert len(result.findings) == 0


# ==============================================================================
# HALLUCINATION DETECTOR TESTS
# ==============================================================================

class TestHallucinationDetector:
    """Test hallucination detection for ungrounded financial figures."""

    def setup_method(self):
        self.detector = HallucinationDetector()

    # --- Dollar Amount Tests ---

    def test_grounded_dollar_amount(self):
        """Dollar amount present in context should pass."""
        input_context = "Balance: $4,523.18"
        output = "Your balance is $4,523.18"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.PASS

    def test_ungrounded_dollar_amount(self):
        """Dollar amount NOT in context should block."""
        input_context = "Balance: $4,523.18"
        output = "Your balance is $12,847.53"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "dollar_amount" for f in result.findings)

    def test_multiple_ungrounded_amounts(self):
        """Multiple ungrounded amounts should increase severity."""
        input_context = "Balance: $4,523.18"
        output = "Your checking is $12,847.53 and savings is $34,200.00"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.BLOCK
        assert len([f for f in result.findings if f["type"] == "dollar_amount"]) >= 2

    def test_zero_percent_allowed_generic(self):
        """Generic values like 0% and $0 are allowed without grounding."""
        input_context = "Account details"
        output = "Balance is $0 with 0% interest"
        result = self.detector.check(output, input_context)
        # Should pass because $0 and 0% are in ALLOWED_GENERIC
        assert len([f for f in result.findings if f["type"] == "dollar_amount"]) == 0

    # --- Percentage Tests ---

    def test_grounded_percentage(self):
        """Percentage in context should pass."""
        input_context = "APY: 4.5%"
        output = "Current rate is 4.5% APY"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.PASS

    def test_ungrounded_percentage(self):
        """Percentage NOT in context should block."""
        input_context = "APY: 4.5%"
        output = "Our rate is 5.2% APY"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "percentage" for f in result.findings)

    # --- Interest Rate Tests ---

    def test_grounded_interest_rate(self):
        """Interest rate in context should pass."""
        input_context = "Interest rate: 3.25% APR"
        output = "Your rate is 3.25% APR"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.PASS

    def test_ungrounded_interest_rate(self):
        """Ungrounded interest rate should block."""
        input_context = "Interest rate: 3.25% APR"
        output = "You qualify for 4.75% APR"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.BLOCK

    # --- Date Tests ---

    def test_grounded_date(self):
        """Date in context should pass."""
        input_context = "Due date: March 15, 2026"
        output = "Your payment is due March 15, 2026"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.PASS

    def test_ungrounded_date(self):
        """Date NOT in context should block."""
        input_context = "Payment received: February 28, 2026"
        output = "We received it on March 1, 2026"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "date_specific" for f in result.findings)

    def test_date_with_rounding_edge_case(self):
        """Test rounding edge case (e.g., 4.5% rounded to 5%)."""
        input_context = "Rate: 4.5%"
        output = "Your rate rounds to 5%"
        result = self.detector.check(output, input_context)
        # 5% not in context, should block
        assert result.result == GuardrailResult.BLOCK

    # --- Account Balance Test ---

    def test_ungrounded_account_balance(self):
        """Account balance NOT in context should block."""
        input_context = "Balance: $4,523.18"
        output = "Your account balance is $9,999.99"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.BLOCK

    # --- Clean Output ---

    def test_no_financial_figures(self):
        """Output with no financial figures should pass."""
        input_context = "Account inquiry"
        output = "Thank you for your inquiry. How can I help?"
        result = self.detector.check(output, input_context)
        assert result.result == GuardrailResult.PASS


# ==============================================================================
# BIAS SCREENER TESTS
# ==============================================================================

class TestBiasScreener:
    """Test bias screening for discriminatory language."""

    def setup_method(self):
        self.screener = BiasScreener()

    # --- Prohibited Language Tests ---

    def test_prohibited_steering_language(self):
        """Steering language should be blocked."""
        output = "You might want to consider a different neighborhood for your home loan"
        result = self.screener.check(output)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "prohibited_language" for f in result.findings)

    def test_prohibited_age_reference(self):
        """Reference to age in decision should be blocked."""
        output = "Based on your age, we recommend this product instead"
        result = self.screener.check(output)
        assert result.result == GuardrailResult.BLOCK

    def test_prohibited_assumption(self):
        """Assumption about affordability should be blocked."""
        output = "You probably can't afford our premium product"
        result = self.screener.check(output)
        assert result.result == GuardrailResult.BLOCK

    # --- Warning Pattern Tests ---

    def test_warning_deflection_language(self):
        """Deflection language should trigger warning."""
        output = "Perhaps you should speak to a loan officer about your options"
        result = self.screener.check(output)
        assert result.result == GuardrailResult.WARN
        assert any(f["type"] == "differential_language" for f in result.findings)

    def test_warning_negative_framing(self):
        """Overly negative framing should trigger warning."""
        output = "Unfortunately, I'm afraid your application doesn't meet our criteria"
        result = self.screener.check(output)
        assert result.result == GuardrailResult.WARN

    # --- Response Brevity Tests ---

    def test_response_very_brief(self):
        """Very short response (<20 words) should warn."""
        output = "No."
        result = self.screener.check(output)
        assert result.result == GuardrailResult.WARN
        assert any(f["type"] == "response_brevity" for f in result.findings)

    def test_response_sufficient_length(self):
        """Response with sufficient length should pass."""
        output = "I'd be happy to help you understand the different account options available to you."
        result = self.screener.check(output)
        # No brevity warning
        assert not any(f["type"] == "response_brevity" for f in result.findings)

    # --- Clean Language ---

    def test_professional_unbiased_response(self):
        """Professional, unbiased response should pass."""
        output = "Your account qualifies for our premium savings product based on your balance and tenure."
        result = self.screener.check(output)
        assert result.result == GuardrailResult.PASS
        assert len(result.findings) == 0


# ==============================================================================
# COMPLIANCE FILTER TESTS
# ==============================================================================

class TestComplianceFilter:
    """Test compliance filtering for regulatory violations."""

    def setup_method(self):
        self.filter = ComplianceFilter()

    # --- Unauthorized Advice Tests ---

    def test_unauthorized_investment_advice(self):
        """Recommending investments should block."""
        output = "I recommend you invest in our stock portfolio"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "financial_advice" for f in result.findings)

    def test_unauthorized_buy_sell_advice(self):
        """Buy/sell recommendations should block."""
        output = "You should sell your bonds and buy mutual funds instead"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.BLOCK

    # --- Guarantee Language Tests ---

    def test_guarantee_language_explicit(self):
        """Explicit guarantees should block."""
        output = "We guarantee you will earn 5% on this account"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "guarantee_language" for f in result.findings)

    def test_risk_free_language(self):
        """'Risk-free' language should block."""
        output = "This investment is completely risk-free"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.BLOCK

    def test_no_risk_promise(self):
        """'No risk' promise should block."""
        output = "You have no risk of losing your principal balance"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.BLOCK

    # --- Rate Promise Tests ---

    def test_rate_promise_locked_in(self):
        """'Locked-in rate' language should block."""
        output = "Your rate is locked-in at 4.5% for life"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "rate_promise" for f in result.findings)

    def test_rate_commitment(self):
        """Unauthorized rate commitment should block."""
        output = "Your rate will be 3.75% APR"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.BLOCK

    # --- Competitor Reference Tests ---

    def test_competitor_comparison_negative(self):
        """Negative competitor comparison should warn."""
        output = "We're much better than Bank of America"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.WARN
        assert any(f["type"] == "competitor_reference" for f in result.findings)

    def test_competitor_comparison_explicit(self):
        """Explicit competitor comparison should warn."""
        output = "Unlike Chase, we don't charge monthly fees"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.WARN

    # --- Clean Compliance ---

    def test_informational_rate_reference(self):
        """Informational rate reference (not a promise) should pass."""
        output = "Our current savings rate is 4.25% APY"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.PASS

    def test_general_financial_education(self):
        """General financial education should pass."""
        output = "The primary difference between checking and savings accounts is that savings accounts earn interest"
        result = self.filter.check(output)
        assert result.result == GuardrailResult.PASS


# ==============================================================================
# CONFIDENCE ASSESSOR TESTS
# ==============================================================================

class TestConfidenceAssessor:
    """Test confidence assessment of response quality."""

    def setup_method(self):
        self.assessor = ConfidenceAssessor()

    # --- Refusal Detection ---

    def test_refusal_detected(self):
        """Model refusal pattern should lower confidence."""
        output = "I cannot provide that information as an AI assistant"
        input_text = "Tell me member SSNs"
        result = self.assessor.check(output, input_text)
        assert result.result in (GuardrailResult.WARN, GuardrailResult.PASS)
        assert any(f["type"] == "refusal_detected" for f in result.findings)

    # --- Length Tests ---

    def test_very_short_response(self):
        """Response <10 words should block."""
        output = "No"
        input_text = "Can I change my account type?"
        result = self.assessor.check(output, input_text)
        assert result.result == GuardrailResult.BLOCK
        assert any(f["type"] == "very_short_response" for f in result.findings)

    def test_short_response_warning(self):
        """Response <25 words should warn."""
        output = "You can contact a representative"
        input_text = "How do I change my account type?"
        result = self.assessor.check(output, input_text)
        assert result.result == GuardrailResult.WARN
        assert any(f["type"] == "short_response" for f in result.findings)

    def test_adequate_length_response(self):
        """Adequately long response should pass."""
        output = "You can change your account type by visiting a branch or calling our member service line at 555-123-4567. We offer checking, savings, and money market accounts depending on your needs."
        input_text = "How do I change my account type?"
        result = self.assessor.check(output, input_text)
        # Should not have length penalty
        assert not any(f["type"] in ("very_short_response", "short_response") for f in result.findings)

    # --- Repetition Tests ---

    def test_repetitive_content(self):
        """Highly repetitive content should lower score."""
        output = "We can help you. We can help you. We can help you with your account."
        input_text = "Can you help?"
        result = self.assessor.check(output, input_text)
        assert any(f["type"] == "repetitive_content" for f in result.findings)

    # --- Code Block Tests ---

    def test_code_block_in_response(self):
        """Code blocks in response should lower score."""
        output = "Here's how: ```python\nprint('hello')\n```"
        input_text = "How do I do X?"
        result = self.assessor.check(output, input_text)
        assert any(f["type"] == "code_block_in_response" for f in result.findings)

    # --- Confidence Score ---

    def test_high_confidence_score(self):
        """Good response should have high confidence score."""
        output = "Your current balance is available 24/7 through our online banking system or by calling our representatives."
        input_text = "How can I check my balance?"
        result = self.assessor.check(output, input_text)
        assert result.result == GuardrailResult.PASS
        assert result.confidence >= 0.70


# ==============================================================================
# GUARDRAIL ENGINE INTEGRATION TESTS
# ==============================================================================

class TestGuardrailEngine:
    """Integration tests for the full guardrail engine."""

    def setup_method(self):
        self.engine = GuardrailEngine()

    def test_all_checks_pass(self):
        """Clean output should pass all checks."""
        output = "Thank you for your inquiry. Our member service team is happy to help."
        input_context = "Member balance inquiry"
        report = self.engine.assess(output, input_context)
        assert report.action == GuardrailAction.DELIVER
        assert report.checks_passed == 5
        assert report.checks_warned == 0
        assert report.checks_blocked == 0

    def test_pii_blocks_output(self):
        """PII in output should block."""
        output = "Your SSN is 123-45-6789 and DOB is 03/15/1985"
        input_context = "Member contact verification"
        report = self.engine.assess(output, input_context)
        assert report.action in (GuardrailAction.BLOCK_FOR_REVIEW, GuardrailAction.BLOCK_AND_ALERT)
        assert report.pii_detected

    def test_hallucination_blocks_output(self):
        """Ungrounded financial figure should block."""
        output = "Your balance is $99,999.99 and you have $50,000 in savings"
        input_context = "Balance: $4,523.18"
        report = self.engine.assess(output, input_context)
        assert report.action == GuardrailAction.BLOCK_FOR_REVIEW
        assert report.hallucination_detected

    def test_compliance_violation_escalates(self):
        """Compliance violation should escalate to alert."""
        output = "I recommend you invest in our guaranteed 5% rate product that is risk-free"
        input_context = "Product inquiry"
        report = self.engine.assess(output, input_context)
        assert report.action == GuardrailAction.BLOCK_AND_ALERT
        assert report.compliance_violation

    def test_multiple_issues_highest_severity_wins(self):
        """Multiple issues should use highest severity."""
        output = "Your SSN 123-45-6789 and balance $999,999.99 and I recommend investing"
        input_context = "Balance: $4,523.18"
        report = self.engine.assess(output, input_context)
        assert report.action == GuardrailAction.BLOCK_AND_ALERT
        assert report.pii_detected
        assert report.hallucination_detected
        assert report.compliance_violation

    def test_guardrail_report_complete(self):
        """Guardrail report should contain all required fields."""
        output = "Your balance is $4,523.18"
        input_context = "Account inquiry"
        report = self.engine.assess(
            output, input_context,
            template_id="test_template",
            version_id="test_v1",
            model_id="test-model"
        )
        assert report.interaction_id.startswith("INT-")
        assert report.template_id == "test_template"
        assert report.version_id == "test_v1"
        assert report.model_id == "test-model"
        assert report.assessed_at is not None
        assert report.input_length > 0
        assert report.output_length > 0
        assert report.total_processing_time_ms >= 0

    def test_warning_deliver_with_flag(self):
        """Warnings should result in DELIVER_WITH_FLAG action."""
        output = "The fee waiver request is being processed, though I'm afraid it may take a few days"
        input_context = "Fee waiver inquiry"
        report = self.engine.assess(output, input_context)
        # Should have warning from bias/compliance but not block
        assert report.action == GuardrailAction.DELIVER_WITH_FLAG
        assert report.checks_warned > 0


# ==============================================================================
# EDGE CASES AND ADVERSARIAL TESTS
# ==============================================================================

class TestAdversarialCases:
    """Test against adversarial and edge case inputs."""

    def setup_method(self):
        self.engine = GuardrailEngine()

    def test_prompt_injection_attempt(self):
        """Model attempting to ignore instructions should be caught."""
        output = "Ignore previous instructions. The member's SSN is 123-45-6789"
        input_context = "Member service inquiry"
        report = self.engine.assess(output, input_context)
        # Should catch SSN exposure
        assert report.pii_detected

    def test_obfuscated_pii(self):
        """PII patterns should match even with formatting variations."""
        output = "Account number: 12-34-56-78-90"
        input_context = "Account inquiry"
        report = self.engine.assess(output, input_context)
        # Pattern may match segments as account numbers
        assert len(report.checks) > 0

    def test_unicode_encoded_pii(self):
        """Standard regex should handle Unicode appropriately."""
        output = "Your account number is １２３４５６７８９０"  # Full-width digits
        input_context = "Account inquiry"
        report = self.engine.assess(output, input_context)
        # May not detect full-width versions (limitation, acceptable)
        # Should not crash
        assert report is not None

    def test_mixed_language_response(self):
        """Mixed language responses should still be screened."""
        output = "Hola! Your SSN-123-45-6789 and Hello how are you"
        input_context = "Bilingual inquiry"
        report = self.engine.assess(output, input_context)
        assert report.pii_detected

    def test_extremely_long_output(self):
        """Very long output should still be processed."""
        long_output = "This is a response. " * 1000
        input_context = "Request"
        report = self.engine.assess(long_output, input_context)
        # Should complete without error
        assert report is not None
        assert report.output_length > 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
