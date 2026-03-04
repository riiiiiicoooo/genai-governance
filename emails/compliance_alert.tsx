import React from "react";
import {
  Body,
  Button,
  Container,
  Head,
  Hr,
  Html,
  Img,
  Link,
  Preview,
  Row,
  Section,
  Text,
  Column,
} from "@react-email/components";

interface ComplianceAlertEmailProps {
  eventType: string;
  severity: "critical" | "warning" | "info";
  eventTitle: string;
  description: string;
  interactionDetails?: {
    interactionId: string;
    useCase: string;
    modelId: string;
    timestamp: string;
  };
  guardrailTriggered?: {
    checkType: string;
    reason: string;
    confidence: number;
  };
  recommendedAction: string;
  dashboardUrl: string;
  eventDetailsUrl: string;
}

const COLORS = {
  critical: "#dc3545",
  warning: "#ffc107",
  info: "#17a2b8",
};

const BACKGROUND_COLORS = {
  critical: "#f8d7da",
  warning: "#fff3cd",
  info: "#d1ecf1",
};

const baseUrl = process.env.VERCEL_URL
  ? `https://${process.env.VERCEL_URL}`
  : "http://localhost:3000";

export const COMPLIANCE_ALERT_EMAIL = ({
  eventType,
  severity,
  eventTitle,
  description,
  interactionDetails,
  guardrailTriggered,
  recommendedAction,
  dashboardUrl,
  eventDetailsUrl,
}: ComplianceAlertEmailProps) => {
  const borderColor = COLORS[severity];
  const backgroundColor = BACKGROUND_COLORS[severity];

  const severityIcon =
    severity === "critical"
      ? "🚨"
      : severity === "warning"
        ? "⚠️"
        : "ℹ️";

  const severityLabel =
    severity === "critical"
      ? "CRITICAL"
      : severity === "warning"
        ? "WARNING"
        : "INFO";

  return (
    <Html>
      <Head />
      <Preview>
        {severityIcon} {severityLabel}: {eventTitle}
      </Preview>
      <Body style={main}>
        <Container style={container}>
          {/* Header */}
          <Section style={{ ...header, borderLeft: `4px solid ${borderColor}` }}>
            <Row>
              <Column style={{ width: "60px" }}>
                <Text style={{ fontSize: "28px", margin: "0" }}>
                  {severityIcon}
                </Text>
              </Column>
              <Column>
                <Text style={headerTitle}>
                  {severityLabel} Compliance Event
                </Text>
                <Text style={headerSubtitle}>{eventTitle}</Text>
              </Column>
            </Row>
          </Section>

          {/* Main Alert Box */}
          <Section
            style={{
              backgroundColor,
              borderLeft: `4px solid ${borderColor}`,
              padding: "20px",
              marginTop: "20px",
              borderRadius: "4px",
            }}
          >
            <Text style={{ margin: "0 0 12px 0", fontSize: "14px" }}>
              <strong>Event Type:</strong> {eventType}
            </Text>
            <Text style={{ margin: "0 0 12px 0", fontSize: "14px" }}>
              <strong>Severity:</strong>{" "}
              <span
                style={{
                  backgroundColor: borderColor,
                  color: "white",
                  padding: "2px 6px",
                  borderRadius: "3px",
                  fontSize: "12px",
                  fontWeight: "bold",
                }}
              >
                {severityLabel}
              </span>
            </Text>
            <Text style={{ margin: "0", fontSize: "14px", lineHeight: "1.6" }}>
              {description}
            </Text>
          </Section>

          {/* Interaction Details (if available) */}
          {interactionDetails && (
            <Section style={detailsSection}>
              <Text style={sectionTitle}>Interaction Details</Text>
              <Row style={{ marginBottom: "8px" }}>
                <Column style={{ width: "30%" }}>
                  <Text style={detailLabel}>Interaction ID</Text>
                </Column>
                <Column>
                  <Text style={detailValue}>{interactionDetails.interactionId}</Text>
                </Column>
              </Row>
              <Row style={{ marginBottom: "8px" }}>
                <Column style={{ width: "30%" }}>
                  <Text style={detailLabel}>Use Case</Text>
                </Column>
                <Column>
                  <Text style={detailValue}>{interactionDetails.useCase}</Text>
                </Column>
              </Row>
              <Row style={{ marginBottom: "8px" }}>
                <Column style={{ width: "30%" }}>
                  <Text style={detailLabel}>Model</Text>
                </Column>
                <Column>
                  <Text style={detailValue}>{interactionDetails.modelId}</Text>
                </Column>
              </Row>
              <Row>
                <Column style={{ width: "30%" }}>
                  <Text style={detailLabel}>Timestamp</Text>
                </Column>
                <Column>
                  <Text style={detailValue}>
                    {new Date(interactionDetails.timestamp).toLocaleString()}
                  </Text>
                </Column>
              </Row>
            </Section>
          )}

          {/* Guardrail Details (if available) */}
          {guardrailTriggered && (
            <Section style={detailsSection}>
              <Text style={sectionTitle}>Guardrail Triggered</Text>
              <Row style={{ marginBottom: "8px" }}>
                <Column style={{ width: "30%" }}>
                  <Text style={detailLabel}>Check Type</Text>
                </Column>
                <Column>
                  <Text style={detailValue}>{guardrailTriggered.checkType}</Text>
                </Column>
              </Row>
              <Row style={{ marginBottom: "8px" }}>
                <Column style={{ width: "30%" }}>
                  <Text style={detailLabel}>Reason</Text>
                </Column>
                <Column>
                  <Text style={detailValue}>{guardrailTriggered.reason}</Text>
                </Column>
              </Row>
              <Row>
                <Column style={{ width: "30%" }}>
                  <Text style={detailLabel}>Confidence</Text>
                </Column>
                <Column>
                  <Text style={detailValue}>
                    {(guardrailTriggered.confidence * 100).toFixed(1)}%
                  </Text>
                </Column>
              </Row>
            </Section>
          )}

          {/* Recommended Action */}
          <Section style={detailsSection}>
            <Text style={sectionTitle}>Recommended Action</Text>
            <Text style={{ margin: "0", fontSize: "14px", lineHeight: "1.6" }}>
              {recommendedAction}
            </Text>
          </Section>

          {/* Action Buttons */}
          <Section style={{ marginTop: "20px", textAlign: "center" as const }}>
            <Button style={primaryButton} href={eventDetailsUrl}>
              View Full Details
            </Button>
            <Text style={{ margin: "16px 0 0 0" }}>
              <Link href={dashboardUrl} style={secondaryLink}>
                Go to Dashboard
              </Link>
            </Text>
          </Section>

          <Hr style={hr} />

          {/* Footer */}
          <Section style={footer}>
            <Text style={footerText}>
              This is an automated alert from the GenAI Governance Platform for
              a NCUA-regulated financial institution.
            </Text>
            <Text style={footerText}>
              Do not reply to this email. Log in to your governance dashboard
              to take action.
            </Text>
            <Text style={footerText}>
              Event severity: <strong>{severityLabel}</strong>
            </Text>
          </Section>
        </Container>
      </Body>
    </Html>
  );
};

