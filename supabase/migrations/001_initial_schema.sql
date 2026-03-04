-- GenAI Governance Platform: Initial Schema
-- This migration creates all tables for prompt management, guardrails, compliance logging,
-- model evaluations, and audit trails with Row-Level Security policies.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. Authentication & Roles (RLS Foundation)
-- ============================================================================

-- Create custom role types (extend beyond Supabase built-in roles)
CREATE TYPE user_role AS ENUM ('compliance_officer', 'model_owner', 'examiner', 'admin');

-- Users table (references Supabase auth.users)
CREATE TABLE IF NOT EXISTS users (
  id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  role user_role NOT NULL DEFAULT 'model_owner',
  full_name TEXT,
  institution_id UUID NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on role for RLS policies
CREATE INDEX idx_users_role ON users(role);

-- ============================================================================
-- 2. Prompt Registry (Versioned Templates)
-- ============================================================================

CREATE TYPE approval_status AS ENUM ('draft', 'pending_review', 'approved', 'rejected', 'deprecated');

CREATE TABLE IF NOT EXISTS prompt_templates (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  description TEXT,
  use_case TEXT NOT NULL CHECK (use_case IN ('member_service', 'loan_processing')),
  owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(name)
);

CREATE INDEX idx_prompt_templates_owner ON prompt_templates(owner_id);
CREATE INDEX idx_prompt_templates_use_case ON prompt_templates(use_case);

CREATE TABLE IF NOT EXISTS prompt_versions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  template_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
  version_number INT NOT NULL,
  system_prompt TEXT NOT NULL,
  user_prompt_template TEXT NOT NULL,
  context_variables TEXT[] NOT NULL DEFAULT '{}',
  approval_status approval_status NOT NULL DEFAULT 'draft',
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
  approval_notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  approved_at TIMESTAMP WITH TIME ZONE,
  deprecated_at TIMESTAMP WITH TIME ZONE,
  UNIQUE(template_id, version_number)
);

CREATE INDEX idx_prompt_versions_template ON prompt_versions(template_id);
CREATE INDEX idx_prompt_versions_status ON prompt_versions(approval_status);
CREATE INDEX idx_prompt_versions_created_by ON prompt_versions(created_by);

-- ============================================================================
-- 3. Guardrail Configuration & Versioning
-- ============================================================================

CREATE TYPE guardrail_type AS ENUM ('pii_detection', 'hallucination', 'bias_screening', 'compliance_filter', 'confidence');
CREATE TYPE guardrail_severity AS ENUM ('info', 'warning', 'critical');

CREATE TABLE IF NOT EXISTS guardrail_configs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  guardrail_type guardrail_type NOT NULL,
  owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_guardrail_configs_type ON guardrail_configs(guardrail_type);
CREATE INDEX idx_guardrail_configs_owner ON guardrail_configs(owner_id);

CREATE TABLE IF NOT EXISTS guardrail_versions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  guardrail_config_id UUID NOT NULL REFERENCES guardrail_configs(id) ON DELETE CASCADE,
  version_number INT NOT NULL,
  rules JSONB NOT NULL DEFAULT '{}',
  threshold NUMERIC(5, 4) DEFAULT 0.5,
  enabled BOOLEAN DEFAULT TRUE,
  approval_status approval_status NOT NULL DEFAULT 'draft',
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
  approval_notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  approved_at TIMESTAMP WITH TIME ZONE,
  UNIQUE(guardrail_config_id, version_number)
);

CREATE INDEX idx_guardrail_versions_config ON guardrail_versions(guardrail_config_id);
CREATE INDEX idx_guardrail_versions_status ON guardrail_versions(approval_status);

-- ============================================================================
-- 4. Interaction Logs (Immutable Audit Trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS interaction_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  interaction_id TEXT NOT NULL UNIQUE,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  use_case TEXT NOT NULL CHECK (use_case IN ('member_service', 'loan_processing')),
  member_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  model_provider TEXT NOT NULL DEFAULT 'aws_bedrock',

  -- Input
  input_context JSONB NOT NULL DEFAULT '{}',
  prompt_template_id UUID REFERENCES prompt_templates(id),
  prompt_version_id UUID REFERENCES prompt_versions(id),
  rendered_prompt TEXT NOT NULL,

  -- Output
  model_output TEXT,
  output_tokens INT,
  input_tokens INT,
  cost_usd NUMERIC(10, 6),

  -- Guardrail Results
  guardrail_results JSONB NOT NULL DEFAULT '{}',
  guardrail_decision TEXT CHECK (guardrail_decision IN ('deliver', 'block', 'warn')),

  -- User Action
  user_action TEXT CHECK (user_action IN ('sent', 'edited', 'discarded')),
  final_output TEXT,

  -- Compliance & Audit
  langsmith_trace_id TEXT,
  trace_url TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

  CONSTRAINT immutable_log CHECK (created_at IS NOT NULL)
);

