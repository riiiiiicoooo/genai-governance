import React from "react";
import {
  Body,
  Button,
  Container,
  Head,
  Hr,
  Html,
  Link,
  Preview,
  Row,
  Section,
  Text,
  Column,
} from "@react-email/components";

interface DailyDigestEmailProps {
  date: string; // YYYY-MM-DD format
  summary: {
    totalInteractions: number;
    deliveredCount: number;
    blockedCount: number;
    warnedCount: number;
    blockRate: number; // percentage
    piiCaught: number;
    avgLatencyMs: number;
    totalCostUSD: number;
  };
  trends: {
    interactions: {
      direction: "up" | "down";
      changePercent: number;
    };
    blockRate: {
      direction: "up" | "down";
      changeDiff: number;
    };
  };
  unresolvedCritical: number;
  unresolvedWarnings: number;
  dashboardUrl: string;
}

const baseUrl = process.env.VERCEL_URL
  ? `https://${process.env.VERCEL_URL}`
  : "http://localhost:3000";

export const DAILY_DIGEST_EMAIL = ({
  date,
  summary,
  trends,
  unresolvedCritical,
  unresolvedWarnings,
  dashboardUrl,
}: DailyDigestEmailProps) => {
  const dateObj = new Date(date);
  const formattedDate = dateObj.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const trendColor = (direction: "up" | "down", isBad = false) => {
    if (isBad) {
      return direction === "up" ? "#dc3545" : "#28a745";
    } else {
      return direction === "up" ? "#28a745" : "#dc3545";
    }
  };

  return (
    <Html>
      <Head />
      <Preview>Daily Compliance Digest - {formattedDate}</Preview>
      <Body style={main}>
        <Container style={container}>
          {/* Header */}
          <Section style={header}>
            <Text style={headerTitle}>Daily Compliance Digest</Text>
            <Text style={headerSubtitle}>{formattedDate}</Text>
          </Section>

          {/* Executive Summary */}
          <Section style={contentSection}>
            <Text style={sectionTitle}>Interactions Processed</Text>
            <Row style={metricsRow}>
              <Column style={metricColumn}>
                <Text style={metricValue}>{summary.totalInteractions}</Text>
                <Text style={metricLabel}>Total</Text>
              </Column>
              <Column style={metricColumn}>
                <Text style={{ ...metricValue, color: "#28a745" }}>
                  {summary.deliveredCount}
                </Text>
                <Text style={metricLabel}>Delivered</Text>
              </Column>
              <Column style={metricColumn}>
                <Text style={{ ...metricValue, color: "#ffc107" }}>
                  {summary.warnedCount}
                </Text>
                <Text style={metricLabel}>Warned</Text>
              </Column>
              <Column style={metricColumn}>
                <Text style={{ ...metricValue, color: "#dc3545" }}>
                  {summary.blockedCount}
                </Text>
                <Text style={metricLabel}>Blocked</Text>
              </Column>
            </Row>
          </Section>

          {/* Key Metrics */}
          <Section style={contentSection}>
            <Text style={sectionTitle}>Key Performance Metrics</Text>

            <Row style={metricRow}>
              <Column style={{ width: "40%" }}>
                <Text style={metricName}>Block Rate</Text>
              </Column>
              <Column style={{ width: "60%", textAlign: "right" as const }}>
                <Text style={metricLargeValue}>{summary.blockRate}%</Text>
                <Text
                  style={{
                    ...metricTrend,
                    color: trendColor(trends.blockRate.direction, true),
                  }}
                >
                  {trends.blockRate.direction === "up" ? "↑" : "↓"}{" "}
                  {Math.abs(trends.blockRate.changeDiff).toFixed(2)}% vs. prior
                </Text>
              </Column>
            </Row>

            <Hr style={rowDivider} />

            <Row style={metricRow}>
              <Column style={{ width: "40%" }}>
                <Text style={metricName}>PII Instances Caught</Text>
              </Column>
              <Column style={{ width: "60%", textAlign: "right" as const }}>
                <Text style={metricLargeValue}>{summary.piiCaught}</Text>
                <Text style={metricNote}>Prevented from reaching members</Text>
              </Column>
            </Row>

            <Hr style={rowDivider} />

            <Row style={metricRow}>
              <Column style={{ width: "40%" }}>
                <Text style={metricName}>Avg Guardrail Latency</Text>
              </Column>
              <Column style={{ width: "60%", textAlign: "right" as const }}>
                <Text style={metricLargeValue}>{summary.avgLatencyMs}ms</Text>
                <Text style={metricNote}>Per interaction processing</Text>
              </Column>
            </Row>

            <Hr style={rowDivider} />

            <Row style={metricRow}>
              <Column style={{ width: "40%" }}>
                <Text style={metricName}>Total LLM Cost</Text>
              </Column>
              <Column style={{ width: "60%", textAlign: "right" as const }}>
                <Text style={metricLargeValue}>
                  ${summary.totalCostUSD.toFixed(2)}
                </Text>
                <Text style={metricNote}>All models combined</Text>
              </Column>
            </Row>
          </Section>

          {/* Trends */}
          <Section style={contentSection}>
            <Text style={sectionTitle}>Trends vs. Prior Period</Text>
            <Row style={trendBox}>
              <Text style={{ margin: "0", fontSize: "14px" }}>
                <strong>Interactions Processed:</strong>{" "}
                <span
                  style={{
                    color: trendColor(trends.interactions.direction, false),
                    fontWeight: "bold",
                  }}
                >
                  {trends.interactions.direction === "up" ? "↑" : "↓"}{" "}
                  {Math.abs(trends.interactions.changePercent).toFixed(1)}%
                </span>{" "}
                vs. previous day
              </Text>
            </Row>
          </Section>

          {/* Alerts - Unresolved Items */}
          {unresolvedCritical > 0 && (
            <Section
              style={{
                ...contentSection,
                backgroundColor: "#f8d7da",
                borderLeft: "4px solid #dc3545",
              }}
            >
              <Text style={{ margin: "0 0 8px 0", fontSize: "14px" }}>
                <strong style={{ color: "#721c24" }}>
                  ⚠️ ATTENTION REQUIRED
                </strong>
              </Text>
              <Text style={{ margin: "0", fontSize: "14px", color: "#721c24" }}>
                <strong>{unresolvedCritical}</strong> unresolved critical
                compliance event{unresolvedCritical === 1 ? "" : "s"} require
                immediate review.
              </Text>
            </Section>
          )}

          {unresolvedWarnings > 0 && !unresolvedCritical && (
            <Section
              style={{
                ...contentSection,
                backgroundColor: "#fff3cd",
                borderLeft: "4px solid #ffc107",
              }}
            >
              <Text style={{ margin: "0 0 8px 0", fontSize: "14px" }}>
                <strong style={{ color: "#856404" }}>📋 Open Items</strong>
              </Text>
              <Text style={{ margin: "0", fontSize: "14px", color: "#856404" }}>
                <strong>{unresolvedWarnings}</strong> warning event
                {unresolvedWarnings === 1 ? "" : "s"} in queue for your review.
              </Text>
            </Section>
          )}

          {unresolvedCritical === 0 && unresolvedWarnings === 0 && (
            <Section
              style={{
                ...contentSection,
                backgroundColor: "#d4edda",
                borderLeft: "4px solid #28a745",
              }}
            >
              <Text style={{ margin: "0", fontSize: "14px", color: "#155724" }}>
                ✓ All compliance events resolved. No open items.
              </Text>
            </Section>
          )}

          {/* Quick Facts */}
          <Section style={contentSection}>
            <Text style={sectionTitle}>Quick Facts</Text>
            <ul style={factsList}>
              <li style={factsItem}>
                Block rate of {summary.blockRate}% indicates{" "}
                {summary.blockRate > 5
                  ? "elevated"
                  : summary.blockRate > 2
                    ? "healthy"
                    : "very low"}{" "}
                guardrail activity
              </li>
              <li style={factsItem}>
                {summary.piiCaught} PII instances prevented from reaching
                members
              </li>
              <li style={factsItem}>
                Guardrails processing in {summary.avgLatencyMs}ms — acceptable
                for real-time operation
              </li>
              <li style={factsItem}>
                Cost tracking integrated: ${summary.totalCostUSD.toFixed(2)} in LLM expenses
              </li>
            </ul>
          </Section>

          {/* Call to Action */}
          <Section style={{ textAlign: "center" as const, marginTop: "20px" }}>
            <Button style={primaryButton} href={dashboardUrl}>
              View Full Dashboard
            </Button>
          </Section>

          <Hr style={hr} />

          {/* Guidance */}
          <Section style={contentSection}>
            <Text style={guidanceTitle}>Recommended Actions</Text>
            <ol style={guidanceList}>
              <li style={guidanceItem}>
                Review any{" "}
                {unresolvedCritical > 0
                  ? "critical events in PagerDuty"
                  : "open compliance events"}{" "}
                for immediate remediation
              </li>
              <li style={guidanceItem}>
                Monitor trend data — significant changes may indicate model drift
              </li>
              <li style={guidanceItem}>
                Compare block rate against historical baseline — sustained changes
                warrant investigation
              </li>
              {summary.piiCaught > 5 && (
                <li style={guidanceItem}>
                  High PII catch count: review guardrail sensitivity settings
                </li>
              )}
            </ol>
          </Section>

          <Hr style={hr} />

          {/* Footer */}
          <Section style={footer}>
            <Text style={footerText}>
              This is a daily automated report from the GenAI Governance Platform.
            </Text>
            <Text style={footerText}>
              For support or questions, contact your compliance team.
            </Text>
            <Text style={footerSmall}>
              Report generated: {new Date().toLocaleString()}
            </Text>
          </Section>
        </Container>
      </Body>
    </Html>
  );
};

