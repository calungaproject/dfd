export interface PipelineType {
  id: string;
  display_name: string;
  description: string;
}

export type RunStatus = 'succeeded' | 'failed' | 'aborted';
export type ProposalStatus = 'pending' | 'accepted' | 'rejected' | 'duplicate';
export type RuleCategory = 'build' | 'infra' | 'unknown';

export interface PipelineRun {
  id: string;
  pipeline_type_id: string;
  completion_time: string;
  status: RunStatus;
  package_name: string | null;
  package_version: string | null;
  target_os: string | null;
  event_type: string | null;
  git_org: string | null;
  git_repo: string | null;
  source_url: string | null;
  pipeline_url: string | null;
  root_cause: string | null;
  category: string | null;
  confidence: number | null;
  alternative_root_cause: string | null;
  alternative_confidence: number | null;
  ambiguity_note: string | null;
  failed_task: string | null;
  failed_step: string | null;
  error_message: string | null;
  evidence: string | null;
  details: string | null;
  suggested_action: string | null;
  remediation: string | null;
  analysis_version: number | null;
  taxonomy_matched: boolean | null;
}

export interface RunsCounts {
  all: number;
  failed: number;
  succeeded: number;
  aborted: number;
  unknown: number;
  novel: number;
}

export interface RunsResponse {
  runs: PipelineRun[];
  total: number;
  page: number;
  per_page: number;
  counts: RunsCounts;
}

export interface BoardEntry {
  id: number;
  pipeline_run_id: string;
  agent_type: string;
  findings: string;
  evidence: string | null;
  classification_suggestion: string | null;
  confidence: string | null;
  flags: string | null;
  thinking: string | null;
  created_at: string;
}

export interface RunDetail extends PipelineRun {
  thinking: string | null;
  board_entries: BoardEntry[];
}

export interface AnalysisVersion {
  id: number;
  pipeline_run_id: string;
  root_cause: string;
  category: string;
  confidence: number;
  alternative_root_cause: string | null;
  alternative_confidence: number | null;
  ambiguity_note: string | null;
  failed_task: string | null;
  failed_step: string | null;
  package_name: string | null;
  error_message: string | null;
  evidence: string | null;
  details: string | null;
  suggested_action: string | null;
  remediation: string | null;
  thinking: string | null;
  analysis_version: number;
  status: string;
  created_at: string;
}

export interface RunHistoryResponse {
  pipeline_run_id: string;
  versions: AnalysisVersion[];
}

export interface DailyStats {
  date: string;
  succeeded: number;
  failed: number;
  aborted: number;
}

export interface RootCauseStat {
  root_cause: string;
  category: string;
  count: number;
}

export interface StatsResponse {
  total: number;
  succeeded: number;
  failed: number;
  aborted: number;
  pass_rate: number;
  daily: DailyStats[];
  root_causes: RootCauseStat[];
}

export interface TaxonomyRule {
  id: number;
  pipeline_type_id: string;
  root_cause: string;
  category: string;
  error_signature: string;
  priority_order: number;
  priority_rule: string | null;
  investigation_recipe: string | null;
  origin: string;
  created_at: string;
}

export interface RuleProposal {
  id: number;
  pipeline_type_id: string;
  pipeline_run_id: string | null;
  root_cause: string;
  category: string;
  error_signature: string;
  priority_rule: string;
  investigation_recipe: string | null;
  reasoning: string | null;
  status: ProposalStatus;
  created_at: string;
}

export interface AnalysisRun {
  id: number;
  trigger: string;
  hours_back: number;
  pipeline_types: string[];
  status: string;
  started_at: string;
  completed_at: string | null;
  total_pipeline_runs: number | null;
  analyzed_count: number | null;
  total_cost_usd: number | null;
  error_message: string | null;
}

export interface CostBreakdown {
  invocation_type: string;
  call_count: number;
  total_cost: number;
  total_input_tokens: number | null;
  total_output_tokens: number | null;
}

export interface AnalysisRunPipelineRun {
  id: string;
  pipeline_type_id: string;
  status: string;
  event_type: string | null;
  git_org: string | null;
  git_repo: string | null;
  root_cause: string | null;
  category: string | null;
  confidence: number | null;
}

export interface AnalysisRunTaxonomyChange {
  id: number;
  pipeline_type_id: string;
  root_cause: string;
  category: string;
  status: string;
  reasoning: string | null;
  pipeline_run_id: string | null;
}

export interface AnalysisRunDetail extends AnalysisRun {
  cost_breakdown: CostBreakdown[];
  pipeline_runs: AnalysisRunPipelineRun[];
  taxonomy_changes: AnalysisRunTaxonomyChange[];
}

export interface ReanalysisItem {
  id: number;
  pipeline_run_id: string;
  pipeline_type_id: string;
  reason: string;
  triggered_by: string;
  status: string;
  created_at: string;
}

export interface CostByType {
  invocation_type: string;
  calls: number;
  total_cost: number;
  input_tokens: number | null;
  output_tokens: number | null;
  cache_read_tokens: number | null;
  avg_duration_ms: number | null;
}

export interface DailyCost {
  day: string;
  invocation_type: string;
  calls: number;
  cost: number;
}

export interface RecentCostEntry {
  id: number;
  invocation_type: string;
  model: string | null;
  cost_usd: number;
  input_tokens: number | null;
  output_tokens: number | null;
  cache_read_tokens: number | null;
  cache_creation_tokens: number | null;
  duration_ms: number | null;
  pipeline_run_id: string | null;
  chat_session_id: string | null;
  created_at: string;
}

export interface CostsResponse {
  by_type: CostByType[];
  daily: DailyCost[];
  recent: RecentCostEntry[];
}

export interface ChatSession {
  id: string;
  title: string | null;
  context_pipeline_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls: unknown | null;
  cost_usd: number | null;
  tokens_used: number | null;
  created_at: string;
}

export interface ConversationAgent {
  agent: string;
  classification?: string;
  confidence?: string | number;
  specialists?: string[];
  root_cause?: string;
  category?: string;
}

export interface BoardEntry {
  id: number;
  pipeline_run_id: string;
  agent_type: string;
  findings: string;
  evidence: string | null;
  classification_suggestion: string | null;
  confidence: string | null;
  flags: string | null;
  thinking: string | null;
  created_at: string;
}

export interface ConversationData {
  pipeline_run_id: string;
  analysis_version: number;
  agents: ConversationAgent[];
  board_entries: BoardEntry[];
}

export interface ConversationLog {
  pipeline_run_id: string;
  analysis_version: number;
  summary: string | null;
  agent_sequence: string[] | null;
  conversation: ConversationData;
}

export interface SSEEvent {
  type: 'tool_call' | 'tool_result' | 'text_delta' | 'done' | 'error';
  name?: string;
  input?: Record<string, unknown>;
  result?: string;
  text?: string;
  content?: string;
  cost_usd?: number;
  tokens_used?: number;
  message?: string;
}
