import { useState } from 'react';
import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from '@patternfly/react-table';
import {
  EmptyState,
  EmptyStateBody,
  Title,
  Button,
  Label,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  Flex,
  FlexItem,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Alert,
} from '@patternfly/react-core';
import { AngleDownIcon, AngleRightIcon, PencilAltIcon, TrashIcon } from '@patternfly/react-icons';
import type { TaxonomyRule } from '../../api/types';
import { useUpdateRule, useDeleteRule } from '../../hooks/useTaxonomy';
import EditRuleModal from './EditRuleModal';

interface RulesTableProps {
  rules: TaxonomyRule[];
}

export default function RulesTable({ rules }: RulesTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [editingRule, setEditingRule] = useState<TaxonomyRule | null>(null);
  const [deletingRule, setDeletingRule] = useState<TaxonomyRule | null>(null);
  const [resultMessage, setResultMessage] = useState<string | null>(null);

  const updateMutation = useUpdateRule();
  const deleteMutation = useDeleteRule();

  if (rules.length === 0) {
    return (
      <EmptyState>
        <Title headingLevel="h4" size="lg">No taxonomy rules yet</Title>
        <EmptyStateBody>Rules will be proposed by the analysis agents.</EmptyStateBody>
      </EmptyState>
    );
  }

  function toggleRow(key: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleSave(data: Partial<TaxonomyRule>) {
    if (!editingRule) return;
    const { priority_rule, investigation_recipe, ...rest } = data;
    const cleaned = {
      ...rest,
      ...(priority_rule !== undefined && { priority_rule: priority_rule ?? '' }),
      ...(investigation_recipe !== undefined && { investigation_recipe: investigation_recipe ?? '' }),
    };
    updateMutation.mutate(
      {
        pipelineTypeId: editingRule.pipeline_type_id,
        ruleId: editingRule.id,
        data: cleaned,
      },
      {
        onSuccess: (resp) => {
          const queued = (resp as { reanalysis_queued?: number }).reanalysis_queued ?? 0;
          setEditingRule(null);
          setResultMessage(
            `Rule updated. ${queued} ${queued === 1 ? 'analysis' : 'analyses'} queued for re-analysis.`,
          );
          setTimeout(() => setResultMessage(null), 5000);
        },
      },
    );
  }

  function handleDelete() {
    if (!deletingRule) return;
    deleteMutation.mutate(
      {
        pipelineTypeId: deletingRule.pipeline_type_id,
        ruleId: deletingRule.id,
      },
      {
        onSuccess: (resp) => {
          const queued = (resp as { reanalysis_queued?: number }).reanalysis_queued ?? 0;
          setDeletingRule(null);
          setResultMessage(
            `Rule deleted. ${queued} ${queued === 1 ? 'analysis' : 'analyses'} queued for re-analysis.`,
          );
          setTimeout(() => setResultMessage(null), 5000);
        },
      },
    );
  }

  return (
    <>
      {resultMessage && (
        <Alert
          variant="success"
          title={resultMessage}
          isInline
          style={{ marginBottom: '0.5rem' }}
          actionClose={<Button variant="plain" onClick={() => setResultMessage(null)}>×</Button>}
        />
      )}
      <Table aria-label="Taxonomy rules" variant="compact">
        <Thead>
          <Tr>
            <Th width={10}></Th>
            <Th width={10}>#</Th>
            <Th width={10}>Pipeline Type</Th>
            <Th width={15}>Root Cause</Th>
            <Th width={10}>Category</Th>
            <Th width={25}>Error Signature</Th>
            <Th width={10}>Origin</Th>
            <Th width={10}>Actions</Th>
          </Tr>
        </Thead>
        <Tbody>
          {rules.map((r) => {
            const key = `${r.pipeline_type_id}-${r.id}`;
            const hasDetails = !!(r.investigation_recipe || r.priority_rule);
            const isExpanded = expandedIds.has(key);

            return (
              <>
                <Tr
                  key={key}
                  isClickable={hasDetails}
                  onRowClick={hasDetails ? () => toggleRow(key) : undefined}
                  style={{ cursor: hasDetails ? 'pointer' : 'default' }}
                >
                  <Td>
                    {hasDetails && (
                      <Button variant="plain" size="sm" aria-label="Details" onClick={(e) => { e.stopPropagation(); toggleRow(key); }}>
                        {isExpanded ? <AngleDownIcon /> : <AngleRightIcon />}
                      </Button>
                    )}
                  </Td>
                  <Td>{r.priority_order}</Td>
                  <Td><code>{r.pipeline_type_id}</code></Td>
                  <Td><code>{r.root_cause}</code></Td>
                  <Td>{r.category}</Td>
                  <Td>{r.error_signature}</Td>
                  <Td>
                    {r.origin === 'auto_consolidation' ? (
                      <Label color="purple" isCompact>auto</Label>
                    ) : (
                      r.origin
                    )}
                  </Td>
                  <Td>
                    <Flex spaceItems={{ default: 'spaceItemsSm' }}>
                      <FlexItem>
                        <Button
                          variant="plain"
                          size="sm"
                          aria-label="Edit rule"
                          onClick={(e) => { e.stopPropagation(); setEditingRule(r); }}
                        >
                          <PencilAltIcon />
                        </Button>
                      </FlexItem>
                      <FlexItem>
                        <Button
                          variant="plain"
                          size="sm"
                          aria-label="Delete rule"
                          isDanger
                          onClick={(e) => { e.stopPropagation(); setDeletingRule(r); }}
                        >
                          <TrashIcon />
                        </Button>
                      </FlexItem>
                    </Flex>
                  </Td>
                </Tr>
                {hasDetails && isExpanded && (
                  <Tr key={`${key}-detail`} isExpanded>
                    <Td colSpan={8} style={{ paddingLeft: '3rem' }}>
                      <DescriptionList isHorizontal isCompact>
                        {r.priority_rule && (
                          <DescriptionListGroup>
                            <DescriptionListTerm>Priority Rule</DescriptionListTerm>
                            <DescriptionListDescription>
                              <code>{r.priority_rule}</code>
                            </DescriptionListDescription>
                          </DescriptionListGroup>
                        )}
                        {r.investigation_recipe && (
                          <DescriptionListGroup>
                            <DescriptionListTerm>Investigation Recipe</DescriptionListTerm>
                            <DescriptionListDescription>
                              <pre style={{
                                whiteSpace: 'pre-wrap',
                                fontSize: '0.85em',
                                background: 'var(--pf-t--global--background--color--secondary--default)',
                                padding: '0.5rem',
                                borderRadius: '4px',
                              }}>
                                {r.investigation_recipe}
                              </pre>
                            </DescriptionListDescription>
                          </DescriptionListGroup>
                        )}
                      </DescriptionList>
                    </Td>
                  </Tr>
                )}
              </>
            );
          })}
        </Tbody>
      </Table>

      {editingRule && (
        <EditRuleModal
          rule={editingRule}
          isOpen
          onClose={() => setEditingRule(null)}
          onSave={handleSave}
          isSaving={updateMutation.isPending}
        />
      )}

      {deletingRule && (
        <Modal
          isOpen
          onClose={() => setDeletingRule(null)}
          variant="small"
          aria-label="Confirm delete"
        >
          <ModalHeader title="Delete taxonomy rule?" />
          <ModalBody>
            Delete rule <strong>#{deletingRule.id}</strong>{' '}
            (<code>{deletingRule.root_cause}</code>) from{' '}
            <code>{deletingRule.pipeline_type_id}</code>?
            Affected analyses will be queued for re-analysis.
          </ModalBody>
          <ModalFooter>
            <Button
              variant="danger"
              onClick={handleDelete}
              isLoading={deleteMutation.isPending}
              isDisabled={deleteMutation.isPending}
            >
              Delete
            </Button>
            <Button
              variant="link"
              onClick={() => setDeletingRule(null)}
              isDisabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
          </ModalFooter>
        </Modal>
      )}
    </>
  );
}