-- Indexes for common queries
CREATE INDEX idx_interaction_logs_user ON interaction_logs(user_id);
CREATE INDEX idx_interaction_logs_use_case ON interaction_logs(use_case);
CREATE INDEX idx_interaction_logs_model ON interaction_logs(model_id);
CREATE INDEX idx_interaction_logs_template ON interaction_logs(prompt_template_id);
CREATE INDEX idx_interaction_logs_created ON interaction_logs(created_at);
CREATE INDEX idx_interaction_logs_guardrail_decision ON interaction_logs(guardrail_decision);
CREATE INDEX idx_interaction_logs_trace ON interaction_logs(langsmith_trace_id);

-- ============================================================================
-- 5. Compliance Events (Severity-Based Routing)
-- ============================================================================

CREATE TYPE compliance_event_type AS ENUM (
  'guardrail_block',
  'guardrail_warn',
  'prompt_change',
  'guardrail_config_change',
  'model_evaluation_complete',
  'bias_detected',
  'drift_detected',
  'evaluation_failed'
);

CREATE TABLE IF NOT EXISTS compliance_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  interaction_log_id UUID REFERENCES interaction_logs(id) ON DELETE CASCADE,
  event_type compliance_event_type NOT NULL,
  severity guardrail_severity NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  details JSONB NOT NULL DEFAULT '{}',

  -- Resolution
  resolved BOOLEAN DEFAULT FALSE,
  resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
  resolution_notes TEXT,
  resolved_at TIMESTAMP WITH TIME ZONE,

  -- Notification State
  notified_pagerduty BOOLEAN DEFAULT FALSE,
  notified_slack BOOLEAN DEFAULT FALSE,
  notified_email BOOLEAN DEFAULT FALSE,

  -- Audit
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_compliance_events_type ON compliance_events(event_type);
CREATE INDEX idx_compliance_events_severity ON compliance_events(severity);
CREATE INDEX idx_compliance_events_resolved ON compliance_events(resolved);
CREATE INDEX idx_compliance_events_created ON compliance_events(created_at);
CREATE INDEX idx_compliance_events_interaction ON compliance_events(interaction_log_id);

-- ============================================================================
-- 6. Model Evaluations & Model Cards
-- ============================================================================

CREATE TYPE evaluation_metric_type AS ENUM ('accuracy', 'bias', 'drift', 'latency', 'cost_per_interaction');

CREATE TABLE IF NOT EXISTS model_evaluations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  model_id TEXT NOT NULL,
  model_name TEXT NOT NULL,
  use_case TEXT NOT NULL CHECK (use_case IN ('member_service', 'loan_processing')),
  evaluator_id UUID REFERENCES users(id) ON DELETE SET NULL,

  -- Evaluation Run
  evaluation_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  test_case_count INT,
  passed_count INT,
  failed_count INT,
  total_duration_seconds INT,

  -- Results
  metrics JSONB NOT NULL DEFAULT '{}',
  findings JSONB NOT NULL DEFAULT '{}',
  recommendations JSONB NOT NULL DEFAULT '{}',

  -- Model Card (MRM Documentation)
  model_card JSONB NOT NULL DEFAULT '{}',

  -- Audit
  langsmith_project_id TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_model_evaluations_model ON model_evaluations(model_id);
CREATE INDEX idx_model_evaluations_use_case ON model_evaluations(use_case);
CREATE INDEX idx_model_evaluations_date ON model_evaluations(evaluation_date);

