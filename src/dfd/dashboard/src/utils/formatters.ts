export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatToolCall(name: string, input?: Record<string, unknown>): string {
  const i = input ?? {};
  switch (name) {
    case 'get_analysis_details':
      return `Fetching analysis for ${i.pipeline_run_id ?? 'run'}`;
    case 'read_artifact':
      return `Reading ${i.artifact_type ?? 'artifact'} for ${i.pipeline_run_id ?? 'run'}`;
    case 'get_investigation_board':
      return `Loading investigation board for ${i.pipeline_run_id ?? 'run'}`;
    case 'get_conversation_log':
      return `Fetching conversation log for ${i.pipeline_run_id ?? 'run'}`;
    case 'query_pipeline_runs': {
      const parts: string[] = [];
      if (i.status) parts.push(String(i.status));
      if (i.pipeline_type_id) parts.push(String(i.pipeline_type_id));
      if (i.root_cause) parts.push(`root_cause=${i.root_cause}`);
      return parts.length ? `Querying runs: ${parts.join(', ')}` : 'Querying pipeline runs';
    }
    case 'get_statistics':
      return `Fetching statistics${i.pipeline_type_id ? ` for ${i.pipeline_type_id}` : ''}`;
    case 'get_taxonomy_rules':
      return `Loading taxonomy for ${i.pipeline_type_id ?? 'pipeline type'}`;
    case 'get_pending_proposals':
      return `Checking pending proposals for ${i.pipeline_type_id ?? 'pipeline type'}`;
    case 'update_taxonomy_rule':
      return `Updating taxonomy rule #${i.rule_id ?? ''}`;
    case 'delete_taxonomy_rule':
      return `Deleting taxonomy rule #${i.rule_id ?? ''}`;
    case 'merge_taxonomy_rules':
      return `Merging taxonomy rules #${i.source_rule_id ?? ''} into #${i.target_rule_id ?? ''}`;
    case 'accept_proposal':
      return `Accepting proposal #${i.proposal_id ?? ''}`;
    case 'reject_proposal':
      return `Rejecting proposal #${i.proposal_id ?? ''}`;
    default:
      return `Calling ${name}`;
  }
}
