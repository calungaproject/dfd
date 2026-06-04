import { useState } from 'react';
import {
  Label,
  Button,
  Flex,
  FlexItem,
  Tooltip,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  Spinner,
  Title,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Alert,
} from '@patternfly/react-core';
import { AngleDownIcon, AngleRightIcon } from '@patternfly/react-icons';
import { Tr, Td } from '@patternfly/react-table';
import type { PipelineRun } from '../../api/types';
import { useRunDetail, useReanalyzeRun } from '../../hooks/useRuns';
import { formatDate } from '../../utils/formatters';

interface RunRowProps {
  run: PipelineRun;
  onAskAboutRun: (pipelineRunId: string) => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
}

const STATUS_COLORS: Record<string, 'green' | 'red' | 'orange' | 'grey'> = {
  succeeded: 'green',
  failed: 'red',
  aborted: 'orange',
};

const CONFIDENCE_COLORS: Record<string, 'green' | 'yellow' | 'red'> = {
  high: 'green',
  medium: 'yellow',
  low: 'red',
};

function confidenceLevel(c: number): 'high' | 'medium' | 'low' {
  if (c >= 80) return 'high';
  if (c >= 50) return 'medium';
  return 'low';
}

const PIPELINE_TYPE_COLORS: Record<string, 'blue' | 'teal' | 'purple' | 'yellow'> = {
  build: 'blue',
  integration_test: 'teal',
  enterprise_contract: 'purple',
  release: 'yellow',
};

const AGENT_LABELS: Record<string, string> = {
  manager_triage: 'Manager Triage',
  log_analyst: 'Log Analyst',
  historical_analyst: 'Historical Analyst',
  manager_synthesis: 'Manager Synthesis',
};

const PRE_STYLE = {
  whiteSpace: 'pre-wrap' as const,
  fontSize: '0.85em',
  background: 'var(--pf-t--global--background--color--secondary--default)',
  padding: '0.5rem',
  borderRadius: '4px',
};

