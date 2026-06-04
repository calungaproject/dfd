import { useState } from 'react';
import {
  Label,
  Button,
  Spinner,
  Title,
} from '@patternfly/react-core';
import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from '@patternfly/react-table';
import { AngleDownIcon, AngleRightIcon } from '@patternfly/react-icons';
import type { AnalysisRun } from '../../api/types';
import { useAnalysisRunDetail } from '../../hooks/useAnalysisRuns';
import { formatDate, formatCost } from '../../utils/formatters';

const STATUS_COLORS: Record<string, 'green' | 'blue' | 'red' | 'orange'> = {
  completed: 'green',
  running: 'blue',
  failed: 'red',
  pending: 'orange',
};

const CATEGORY_COLORS: Record<string, 'orange' | 'blue' | 'grey'> = {
  build: 'blue',
  infra: 'orange',
  unknown: 'grey',
};

const PROPOSAL_STATUS_COLORS: Record<string, 'green' | 'red' | 'grey' | 'orange'> = {
  accepted: 'green',
  rejected: 'red',
  duplicate: 'grey',
  pending: 'orange',
};

interface Props {
  run: AnalysisRun;
}

export default function AnalysisRunRow({ run }: Props) {
  const [expanded, setExpanded] = useState(false);
  const detailQuery = useAnalysisRunDetail(expanded ? run.id : undefined);

  return (
    <>
      <Tr
        isClickable
        onRowClick={() => setExpanded(!expanded)}
        style={{ cursor: 'pointer' }}
      >
        <Td>
          <Button variant="plain" size="sm" aria-label="Details" onClick={() => setExpanded(!expanded)}>
            {expanded ? <AngleDownIcon /> : <AngleRightIcon />}
          </Button>
        </Td>
        <Td>{run.id}</Td>
        <Td>{run.trigger}</Td>
        <Td>{run.pipeline_types?.join(', ')}</Td>
        <Td>
          <Label color={STATUS_COLORS[run.status] ?? 'grey'} isCompact>
            {run.status}
          </Label>
        </Td>
        <Td>{run.total_pipeline_runs ?? '—'}</Td>
        <Td>{run.analyzed_count ?? '—'}</Td>
        <Td>{run.total_cost_usd != null ? formatCost(run.total_cost_usd) : '—'}</Td>
        <Td>{formatDate(run.started_at)}</Td>
      </Tr>

      {expanded && (
        <Tr isExpanded>
          <Td colSpan={9} style={{ paddingLeft: '3rem' }}>
            {detailQuery.isLoading ? (
              <Spinner size="md" />
            ) : detailQuery.data ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '0.5rem 0' }}>
                {/* Pipeline Runs */}
                {(detailQuery.data.pipeline_runs?.length ?? 0) > 0 && (
                  <div>
                    <Title headingLevel="h4" size="md" style={{ marginBottom: '0.5rem' }}>
                      Pipeline Runs Processed ({detailQuery.data.pipeline_runs?.length ?? 0})
                    </Title>
                    <Table aria-label="Pipeline runs" variant="compact" borders={false}>
                      <Thead>
                        <Tr>
                          <Th>Pipeline Run</Th>
                          <Th>Pipeline Type</Th>
                          <Th>Type</Th>
                          <Th>Root Cause</Th>
                          <Th>Category</Th>
                          <Th>Confidence</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {detailQuery.data.pipeline_runs.map((pr) => (
                          <Tr key={pr.id}>
                            <Td>
                              <code style={{ fontSize: '0.85em' }}>{pr.id}</code>
                            </Td>
                            <Td><code>{pr.pipeline_type_id}</code></Td>
                            <Td>
                              {pr.event_type === 'pull_request' ? (
                                <Label color="blue" isCompact>PR</Label>
                              ) : pr.event_type === 'push' ? (
                                <Label color="grey" isCompact>push</Label>
                              ) : null}
                            </Td>
                            <Td>
                              {pr.root_cause ? (
                                <Label color="orange" isCompact>{pr.root_cause}</Label>
                              ) : '—'}
                            </Td>
                            <Td>
                              {pr.category ? (
                                <Label color={CATEGORY_COLORS[pr.category] ?? 'grey'} isCompact>
                                  {pr.category}
                                </Label>
                              ) : '—'}
                            </Td>
                            <Td>{pr.confidence != null ? `${pr.confidence}%` : '—'}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </div>
                )}

                {(detailQuery.data.pipeline_runs?.length ?? 0) === 0 && (
                  <div style={{ color: 'var(--pf-t--global--color--nonstatus--gray--default)' }}>
                    No pipeline runs processed in this analysis run.
                  </div>
                )}

                {/* Taxonomy Changes */}
                {(detailQuery.data.taxonomy_changes?.length ?? 0) > 0 && (
                  <div>
                    <Title headingLevel="h4" size="md" style={{ marginBottom: '0.5rem' }}>
                      Taxonomy Changes ({detailQuery.data.taxonomy_changes?.length ?? 0})
                    </Title>
                    <Table aria-label="Taxonomy changes" variant="compact" borders={false}>
                      <Thead>
                        <Tr>
                          <Th>Status</Th>
                          <Th>Root Cause</Th>
                          <Th>Category</Th>
                          <Th>Pipeline Type</Th>
                          <Th>Reasoning</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {detailQuery.data.taxonomy_changes.map((tc) => (
                          <Tr key={tc.id}>
                            <Td>
                              <Label color={PROPOSAL_STATUS_COLORS[tc.status] ?? 'grey'} isCompact>
                                {tc.status}
                              </Label>
                            </Td>
                            <Td><code>{tc.root_cause}</code></Td>
                            <Td>
                              <Label color={CATEGORY_COLORS[tc.category] ?? 'grey'} isCompact>
                                {tc.category}
                              </Label>
                            </Td>
                            <Td><code>{tc.pipeline_type_id}</code></Td>
                            <Td>
                              {tc.reasoning ? (
                                <span style={{ fontSize: '0.85em' }}>
                                  {tc.reasoning.length > 120
                                    ? `${tc.reasoning.slice(0, 120)}...`
                                    : tc.reasoning}
                                </span>
                              ) : '—'}
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </div>
                )}

                {/* Error message */}
                {detailQuery.data.error_message && (
                  <div>
                    <Title headingLevel="h4" size="md" style={{ marginBottom: '0.25rem' }}>Error</Title>
                    <code style={{ color: 'var(--pf-t--global--color--status--danger--default)' }}>
                      {detailQuery.data.error_message}
                    </code>
                  </div>
                )}
              </div>
            ) : null}
          </Td>
        </Tr>
      )}
    </>
  );
}
