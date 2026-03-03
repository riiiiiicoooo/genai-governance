/**
 * GenAI Governance Dashboard
 *
 * The screen the compliance officer pulls up for the NCUA examiner.
 * The screen the CIO shows the board during quarterly updates.
 *
 * Four tabs:
 * 1. Overview — credit union-wide GenAI health metrics
 * 2. Guardrails — block rates, detection trends, check-level breakdown
 * 3. Model Health — evaluation scores, validation status, drift monitoring
 * 4. Compliance — audit trail stats, open events, examiner readiness
 */

import { useState } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

// ============================================================================
// SYNTHETIC DATA — scaled to a $3.2B credit union, 2 use cases, Q1 production
// ============================================================================

const OVERVIEW = {
  totalInteractions: 43800,
  interactionsThisWeek: 3420,
  deliveredPct: 97.4,
  blockedPct: 2.6,
  piiCaught: 191,
  piiCaughtPct: 0.5,
  complianceEvents: 14,
  unresolvedEvents: 2,
  modelsInProduction: 2,
  modelsValidated: 2,
  avgGuardrailLatency: 172,
  humanReviews: 48,
};

const WEEKLY_TREND = [
  { week: "Jan 6", interactions: 2840, blocked: 78, pii: 12 },
  { week: "Jan 13", interactions: 3012, blocked: 82, pii: 16 },
  { week: "Jan 20", interactions: 3180, blocked: 74, pii: 11 },
  { week: "Jan 27", interactions: 3245, blocked: 89, pii: 18 },
  { week: "Feb 3", interactions: 3310, blocked: 85, pii: 14 },
  { week: "Feb 10", interactions: 3402, blocked: 91, pii: 15 },
  { week: "Feb 17", interactions: 3285, blocked: 79, pii: 13 },
  { week: "Feb 24", interactions: 3490, blocked: 96, pii: 17 },
  { week: "Mar 3", interactions: 3420, blocked: 88, pii: 14 },
];

const GUARDRAIL_CHECKS = [
  { check: "PII Detection", pass: 43418, warn: 191, block: 191, blockPct: 0.44 },
  { check: "Hallucination", pass: 42650, warn: 612, block: 538, blockPct: 1.23 },
  { check: "Bias Screen", pass: 43690, warn: 98, block: 12, blockPct: 0.03 },
  { check: "Compliance Filter", pass: 43612, warn: 142, block: 46, blockPct: 0.11 },
  { check: "Confidence", pass: 43348, warn: 389, block: 63, blockPct: 0.14 },
];

const MODELS = [
  {
    id: "claude-3-sonnet-member-svc",
    name: "Member Service Copilot",
    provider: "Anthropic (Bedrock)",
    useCase: "Call Center Draft Responses",
    riskTier: "Tier 2",
    status: "approved",
    promptVersion: "v2.1",
    lastEval: "Feb 28",
    nextEval: "Mar 28",
    evalScores: {
      accuracy: 91.2,
      relevance: 93.8,
      groundedness: 96.4,
      consistency: 85.1,
      safety: 99.1,
      bias: 97.3,
      compliance: 99.2,
    },
    evalTrend: [
      { period: "Jan", score: 88.4 },
      { period: "Feb", score: 90.6 },
      { period: "Mar", score: 91.2 },
    ],
    interactions: 38200,
    blockRate: 2.8,
  },
  {
    id: "claude-3-sonnet-loan-doc",
    name: "Loan Document Summarizer",
    provider: "Anthropic (Bedrock)",
    useCase: "Loan Application Processing",
    riskTier: "Tier 3",
    status: "approved",
    promptVersion: "v1.1",
    lastEval: "Feb 15",
    nextEval: "Mar 15",
    evalScores: {
      accuracy: 93.5,
      relevance: 95.2,
      groundedness: 97.8,
      consistency: 89.7,
      safety: 99.8,
      bias: 99.4,
      compliance: 99.6,
    },
    evalTrend: [
      { period: "Jan", score: 91.0 },
      { period: "Feb", score: 92.8 },
      { period: "Mar", score: 93.5 },
    ],
    interactions: 5600,
    blockRate: 1.4,
  },
];