export default function RunRow({ run, onAskAboutRun, isExpanded, onToggleExpand }: RunRowProps) {
  const [showInvestigation, setShowInvestigation] = useState(false);
  const [showReanalyzeConfirm, setShowReanalyzeConfirm] = useState(false);
  const [reanalyzeSuccess, setReanalyzeSuccess] = useState(false);
  const reanalyzeMutation = useReanalyzeRun();
  const isFailed = run.status === 'failed';
  const expanded = isFailed && isExpanded;
  const detailQuery = useRunDetail(expanded ? run.id : undefined);

  return (
    <>
      <Tr
        isClickable={isFailed}
        onRowClick={isFailed ? () => onToggleExpand() : undefined}
        style={{ cursor: isFailed ? 'pointer' : 'default' }}
      >
        <Td>
          {isFailed && (
            <Button variant="plain" size="sm" aria-label="Details" onClick={() => onToggleExpand()}>
              {expanded ? <AngleDownIcon /> : <AngleRightIcon />}
            </Button>
          )}
        </Td>
        <Td>
          <Label color={STATUS_COLORS[run.status] ?? 'grey'} isCompact>{run.status}</Label>
        </Td>
        <Td>
          {run.pipeline_url ? (
            <a href={run.pipeline_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.9em' }}>{run.id}</a>
          ) : (
            <span style={{ fontSize: '0.9em' }}>{run.id}</span>
          )}
        </Td>
        <Td>
          {run.package_name ? (
            run.source_url ? (
              <a href={run.source_url} target="_blank" rel="noopener noreferrer">{run.package_name}</a>
            ) : run.package_name
          ) : ''}
        </Td>
        <Td>
          {isFailed && run.root_cause && (
            <Flex spaceItems={{ default: 'spaceItemsSm' }} alignItems={{ default: 'alignItemsCenter' }} flexWrap={{ default: 'nowrap' }}>
              <FlexItem>
                {run.taxonomy_matched === false ? (
                  <Tooltip content="Novel classification — not in taxonomy">
                    <Label color="purple" isCompact>* {run.root_cause}</Label>
                  </Tooltip>
                ) : (
                  <Label color="orange" isCompact>{run.root_cause}</Label>
                )}
              </FlexItem>
              {run.confidence != null && (
                <FlexItem>
                  <Label color={CONFIDENCE_COLORS[confidenceLevel(run.confidence)]} isCompact>
                    {run.confidence}%
                  </Label>
                </FlexItem>
              )}
            </Flex>
          )}
        </Td>
        <Td>
          <Label color={PIPELINE_TYPE_COLORS[run.pipeline_type_id] ?? 'grey'} isCompact>
            {run.pipeline_type_id}
          </Label>
        </Td>
        <Td>{formatDate(run.completion_time)}</Td>
        <Td>{isFailed && run.failed_task ? <small>{run.failed_task}</small> : null}</Td>
      </Tr>

      {isFailed && expanded && (
        <Tr isExpanded>
          <Td colSpan={8} style={{ paddingLeft: '3rem' }}>
            <DescriptionList isHorizontal isCompact>
              {run.package_name && (
                <DescriptionListGroup>
                  <DescriptionListTerm>Package</DescriptionListTerm>
                  <DescriptionListDescription>
                    {run.source_url ? (
                      <a href={run.source_url} target="_blank" rel="noopener noreferrer">
                        {run.package_name}{run.package_version ? ` ${run.package_version}` : ''}
                      </a>
                    ) : (
                      <>{run.package_name}{run.package_version ? ` ${run.package_version}` : ''}</>
                    )}
                  </DescriptionListDescription>
                </DescriptionListGroup>
              )}
              {run.target_os && (
                <DescriptionListGroup>
                  <DescriptionListTerm>Target OS</DescriptionListTerm>
                  <DescriptionListDescription>{run.target_os}</DescriptionListDescription>
                </DescriptionListGroup>
              )}
              {run.error_message && (
                <DescriptionListGroup>
                  <DescriptionListTerm>Error</DescriptionListTerm>
                  <DescriptionListDescription>
                    <code>{run.error_message}</code>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              )}
              {run.ambiguity_note && (
                <DescriptionListGroup>
                  <DescriptionListTerm>Ambiguity</DescriptionListTerm>
                  <DescriptionListDescription>
                    {run.ambiguity_note}
                    {run.alternative_root_cause && (
                      <> (alternative: <code>{run.alternative_root_cause}</code> at {run.alternative_confidence ?? '?'}%)</>
                    )}
                  </DescriptionListDescription>
                </DescriptionListGroup>
              )}
              {run.evidence && (
                <DescriptionListGroup>
                  <DescriptionListTerm>Evidence</DescriptionListTerm>
                  <DescriptionListDescription>
                    <pre style={PRE_STYLE}>{run.evidence}</pre>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              )}
              {run.details && (
                <DescriptionListGroup>
                  <DescriptionListTerm>Details</DescriptionListTerm>
                  <DescriptionListDescription>{run.details}</DescriptionListDescription>
                </DescriptionListGroup>
              )}
              {run.suggested_action && (
                <DescriptionListGroup>
                  <DescriptionListTerm>Suggested Action</DescriptionListTerm>
                  <DescriptionListDescription>
                    <strong>{run.suggested_action}</strong>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              )}
              {run.remediation && run.remediation !== 'N/A' && (
                <DescriptionListGroup>
                  <DescriptionListTerm>Remediation</DescriptionListTerm>
                  <DescriptionListDescription>
                    <pre style={PRE_STYLE}>{run.remediation}</pre>
                  </DescriptionListDescription>
                </DescriptionListGroup>
              )}
            </DescriptionList>
            {reanalyzeSuccess && (
              <Alert
                variant="success"
                isInline
                isPlain
                title="Re-analysis queued — will be processed on the next collector run."
                style={{ marginTop: '0.5rem' }}
              />
            )}
            <Flex style={{ marginTop: '1rem' }} spaceItems={{ default: 'spaceItemsSm' }}>
              <FlexItem>
                <Button
                  variant="tertiary"
                  size="sm"
                  onClick={() => setShowInvestigation(!showInvestigation)}
                >
                  {showInvestigation ? 'Hide' : 'Show'} Investigation
                </Button>
              </FlexItem>
              <FlexItem>
                <Button
                  variant="tertiary"
                  size="sm"
                  onClick={() => setShowReanalyzeConfirm(true)}
                  isDisabled={reanalyzeMutation.isPending || reanalyzeSuccess}
                  isLoading={reanalyzeMutation.isPending}
                >
                  Re-analyze
                </Button>
              </FlexItem>
              <FlexItem>
                <Button
                  variant="tertiary"
                  size="sm"
                  onClick={() => { window.location.hash = `#/conversations?run=${run.id}`; }}
                >
                  View Conversation
                </Button>
              </FlexItem>
              <FlexItem style={{ marginLeft: 'auto' }}>
                <Button variant="secondary" size="sm" onClick={() => onAskAboutRun(run.id)}>
                  Ask AI about this failure
                </Button>
              </FlexItem>
            </Flex>

            {showReanalyzeConfirm && (
              <Modal isOpen onClose={() => setShowReanalyzeConfirm(false)} variant="small">
                <ModalHeader title="Re-analyze this pipeline run?" />
                <ModalBody>
                  Queue <code>{run.id}</code> for re-analysis. The failure will be re-analyzed
                  with the current taxonomy rules and agent configuration on the next collector run.
                </ModalBody>
                <ModalFooter>
                  <Button
                    variant="primary"
                    onClick={() => {
                      reanalyzeMutation.mutate(run.id, {
                        onSuccess: () => {
                          setShowReanalyzeConfirm(false);
                          setReanalyzeSuccess(true);
                          setTimeout(() => setReanalyzeSuccess(false), 5000);
                        },
                      });
                    }}
                    isLoading={reanalyzeMutation.isPending}
                    isDisabled={reanalyzeMutation.isPending}
                  >
                    Re-analyze
                  </Button>
                  <Button
                    variant="link"
                    onClick={() => setShowReanalyzeConfirm(false)}
                    isDisabled={reanalyzeMutation.isPending}
                  >
                    Cancel
                  </Button>
                </ModalFooter>
              </Modal>
            )}

            {showInvestigation && (
              <div style={{ marginTop: '1rem' }}>
                {detailQuery.isLoading ? (
                  <Spinner size="md" />
                ) : detailQuery.data?.board_entries && detailQuery.data.board_entries.length > 0 ? (
                  <>
                    <Title headingLevel="h5" size="md" style={{ marginBottom: '0.5rem' }}>
                      Investigation Board ({detailQuery.data.board_entries.length} entries)
                    </Title>
                    {detailQuery.data.board_entries.map((entry) => (
                      <details
                        key={entry.id}
                        style={{
                          marginBottom: '0.75rem',
                          background: 'var(--pf-t--global--background--color--secondary--default)',
                          borderRadius: '4px',
                          borderLeft: '3px solid var(--pf-t--global--border--color--default)',
                        }}
                      >
                        <summary style={{ cursor: 'pointer', padding: '0.75rem' }}>
                          <Flex
                            display={{ default: 'inlineFlex' }}
                            spaceItems={{ default: 'spaceItemsSm' }}
                            alignItems={{ default: 'alignItemsCenter' }}
                          >
                            <FlexItem>
                              <Label color="blue" isCompact>
                                {AGENT_LABELS[entry.agent_type] ?? entry.agent_type}
                              </Label>
                            </FlexItem>
                            {entry.classification_suggestion && (
                              <FlexItem>
                                <Label color="orange" isCompact>
                                  {entry.classification_suggestion}
                                  {entry.confidence ? ` (${entry.confidence})` : ''}
                                </Label>
                              </FlexItem>
                            )}
                            {entry.flags && (
                              <FlexItem>
                                <Label color="red" isCompact>{entry.flags}</Label>
                              </FlexItem>
                            )}
                          </Flex>
                        </summary>
                        <div style={{ padding: '0 0.75rem 0.75rem' }}>
                          <pre style={PRE_STYLE}>{entry.findings}</pre>
                          {entry.evidence && (
                            <details style={{ marginTop: '0.5rem' }}>
                              <summary style={{ cursor: 'pointer', fontSize: '0.85em' }}>Evidence</summary>
                              <pre style={{ ...PRE_STYLE, marginTop: '0.25rem' }}>{entry.evidence}</pre>
                            </details>
                          )}
                          {entry.thinking && (
                            <details style={{ marginTop: '0.5rem' }}>
                              <summary style={{ cursor: 'pointer', fontSize: '0.85em' }}>Thinking</summary>
                              <pre style={{ ...PRE_STYLE, marginTop: '0.25rem' }}>{entry.thinking}</pre>
                            </details>
                          )}
                        </div>
                      </details>
                    ))}
                    {detailQuery.data.thinking && (
                      <>
                        <Title headingLevel="h5" size="md" style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
                          Manager Synthesis Thinking
                        </Title>
                        <pre style={PRE_STYLE}>{detailQuery.data.thinking}</pre>
                      </>
                    )}
                  </>
                ) : (
                  <em>No investigation board entries available.</em>
                )}
              </div>
            )}
          </Td>
        </Tr>
      )}
    </>
  );
}