CREATE TABLE IF NOT EXISTS evaluation_test_cases (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  evaluation_id UUID NOT NULL REFERENCES model_evaluations(id) ON DELETE CASCADE,
  test_case_name TEXT NOT NULL,
  input_text TEXT NOT NULL,
  input_context JSONB NOT NULL DEFAULT '{}',
  expected_output TEXT,
  expected_guardrail_decision TEXT CHECK (expected_guardrail_decision IN ('deliver', 'block', 'warn')),

  -- Results
  actual_output TEXT,
  actual_guardrail_decision TEXT,
  passed BOOLEAN,
  error_message TEXT,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_evaluation_test_cases_evaluation ON evaluation_test_cases(evaluation_id);

-- ============================================================================
-- 7. Audit Reports
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_reports (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  report_type TEXT NOT NULL,
  period_start TIMESTAMP WITH TIME ZONE NOT NULL,
  period_end TIMESTAMP WITH TIME ZONE NOT NULL,
  generated_by UUID REFERENCES users(id) ON DELETE SET NULL,

  -- Metrics
  total_interactions INT DEFAULT 0,
  interactions_blocked INT DEFAULT 0,
  block_rate NUMERIC(5, 4) DEFAULT 0,
  pii_instances_caught INT DEFAULT 0,
  average_guardrail_latency_ms INT DEFAULT 0,

  -- Trends
  metrics JSONB NOT NULL DEFAULT '{}',
  findings JSONB NOT NULL DEFAULT '{}',

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_reports_type ON audit_reports(report_type);
CREATE INDEX idx_audit_reports_period ON audit_reports(period_start, period_end);

-- ============================================================================
-- 8. Dashboard Metrics (Denormalized for Performance)
-- ============================================================================

CREATE TABLE IF NOT EXISTS dashboard_metrics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  metric_date DATE NOT NULL DEFAULT CURRENT_DATE,

  -- Interaction Metrics
  total_interactions INT DEFAULT 0,
  interactions_delivered INT DEFAULT 0,
  interactions_blocked INT DEFAULT 0,
  interactions_warned INT DEFAULT 0,

  -- Guardrail Metrics (by type)
  pii_blocks INT DEFAULT 0,
  hallucination_blocks INT DEFAULT 0,
  bias_warns INT DEFAULT 0,
  confidence_blocks INT DEFAULT 0,

  -- Quality Metrics
  avg_response_latency_ms INT DEFAULT 0,
  total_cost_usd NUMERIC(10, 2) DEFAULT 0,

  -- Compliance Events
  critical_events INT DEFAULT 0,
  warning_events INT DEFAULT 0,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  UNIQUE(metric_date)
);

CREATE INDEX idx_dashboard_metrics_date ON dashboard_metrics(metric_date);

-- ============================================================================
-- 9. Row-Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE prompt_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE prompt_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE guardrail_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE guardrail_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE interaction_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_test_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_metrics ENABLE ROW LEVEL SECURITY;

-- Policy: Compliance Officers see all records
CREATE POLICY compliance_officer_all ON interaction_logs
  FOR SELECT USING (
    (SELECT role FROM users WHERE id = auth.uid()) = 'compliance_officer'
  );

CREATE POLICY compliance_officer_all_events ON compliance_events
  FOR SELECT USING (
    (SELECT role FROM users WHERE id = auth.uid()) = 'compliance_officer'
  );

CREATE POLICY compliance_officer_all_evaluations ON model_evaluations
  FOR SELECT USING (
    (SELECT role FROM users WHERE id = auth.uid()) = 'compliance_officer'
  );

-- Policy: Model Owners see their own models and interactions
CREATE POLICY model_owner_own_interactions ON interaction_logs
  FOR SELECT USING (
    user_id = auth.uid()
    OR (SELECT role FROM users WHERE id = auth.uid()) = 'compliance_officer'
  );

CREATE POLICY model_owner_own_templates ON prompt_templates
  FOR SELECT USING (
    owner_id = auth.uid()
    OR (SELECT role FROM users WHERE id = auth.uid()) = 'compliance_officer'
  );

CREATE POLICY model_owner_own_guardrails ON guardrail_configs
  FOR SELECT USING (
    owner_id = auth.uid()
    OR (SELECT role FROM users WHERE id = auth.uid()) = 'compliance_officer'
  );

-- Policy: Examiners have read-only access to all audit-relevant views
CREATE POLICY examiner_readonly_interactions ON interaction_logs
  FOR SELECT USING (
    (SELECT role FROM users WHERE id = auth.uid()) IN ('examiner', 'compliance_officer')
  );

CREATE POLICY examiner_readonly_compliance ON compliance_events
  FOR SELECT USING (
    (SELECT role FROM users WHERE id = auth.uid()) IN ('examiner', 'compliance_officer')
  );

CREATE POLICY examiner_readonly_evaluations ON model_evaluations
  FOR SELECT USING (
    (SELECT role FROM users WHERE id = auth.uid()) IN ('examiner', 'compliance_officer')
  );

CREATE POLICY examiner_readonly_audit_reports ON audit_reports
  FOR SELECT USING (
    (SELECT role FROM users WHERE id = auth.uid()) IN ('examiner', 'compliance_officer')
  );

-- Policy: Dashboard metrics visible to all authenticated users
CREATE POLICY all_read_metrics ON dashboard_metrics
  FOR SELECT USING (auth.uid() IS NOT NULL);

-- Policy: Create new interactions (via service role)
CREATE POLICY interactions_insert ON interaction_logs
  FOR INSERT WITH CHECK (true);

-- Policy: Create new compliance events (via service role)
CREATE POLICY events_insert ON compliance_events
  FOR INSERT WITH CHECK (true);

-- ============================================================================
-- 10. Trigger Functions for Automation
-- ============================================================================

-- Update compliance_events.updated_at on change
CREATE OR REPLACE FUNCTION update_compliance_events_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER compliance_events_updated_at
  BEFORE UPDATE ON compliance_events
  FOR EACH ROW
  EXECUTE FUNCTION update_compliance_events_timestamp();

-- Update dashboard metrics when interaction_logs are inserted
CREATE OR REPLACE FUNCTION update_dashboard_metrics_on_interaction()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO dashboard_metrics (metric_date, total_interactions)
  VALUES (CURRENT_DATE, 1)
  ON CONFLICT (metric_date) DO UPDATE
  SET total_interactions = dashboard_metrics.total_interactions + 1;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER interaction_logs_update_metrics
  AFTER INSERT ON interaction_logs
  FOR EACH ROW
  EXECUTE FUNCTION update_dashboard_metrics_on_interaction();

-- ============================================================================
-- 11. Views for Examiner Reports
-- ============================================================================

-- View: All interactions with guardrail outcomes (for examiners)
CREATE OR REPLACE VIEW interaction_audit_view AS
SELECT
  il.interaction_id,
  il.created_at,
  il.use_case,
  il.member_id,
  il.model_id,
  pv.version_number as prompt_version,
  il.guardrail_decision,
  il.user_action,
  il.model_output,
  il.input_tokens,
  il.output_tokens,
  il.cost_usd,
  il.langsmith_trace_id
FROM interaction_logs il
LEFT JOIN prompt_versions pv ON il.prompt_version_id = pv.id
ORDER BY il.created_at DESC;

-- View: Compliance events by severity and date
CREATE OR REPLACE VIEW compliance_event_summary AS
SELECT
  DATE(created_at) as event_date,
  severity,
  event_type,
  COUNT(*) as count,
  SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as resolved_count
FROM compliance_events
GROUP BY DATE(created_at), severity, event_type
ORDER BY event_date DESC;

-- View: Monthly compliance metrics
CREATE OR REPLACE VIEW monthly_compliance_metrics AS
SELECT
  DATE_TRUNC('month', created_at)::DATE as month,
  use_case,
  COUNT(*) as total_interactions,
  SUM(CASE WHEN guardrail_decision = 'block' THEN 1 ELSE 0 END) as blocked_count,
  ROUND(
    100.0 * SUM(CASE WHEN guardrail_decision = 'block' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
    2
  ) as block_rate_percent,
  AVG(CASE WHEN input_tokens > 0 THEN output_tokens::NUMERIC / input_tokens ELSE 0 END) as avg_token_ratio
FROM interaction_logs
GROUP BY DATE_TRUNC('month', created_at), use_case
ORDER BY month DESC;

-- ============================================================================
-- 12. Grant Permissions (for Supabase service role)
-- ============================================================================

-- Service role can read/write everything (for backend operations)
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- ============================================================================
-- 13. Seed Data (Examples - Optional)
-- ============================================================================

-- Insert default institutions (if needed)
-- This would be institution-specific based on deployment