// Default export for testing
export default COMPLIANCE_ALERT_EMAIL;

// ============================================================================
// Styles
// ============================================================================

const main = {
  backgroundColor: "#f5f5f5",
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
};

const container = {
  backgroundColor: "#ffffff",
  margin: "0 auto",
  padding: "20px 0",
  marginBottom: "64px",
};

const header = {
  backgroundColor: "#f8f9fa",
  padding: "20px",
  margin: "0",
  borderRadius: "4px 4px 0 0",
};

const headerTitle = {
  margin: "0",
  fontSize: "20px",
  fontWeight: "bold" as const,
  color: "#212529",
};

const headerSubtitle = {
  margin: "4px 0 0 0",
  fontSize: "16px",
  color: "#666",
};

const detailsSection = {
  padding: "20px",
  borderTop: "1px solid #e9ecef",
};

const sectionTitle = {
  margin: "0 0 16px 0",
  fontSize: "14px",
  fontWeight: "bold" as const,
  color: "#212529",
};

const detailLabel = {
  margin: "0",
  fontSize: "12px",
  fontWeight: "bold" as const,
  color: "#666",
};

const detailValue = {
  margin: "0",
  fontSize: "14px",
  color: "#212529",
  fontFamily: "monospace",
};

const primaryButton = {
  backgroundColor: "#667eea",
  borderRadius: "4px",
  color: "#fff",
  fontSize: "14px",
  fontWeight: "bold" as const,
  padding: "12px 24px",
  textDecoration: "none" as const,
  textAlign: "center" as const,
  display: "inline-block" as const,
};

const secondaryLink = {
  color: "#667eea",
  textDecoration: "underline",
  fontSize: "14px",
};

const hr = {
  borderColor: "#e9ecef",
  margin: "20px 0",
};

const footer = {
  padding: "20px",
  textAlign: "center" as const,
};

const footerText = {
  margin: "0 0 8px 0",
  color: "#666",
  fontSize: "12px",
  lineHeight: "1.5",
};
