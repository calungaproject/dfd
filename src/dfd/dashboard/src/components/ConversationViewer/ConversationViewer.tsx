import { useState } from 'react';
import {
  PageSection,
  Toolbar,
  ToolbarContent,
  ToolbarItem,
  FormGroup,
  FormSelect,
  FormSelectOption,
  Spinner,
  Bullseye,
  Card,
  CardBody,
  CardTitle,
  Title,
  Label,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  EmptyState,
  EmptyStateBody,
  ExpandableSection,
  Flex,
  FlexItem,
  Icon,
} from '@patternfly/react-core';
import {
  ArrowRightIcon,
} from '@patternfly/react-icons';
import { useQuery } from '@tanstack/react-query';
import { fetchRuns, fetchConversation } from '../../api/client';
import type { PipelineRun, ConversationLog, ConversationAgent, BoardEntry } from '../../api/types';

const DAYS_OPTIONS = [7, 14, 30, 60, 90];

export default function ConversationViewer() {
  const [days, setDays] = useState(30);
  const [selectedRunId, setSelectedRunId] = useState<string>('');

  const runsQuery = useQuery({
    queryKey: ['failedRuns', days],
    queryFn: () => fetchRuns({ status: 'failed', days, per_page: 100 }),
    select: (data) => data.runs.filter((r: PipelineRun) => r.root_cause),
  });

  const conversationQuery = useQuery({
    queryKey: ['conversation', selectedRunId],
    queryFn: () => fetchConversation(selectedRunId),
    enabled: !!selectedRunId,
  });

  const failedRuns = runsQuery.data ?? [];

  return (
    <PageSection>
      <Toolbar>
        <ToolbarContent>
          <ToolbarItem>
            <FormGroup label="Time Range" fieldId="conv-days">
              <FormSelect
                id="conv-days"
                value={String(days)}
                onChange={(_e, val) => setDays(Number(val))}
              >
                {DAYS_OPTIONS.map((d) => (
                  <FormSelectOption key={d} value={String(d)} label={`Last ${d} days`} />
                ))}
              </FormSelect>
            </FormGroup>
          </ToolbarItem>
          <ToolbarItem>
            <FormGroup label="Pipeline Run" fieldId="conv-run">
              <FormSelect
                id="conv-run"
                value={selectedRunId}
                onChange={(_e, val) => setSelectedRunId(val)}
              >
                <FormSelectOption value="" label="Select a failed run..." />
                {failedRuns.map((r) => (
                  <FormSelectOption
                    key={r.id}
                    value={r.id}
                    label={`${r.id.slice(0, 40)}... — ${r.root_cause ?? 'unknown'}`}
                  />
                ))}
              </FormSelect>
            </FormGroup>
          </ToolbarItem>
        </ToolbarContent>
      </Toolbar>

      {!selectedRunId && (
        <EmptyState>
          <Title headingLevel="h4" size="lg">Select a Pipeline Run</Title>
          <EmptyStateBody>
            Choose a failed pipeline run above to view the full agent conversation log.
          </EmptyStateBody>
        </EmptyState>
      )}

      {selectedRunId && conversationQuery.isLoading && (
        <Bullseye><Spinner /></Bullseye>
      )}

      {selectedRunId && conversationQuery.error && (
        <EmptyState>
          <Title headingLevel="h4" size="lg">Conversation Not Available</Title>
          <EmptyStateBody>
            No conversation log found for this pipeline run. It may not have been analyzed yet.
          </EmptyStateBody>
        </EmptyState>
      )}

      {selectedRunId && conversationQuery.data && (
        <ConversationDetail log={conversationQuery.data} />
      )}
    </PageSection>
  );
}

function ConversationDetail({ log }: { log: ConversationLog }) {
  const conv = log.conversation;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
      {/* Agent flow */}
      <Card>
        <CardTitle>Analysis Overview</CardTitle>
        <CardBody>
          <DescriptionList isHorizontal>
            <DescriptionListGroup>
              <DescriptionListTerm>Pipeline Run</DescriptionListTerm>
              <DescriptionListDescription>
                <code>{log.pipeline_run_id}</code>
              </DescriptionListDescription>
            </DescriptionListGroup>
            <DescriptionListGroup>
              <DescriptionListTerm>Analysis Version</DescriptionListTerm>
              <DescriptionListDescription>{log.analysis_version}</DescriptionListDescription>
            </DescriptionListGroup>
            <DescriptionListGroup>
              <DescriptionListTerm>Agent Flow</DescriptionListTerm>
              <DescriptionListDescription>
                <AgentFlow agents={conv.agents} />
              </DescriptionListDescription>
            </DescriptionListGroup>
            {conv.agents.length > 0 && (() => {
              const synthesis = conv.agents.find(a => a.agent === 'manager_synthesis');
              if (!synthesis) return null;
              return (
                <>
                  <DescriptionListGroup>
                    <DescriptionListTerm>Root Cause</DescriptionListTerm>
                    <DescriptionListDescription>
                      <Label color="red">{synthesis.root_cause}</Label>
                    </DescriptionListDescription>
                  </DescriptionListGroup>
                  {synthesis.category && (
                    <DescriptionListGroup>
                      <DescriptionListTerm>Category</DescriptionListTerm>
                      <DescriptionListDescription>
                        <Label color="grey">{synthesis.category}</Label>
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                  )}
                  {synthesis.confidence != null && (
                    <DescriptionListGroup>
                      <DescriptionListTerm>Confidence</DescriptionListTerm>
                      <DescriptionListDescription>
                        <ConfidenceBadge confidence={synthesis.confidence} />
                      </DescriptionListDescription>
                    </DescriptionListGroup>
                  )}
                </>
              );
            })()}
          </DescriptionList>
        </CardBody>
      </Card>

      {/* Board entries — the detailed agent analysis */}
      {conv.board_entries.map((entry) => (
        <BoardEntryCard key={entry.id} entry={entry} />
      ))}
    </div>
  );
}

