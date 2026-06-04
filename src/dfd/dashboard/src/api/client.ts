import type {
  PipelineType,
  RunsResponse,
  RunDetail,
  RunHistoryResponse,
  StatsResponse,
  TaxonomyRule,
  RuleProposal,
  AnalysisRun,
  AnalysisRunDetail,
  ReanalysisItem,
  CostsResponse,
  ChatSession,
  ChatMessage,
  ConversationLog,
} from './types';

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function put<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function del<T>(url: string): Promise<T> {
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// -- Pipeline Types --

export function fetchPipelineTypes(): Promise<PipelineType[]> {
  return get<PipelineType[]>('/api/pipeline-types');
}

// -- Runs --

interface RunsParams {
  pipeline_type?: string;
  status?: string;
  package_name?: string;
  days?: number;
  from?: string;
  to?: string;
  root_cause?: string;
  root_cause_search?: string;
  has_root_cause?: boolean;
  taxonomy_matched?: boolean;
  name_search?: string;
  page?: number;
  per_page?: number;
}

export function fetchRuns(params: RunsParams = {}): Promise<RunsResponse> {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') sp.set(k, String(v));
  }
  return get<RunsResponse>(`/api/runs?${sp}`);
}

export function fetchRun(pipelineRunId: string): Promise<RunDetail> {
  return get<RunDetail>(`/api/runs/${encodeURIComponent(pipelineRunId)}`);
}

export function fetchRunHistory(pipelineRunId: string): Promise<RunHistoryResponse> {
  return get<RunHistoryResponse>(`/api/runs/${encodeURIComponent(pipelineRunId)}/history`);
}

// -- Stats --

export function fetchStats(params: { pipeline_type?: string; days?: number } = {}): Promise<StatsResponse> {
  const sp = new URLSearchParams();
  if (params.pipeline_type) sp.set('pipeline_type', params.pipeline_type);
  if (params.days) sp.set('days', String(params.days));
  return get<StatsResponse>(`/api/stats?${sp}`);
}

// -- Taxonomy --

export function fetchTaxonomyRules(pipelineTypeId: string): Promise<TaxonomyRule[]> {
  return get<TaxonomyRule[]>(`/api/taxonomy/${encodeURIComponent(pipelineTypeId)}`);
}

export function fetchTaxonomyProposals(pipelineTypeId: string): Promise<RuleProposal[]> {
  return get<RuleProposal[]>(`/api/taxonomy/${encodeURIComponent(pipelineTypeId)}/proposals`);
}

export function acceptProposal(pipelineTypeId: string, proposalId: number) {
  return post(`/api/taxonomy/${encodeURIComponent(pipelineTypeId)}/proposals/${proposalId}/accept`);
}

export function rejectProposal(pipelineTypeId: string, proposalId: number) {
  return post(`/api/taxonomy/${encodeURIComponent(pipelineTypeId)}/proposals/${proposalId}/reject`);
}

export function updateRule(pipelineTypeId: string, ruleId: number, data: Partial<TaxonomyRule>) {
  return put(`/api/taxonomy/${encodeURIComponent(pipelineTypeId)}/rules/${ruleId}`, data);
}

export function deleteRule(pipelineTypeId: string, ruleId: number) {
  return del(`/api/taxonomy/${encodeURIComponent(pipelineTypeId)}/rules/${ruleId}`);
}

export function mergeRule(pipelineTypeId: string, ruleId: number, targetRuleId: number) {
  return post(`/api/taxonomy/${encodeURIComponent(pipelineTypeId)}/rules/${ruleId}/merge`, {
    target_rule_id: targetRuleId,
  });
}

// -- Analysis Runs --

export function fetchAnalysisRuns(limit = 20): Promise<AnalysisRun[]> {
  return get<AnalysisRun[]>(`/api/analysis-runs?limit=${limit}`);
}

export function fetchAnalysisRunDetail(runId: number): Promise<AnalysisRunDetail> {
  return get<AnalysisRunDetail>(`/api/analysis-runs/${runId}`);
}

export function fetchReanalysisQueue(): Promise<ReanalysisItem[]> {
  return get<ReanalysisItem[]>(`/api/reanalysis/queue`);
}

export function triggerReanalysis(data: { pipeline_type_id: string; root_cause?: string; days?: number }) {
  return post<{ queued: number }>('/api/reanalysis', data);
}

export function reanalyzeSingleRun(pipelineRunId: string) {
  return post<{ queued: number; pipeline_run_id: string }>(
    `/api/reanalysis/${encodeURIComponent(pipelineRunId)}`,
  );
}

// -- Costs --

export function fetchCosts(days = 30): Promise<CostsResponse> {
  return get<CostsResponse>(`/api/costs?days=${days}`);
}

// -- Chat --

export function createChatSession(data: { title?: string; context_pipeline_run_id?: string }) {
  return post<{ session_id: string }>('/api/chat/sessions', data);
}

export function fetchChatSessions(limit = 20) {
  return get<{ sessions: ChatSession[] }>(`/api/chat/sessions?limit=${limit}`);
}

export function fetchChatMessages(sessionId: string) {
  return get<{ messages: ChatMessage[] }>(`/api/chat/sessions/${sessionId}/messages`);
}

export function sendChatMessage(sessionId: string, content: string): Promise<Response> {
  return fetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
}

// -- Conversations --

export function fetchConversation(pipelineRunId: string): Promise<ConversationLog> {
  return get<ConversationLog>(`/api/conversations/${encodeURIComponent(pipelineRunId)}`);
}

// -- Collect --

export function triggerCollect(data?: { pipeline_types?: string[]; hours_back?: number }) {
  return post<{ status: string; request_id: number }>('/api/collect', data);
}
