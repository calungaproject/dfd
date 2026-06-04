import { useState } from 'react';
import {
  PageSection,
  FormGroup,
  FormSelect,
  FormSelectOption,
  Spinner,
  Bullseye,
  Title,
  EmptyState,
  EmptyStateBody,
} from '@patternfly/react-core';
import { useTaxonomyRules, useTaxonomyProposals, useAcceptProposal, useRejectProposal } from '../../hooks/useTaxonomy';
import { usePipelineTypes } from '../../hooks/usePipelineTypes';
import RulesTable from './RulesTable';
import ProposalCard from './ProposalCard';

export default function TaxonomyTab() {
  const [pipelineType, setPipelineType] = useState('');
  const pipelineTypesQuery = usePipelineTypes();
  const rulesQuery = useTaxonomyRules(pipelineType);
  const proposalsQuery = useTaxonomyProposals(pipelineType);
  const acceptMutation = useAcceptProposal();
  const rejectMutation = useRejectProposal();

  return (
    <PageSection>
      <FormGroup label="Pipeline Type" fieldId="taxonomy-pipeline-type" style={{ maxWidth: 300, marginBottom: '1rem' }}>
        <FormSelect
          id="taxonomy-pipeline-type"
          value={pipelineType}
          onChange={(_e, val) => setPipelineType(val)}
        >
          <FormSelectOption value="" label="All pipeline types" />
          {(pipelineTypesQuery.data ?? []).map((pt) => (
            <FormSelectOption key={pt.id} value={pt.id} label={pt.display_name} />
          ))}
        </FormSelect>
      </FormGroup>

      <Title headingLevel="h3" style={{ marginBottom: '0.5rem' }}>Rules</Title>
      {rulesQuery.isLoading ? (
        <Bullseye><Spinner /></Bullseye>
      ) : rulesQuery.data ? (
        <RulesTable rules={rulesQuery.data} />
      ) : null}

      <Title headingLevel="h3" style={{ marginTop: '2rem', marginBottom: '0.5rem' }}>Proposals</Title>
      {proposalsQuery.isLoading ? (
        <Bullseye><Spinner /></Bullseye>
      ) : proposalsQuery.data && proposalsQuery.data.length > 0 ? (
        proposalsQuery.data.map((p) => (
          <ProposalCard
            key={p.id}
            proposal={p}
            onAccept={() => acceptMutation.mutate({ pipelineTypeId: pipelineType || p.pipeline_type_id, proposalId: p.id })}
            onReject={() => rejectMutation.mutate({ pipelineTypeId: pipelineType || p.pipeline_type_id, proposalId: p.id })}
            isAccepting={acceptMutation.isPending && acceptMutation.variables?.proposalId === p.id}
            isRejecting={rejectMutation.isPending && rejectMutation.variables?.proposalId === p.id}
          />
        ))
      ) : (
        <EmptyState>
          <Title headingLevel="h4" size="lg">No pending proposals</Title>
          <EmptyStateBody>New proposals will appear here when analysis agents suggest new taxonomy rules.</EmptyStateBody>
        </EmptyState>
      )}
    </PageSection>
  );
}