const COMPLIANCE_EVENTS = [
  { id: "EVT-014", type: "pii_in_output", severity: "alert", date: "Mar 2", model: "Member Service", status: "open", desc: "Member account number surfaced in draft response to balance inquiry" },
  { id: "EVT-013", type: "guardrail_block", severity: "warning", date: "Mar 1", model: "Member Service", status: "open", desc: "Response included auto loan rate not in context (hallucination)" },
  { id: "EVT-012", type: "compliance_violation", severity: "warning", date: "Feb 27", model: "Member Service", status: "resolved", desc: "Draft said 'guaranteed' when describing share certificate rates" },
  { id: "EVT-011", type: "bias_flag", severity: "warning", date: "Feb 28", model: "Member Service", status: "resolved", desc: "Monthly eval: 4.1% response length disparity by account balance tier" },
  { id: "EVT-010", type: "pii_in_output", severity: "alert", date: "Feb 20", model: "Loan Summarizer", status: "resolved", desc: "Co-applicant SSN appeared in loan summary output" },
];

const PROMPT_REGISTRY = [
  { template: "Member Service Response", activeVersion: "v2.1", totalVersions: 5, pending: 0, lastDeployed: "Feb 12", riskTier: "Tier 2" },
  { template: "Loan Document Summary", activeVersion: "v1.1", totalVersions: 3, pending: 1, lastDeployed: "Jan 28", riskTier: "Tier 3" },
];

// ============================================================================
// THEME
// ============================================================================

const C = {
  bg: "#0f1117",
  surface: "#1a1d27",
  surfaceHover: "#22262f",
  border: "#2a2e3a",
  borderStrong: "#3a3f4d",
  text: "#e4e5e9",
  textMuted: "#8b8fa3",
  textDim: "#5c6178",
  green: "#22c55e",
  greenBg: "rgba(34,197,94,0.1)",
  amber: "#f59e0b",
  amberBg: "rgba(245,158,11,0.1)",
  red: "#ef4444",
  redBg: "rgba(239,68,68,0.1)",
  blue: "#3b82f6",
  blueBg: "rgba(59,130,246,0.1)",
};

// ============================================================================
// COMPONENTS
// ============================================================================

const Badge = ({ children, variant = "default" }) => {
  const map = {
    approved: { bg: C.greenBg, color: C.green, border: "rgba(34,197,94,0.3)" },
    conditional: { bg: C.amberBg, color: C.amber, border: "rgba(245,158,11,0.3)" },
    alert: { bg: C.redBg, color: C.red, border: "rgba(239,68,68,0.3)" },
    warning: { bg: C.amberBg, color: C.amber, border: "rgba(245,158,11,0.3)" },
    open: { bg: C.redBg, color: C.red, border: "rgba(239,68,68,0.3)" },
    resolved: { bg: C.greenBg, color: C.green, border: "rgba(34,197,94,0.3)" },
    tier2: { bg: C.amberBg, color: C.amber, border: "rgba(245,158,11,0.3)" },
    tier3: { bg: C.blueBg, color: C.blue, border: "rgba(59,130,246,0.3)" },
    default: { bg: "rgba(99,102,241,0.1)", color: "#818cf8", border: "rgba(99,102,241,0.3)" },
  };
  const s = map[variant] || map.default;
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: 10,
      fontWeight: 600, backgroundColor: s.bg, color: s.color, border: `1px solid ${s.border}`,
      letterSpacing: "0.04em", textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace",
    }}>{children}</span>
  );
};

const Card = ({ children, style = {} }) => (
  <div style={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, padding: 20, ...style }}>{children}</div>
);

const Metric = ({ value, label, color, sub }) => (
  <div>
    <div style={{ fontSize: 28, fontWeight: 700, color: color || C.text, fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 }}>{value}</div>
    <div style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>{label}</div>
    {sub && <div style={{ fontSize: 11, color: C.textMuted, marginTop: 2 }}>{sub}</div>}
  </div>
);