function AgentFlow({ agents }: { agents: ConversationAgent[] }) {
  return (
    <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }}>
      {agents.map((agent, i) => (
        <Flex key={i} alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }}>
          {i > 0 && (
            <FlexItem>
              <Icon size="sm">
                <ArrowRightIcon color="var(--pf-t--global--text--color--subtle)" />
              </Icon>
            </FlexItem>
          )}
          <FlexItem>
            <Label color={agent.agent.includes('triage') ? 'blue' : agent.agent.includes('synthesis') ? 'purple' : 'teal'}>
              {agent.agent}
            </Label>
          </FlexItem>
          {agent.specialists && agent.specialists.length > 0 && (
            <FlexItem>
              <span style={{ fontSize: '0.82rem', color: 'var(--pf-t--global--text--color--subtle)' }}>
                (specialists: {agent.specialists.join(', ')})
              </span>
            </FlexItem>
          )}
        </Flex>
      ))}
    </Flex>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string | number }) {
  const numVal = typeof confidence === 'number' ? confidence : (confidence === 'high' ? 95 : confidence === 'medium' ? 70 : 40);
  const color = numVal >= 80 ? 'green' : numVal >= 60 ? 'yellow' : 'orange';
  const display = typeof confidence === 'number' ? `${confidence}%` : confidence;
  return <Label color={color}>{display}</Label>;
}

function BoardEntryCard({ entry }: { entry: BoardEntry }) {
  const agentColor = entry.agent_type.includes('triage') ? 'blue'
    : entry.agent_type.includes('log') ? 'teal'
    : entry.agent_type.includes('historical') ? 'orange'
    : 'purple';

  return (
    <Card>
      <CardTitle>
        <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsMd' }}>
          <FlexItem>
            <Label color={agentColor}>{entry.agent_type}</Label>
          </FlexItem>
          {entry.classification_suggestion && (
            <FlexItem>
              <Label color="red">{entry.classification_suggestion}</Label>
            </FlexItem>
          )}
          {entry.confidence && (
            <FlexItem>
              <ConfidenceBadge confidence={entry.confidence} />
            </FlexItem>
          )}
          <FlexItem>
            <span style={{ fontSize: '0.82rem', color: 'var(--pf-t--global--text--color--subtle)' }}>
              {new Date(entry.created_at).toLocaleString()}
            </span>
          </FlexItem>
        </Flex>
      </CardTitle>
      <CardBody>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {/* Findings */}
          <div>
            <Title headingLevel="h5" size="md" style={{ marginBottom: '0.5rem' }}>Findings</Title>
            <div style={{
              whiteSpace: 'pre-wrap',
              fontSize: '0.9rem',
              lineHeight: '1.6',
              padding: '0.75rem',
              borderRadius: '6px',
              background: 'var(--pf-t--global--background--color--secondary--default)',
            }}>
              {entry.findings}
            </div>
          </div>

          {/* Evidence */}
          {entry.evidence && (
            <div>
              <Title headingLevel="h5" size="md" style={{ marginBottom: '0.5rem' }}>Evidence</Title>
              <pre style={{
                fontSize: '0.82rem',
                whiteSpace: 'pre-wrap',
                padding: '0.75rem',
                borderRadius: '6px',
                background: 'var(--pf-t--global--background--color--secondary--default)',
                maxHeight: '400px',
                overflowY: 'auto',
              }}>
                {entry.evidence}
              </pre>
            </div>
          )}

          {/* Thinking — collapsible */}
          {entry.thinking && (
            <ExpandableSection toggleText="Agent Thinking" isIndented>
              <pre style={{
                fontSize: '0.82rem',
                whiteSpace: 'pre-wrap',
                lineHeight: '1.5',
                maxHeight: '500px',
                overflowY: 'auto',
                padding: '0.75rem',
                borderRadius: '6px',
                background: 'var(--pf-t--global--background--color--secondary--default)',
              }}>
                {entry.thinking}
              </pre>
            </ExpandableSection>
          )}

          {/* Flags */}
          {entry.flags && (
            <div>
              <Label color="yellow">{entry.flags}</Label>
            </div>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