// Default export for testing
export default DAILY_DIGEST_EMAIL;

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
  padding: "0",
  marginBottom: "64px",
};

const header = {
  backgroundColor: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  padding: "40px 20px",
  textAlign: "center" as const,
  color: "white",
};

const headerTitle = {
  margin: "0",
  fontSize: "28px",
  fontWeight: "bold" as const,
  color: "white",
};

const headerSubtitle = {
  margin: "8px 0 0 0",
  fontSize: "16px",
  color: "rgba(255,255,255,0.9)",
};

const contentSection = {
  padding: "20px",
  borderBottom: "1px solid #e9ecef",
};

const sectionTitle = {
  margin: "0 0 16px 0",
  fontSize: "16px",
  fontWeight: "bold" as const,
  color: "#212529",
};

const metricsRow = {
  margin: "0",
};

const metricColumn = {
  width: "25%",
  padding: "12px",
  backgroundColor: "#f8f9fa",
  borderRadius: "4px",
  textAlign: "center" as const,
  marginRight: "8px",
};

const metricValue = {
  margin: "0",
  fontSize: "24px",
  fontWeight: "bold" as const,
  color: "#667eea",
};

const metricLabel = {
  margin: "4px 0 0 0",
  fontSize: "12px",
  color: "#666",
};