const SectionLabel = ({ children }) => (
  <h2 style={{ fontSize: 11, fontWeight: 600, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 12px 0", fontFamily: "'JetBrains Mono', monospace" }}>{children}</h2>
);

const ScoreBar = ({ score, threshold = 85, width = 140 }) => {
  const color = score >= threshold ? C.green : score >= threshold - 10 ? C.amber : C.red;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width, height: 6, backgroundColor: C.border, borderRadius: 3, overflow: "hidden", position: "relative" }}>
        <div style={{ height: "100%", width: `${score}%`, backgroundColor: color, borderRadius: 3 }} />
        <div style={{ position: "absolute", left: `${threshold}%`, top: -2, width: 1, height: 10, backgroundColor: C.textDim }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", color, minWidth: 36 }}>{score.toFixed(1)}</span>
    </div>
  );
};

// ============================================================================
// MAIN DASHBOARD
// ============================================================================

export default function GovernanceDashboard() {
  const [tab, setTab] = useState("overview");

  return (
    <div style={{ backgroundColor: C.bg, color: C.text, minHeight: "100vh", fontFamily: "'Inter', sans-serif", fontSize: 14 }}>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ borderBottom: `1px solid ${C.border}`, padding: "14px 28px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: 15, fontWeight: 700, margin: 0, letterSpacing: "-0.01em" }}>GenAI Governance</h1>
          <span style={{ fontSize: 11, color: C.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
            Member Services & Loan Processing -- AI Governance Platform
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {OVERVIEW.unresolvedEvents > 0 && (
            <div style={{ padding: "4px 10px", borderRadius: 6, backgroundColor: C.redBg, border: "1px solid rgba(239,68,68,0.3)", fontSize: 11, fontWeight: 600, color: C.red }}>
              {OVERVIEW.unresolvedEvents} open events
            </div>
          )}
          <div style={{ padding: "4px 10px", borderRadius: 6, backgroundColor: C.greenBg, border: "1px solid rgba(34,197,94,0.3)", fontSize: 11, fontWeight: 600, color: C.green }}>
            {OVERVIEW.modelsValidated}/{OVERVIEW.modelsInProduction} models validated
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ borderBottom: `1px solid ${C.border}`, padding: "0 28px" }}>
        {["overview", "guardrails", "models", "compliance"].map((t) => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: "10px 16px", fontSize: 12, fontWeight: tab === t ? 600 : 400,
            color: tab === t ? C.text : C.textMuted, background: "none", border: "none",
            borderBottom: tab === t ? `2px solid ${C.blue}` : "2px solid transparent",
            cursor: "pointer", fontFamily: "inherit", textTransform: "capitalize",
          }}>{t === "models" ? "Model Health" : t}</button>
        ))}
      </div>

      <div style={{ padding: 28 }}>
        {tab === "overview" && <OverviewTab />}
        {tab === "guardrails" && <GuardrailsTab />}
        {tab === "models" && <ModelsTab />}
        {tab === "compliance" && <ComplianceTab />}
      </div>
    </div>
  );
}

// ============================================================================
// OVERVIEW TAB
// ============================================================================

function OverviewTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Card><Metric value={`${(OVERVIEW.totalInteractions / 1000).toFixed(1)}k`} label="Total Interactions" sub="Q1 2026" /></Card>
        <Card><Metric value={`${OVERVIEW.deliveredPct}%`} label="Delivered" color={C.green} sub={`${OVERVIEW.blockedPct}% blocked`} /></Card>
        <Card><Metric value={OVERVIEW.piiCaught} label="PII Caught" color={C.red} sub={`${OVERVIEW.piiCaughtPct}% of outputs`} /></Card>
        <Card><Metric value={`${OVERVIEW.avgGuardrailLatency}ms`} label="Avg Guardrail Latency" color={C.blue} /></Card>
      </div>

      <Card>
        <SectionLabel>Weekly Interaction Volume</SectionLabel>
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={WEEKLY_TREND} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: C.textDim }} />
              <YAxis tick={{ fontSize: 11, fill: C.textDim }} width={45} />
              <Tooltip contentStyle={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 12 }} />
              <Area type="monotone" dataKey="interactions" stroke={C.blue} fill={C.blue} fillOpacity={0.1} strokeWidth={2} name="Total" />
              <Area type="monotone" dataKey="blocked" stroke={C.red} fill={C.red} fillOpacity={0.15} strokeWidth={2} name="Blocked" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Card>
          <SectionLabel>Prompt Registry</SectionLabel>
          {PROMPT_REGISTRY.map((p, i) => (
            <div key={i} style={{ padding: "10px 0", borderBottom: i < PROMPT_REGISTRY.length - 1 ? `1px solid ${C.border}` : "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{p.template}</div>
                  <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>
                    Active: {p.activeVersion} -- {p.totalVersions} versions -- Deployed {p.lastDeployed}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 4 }}>
                  <Badge variant={p.riskTier === "Tier 2" ? "tier2" : "tier3"}>{p.riskTier}</Badge>
                  {p.pending > 0 && <Badge variant="warning">{p.pending} pending</Badge>}
                </div>
              </div>
            </div>
          ))}
        </Card>
        <Card>
          <SectionLabel>Recent Compliance Events</SectionLabel>
          {COMPLIANCE_EVENTS.slice(0, 4).map((e, i) => (
            <div key={i} style={{ padding: "8px 0", borderBottom: i < 3 ? `1px solid ${C.border}` : "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{e.desc}</div>
                  <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>{e.date} -- {e.model}</div>
                </div>
                <Badge variant={e.status}>{e.status}</Badge>
              </div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}

// ============================================================================
// GUARDRAILS TAB
// ============================================================================

function GuardrailsTab() {
  const barData = GUARDRAIL_CHECKS.map((g) => ({
    name: g.check.replace("Detection", "").replace("Filter", "").replace("Assessment", "").trim(),
    blocks: g.block,
    blockPct: g.blockPct,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SectionLabel>Guardrail Check Results (Q1 2026)</SectionLabel>
      {GUARDRAIL_CHECKS.map((g, i) => (
        <Card key={i}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{g.check}</div>
              <div style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>
                {g.pass.toLocaleString()} pass -- {g.warn.toLocaleString()} warn -- {g.block.toLocaleString()} block
              </div>
            </div>
            <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: g.blockPct > 0.5 ? C.amber : C.green }}>
                  {g.blockPct}%
                </div>
                <div style={{ fontSize: 10, color: C.textDim }}>block rate</div>
              </div>
              <div style={{ width: 200, height: 8, backgroundColor: C.border, borderRadius: 4, overflow: "hidden" }}>
                <div style={{ height: "100%", backgroundColor: C.green, width: `${(g.pass / (g.pass + g.warn + g.block)) * 100}%`, float: "left" }} />
                <div style={{ height: "100%", backgroundColor: C.amber, width: `${(g.warn / (g.pass + g.warn + g.block)) * 100}%`, float: "left" }} />
                <div style={{ height: "100%", backgroundColor: C.red, width: `${(g.block / (g.pass + g.warn + g.block)) * 100}%`, float: "left" }} />
              </div>
            </div>
          </div>
        </Card>
      ))}

      <Card>
        <SectionLabel>Block Volume by Check</SectionLabel>
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: C.textDim }} />
              <YAxis tick={{ fontSize: 11, fill: C.textDim }} width={50} />
              <Tooltip contentStyle={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 12 }} />
              <Bar dataKey="blocks" radius={[4, 4, 0, 0]}>
                {barData.map((d, i) => <Cell key={i} fill={d.blockPct > 0.5 ? C.amber : C.blue} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}

// ============================================================================
// MODEL HEALTH TAB
// ============================================================================

function ModelsTab() {
  const [selected, setSelected] = useState(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SectionLabel>Registered Models</SectionLabel>
      {MODELS.map((m) => (
        <Card key={m.id} style={{ cursor: "pointer", borderColor: selected === m.id ? C.blue : C.border }}
          onClick={() => setSelected(selected === m.id ? null : m.id)}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{m.name}</span>
                <Badge variant={m.status}>{m.status}</Badge>
                <Badge variant={m.riskTier === "Tier 2" ? "tier2" : "tier3"}>{m.riskTier}</Badge>
              </div>
              <div style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>
                {m.provider} -- {m.useCase} -- Prompt {m.promptVersion} -- {(m.interactions / 1000).toFixed(1)}k interactions
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 11, color: C.textDim }}>Last eval: {m.lastEval}</div>
              <div style={{ fontSize: 11, color: C.textDim }}>Next: {m.nextEval}</div>
            </div>
          </div>

          {selected === m.id && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                <div>
                  <SectionLabel>Evaluation Scores</SectionLabel>
                  {Object.entries(m.evalScores).map(([dim, score]) => (
                    <div key={dim} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0" }}>
                      <span style={{ fontSize: 12, color: C.textMuted, textTransform: "capitalize" }}>{dim}</span>
                      <ScoreBar score={score} threshold={dim === "safety" || dim === "compliance" ? 99 : dim === "groundedness" ? 95 : 85} />
                    </div>
                  ))}
                </div>
                <div>
                  <SectionLabel>Score Trend (Monthly Evals)</SectionLabel>
                  <div style={{ height: 200 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={m.evalTrend} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
                        <XAxis dataKey="period" tick={{ fontSize: 11, fill: C.textDim }} />
                        <YAxis domain={[80, 100]} tick={{ fontSize: 11, fill: C.textDim }} width={30} />
                        <Tooltip contentStyle={{ backgroundColor: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 12 }} />
                        <Area type="monotone" dataKey="score" stroke={C.green} fill={C.green} fillOpacity={0.1} strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// COMPLIANCE TAB
// ============================================================================

function ComplianceTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <Card><Metric value={OVERVIEW.complianceEvents} label="Total Events" color={C.amber} /></Card>
        <Card><Metric value={OVERVIEW.unresolvedEvents} label="Unresolved" color={C.red} /></Card>
        <Card><Metric value={OVERVIEW.humanReviews} label="Human Reviews" /></Card>
        <Card><Metric value={OVERVIEW.piiCaught} label="PII Prevented" color={C.green} /></Card>
      </div>

      <Card>
        <SectionLabel>Compliance Events</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto auto auto", gap: "0", fontSize: 12 }}>
          {["ID", "Description", "Severity", "Date", "Status"].map((h) => (
            <div key={h} style={{ padding: "8px 12px", fontWeight: 600, color: C.textDim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em", borderBottom: `1px solid ${C.border}` }}>{h}</div>
          ))}
          {COMPLIANCE_EVENTS.map((e, i) => (
            [
              <div key={`${i}-id`} style={{ padding: "10px 12px", borderBottom: `1px solid ${C.border}`, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: C.textMuted }}>{e.id}</div>,
              <div key={`${i}-desc`} style={{ padding: "10px 12px", borderBottom: `1px solid ${C.border}` }}>
                <div style={{ fontWeight: 500 }}>{e.desc}</div>
                <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>{e.model} -- {e.type}</div>
              </div>,
              <div key={`${i}-sev`} style={{ padding: "10px 12px", borderBottom: `1px solid ${C.border}` }}><Badge variant={e.severity}>{e.severity}</Badge></div>,
              <div key={`${i}-date`} style={{ padding: "10px 12px", borderBottom: `1px solid ${C.border}`, color: C.textMuted, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>{e.date}</div>,
              <div key={`${i}-status`} style={{ padding: "10px 12px", borderBottom: `1px solid ${C.border}` }}><Badge variant={e.status}>{e.status}</Badge></div>,
            ]
          ))}
        </div>
      </Card>

      <Card>
        <SectionLabel>NCUA Exam Readiness</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          {[
            { label: "Interaction Logs", status: "Complete", desc: "43,800 interactions fully logged with guardrail results, examiner-ready exports available", ok: true },
            { label: "Model Documentation", status: "Current", desc: "2/2 model cards validated. FFIEC model risk management format. Last updated Feb 28.", ok: true },
            { label: "Prompt Version History", status: "Complete", desc: "8 prompt versions across 2 templates, full approval chain with compliance sign-off", ok: true },
          ].map((item, i) => (
            <div key={i} style={{ padding: 16, borderRadius: 6, border: `1px solid ${item.ok ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`, backgroundColor: item.ok ? C.greenBg : C.redBg }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{item.label}</span>
                <Badge variant={item.ok ? "approved" : "alert"}>{item.status}</Badge>
              </div>
              <div style={{ fontSize: 11, color: C.textMuted, lineHeight: 1.4 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