const metricRow = {
  margin: "16px 0",
  padding: "0",
};

const metricName = {
  margin: "0",
  fontSize: "14px",
  fontWeight: "bold" as const,
  color: "#212529",
};

const metricLargeValue = {
  margin: "0",
  fontSize: "28px",
  fontWeight: "bold" as const,
  color: "#667eea",
};

const metricTrend = {
  margin: "4px 0 0 0",
  fontSize: "12px",
  fontWeight: "bold" as const,
};

const metricNote = {
  margin: "4px 0 0 0",
  fontSize: "12px",
  color: "#666",
};

const rowDivider = {
  borderColor: "#e9ecef",
  margin: "0",
};

const trendBox = {
  backgroundColor: "#f8f9fa",
  padding: "12px",
  borderRadius: "4px",
  borderLeft: "4px solid #667eea",
};

const factsList = {
  margin: "0",
  paddingLeft: "20px",
};

const factsItem = {
  margin: "8px 0",
  fontSize: "14px",
  color: "#212529",
  lineHeight: "1.5",
};

const guidanceTitle = {
  margin: "0 0 12px 0",
  fontSize: "14px",
  fontWeight: "bold" as const,
  color: "#212529",
};

const guidanceList = {
  margin: "0",
  paddingLeft: "20px",
};

const guidanceItem = {
  margin: "8px 0",
  fontSize: "14px",
  color: "#212529",
  lineHeight: "1.5",
};

const primaryButton = {
  backgroundColor: "#667eea",
  borderRadius: "4px",
  color: "#fff",
  fontSize: "14px",
  fontWeight: "bold" as const,
  padding: "12px 32px",
  textDecoration: "none" as const,
  textAlign: "center" as const,
  display: "inline-block" as const,
};

const hr = {
  borderColor: "#e9ecef",
  margin: "0",
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

const footerSmall = {
  margin: "0",
  color: "#999",
  fontSize: "11px",
};
