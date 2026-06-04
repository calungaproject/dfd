import {
  Card,
  CardBody,
  Flex,
  FlexItem,
  Button,
  Content,
} from '@patternfly/react-core';
import type { RuleProposal } from '../../api/types';

interface ProposalCardProps {
  proposal: RuleProposal;
  onAccept: () => void;
  onReject: () => void;
  isAccepting: boolean;
  isRejecting: boolean;
}

export default function ProposalCard({
  proposal,
  onAccept,
  onReject,
  isAccepting,
  isRejecting,
}: ProposalCardProps) {
  return (
    <Card isCompact style={{ marginBottom: '0.5rem' }}>
      <CardBody>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
          <FlexItem>
            <strong><code>{proposal.root_cause}</code></strong>{' '}
            <span style={{ color: 'var(--pf-t--global--text--color--subtle)' }}>({proposal.category})</span>
          </FlexItem>
          <Flex spaceItems={{ default: 'spaceItemsSm' }}>
            <FlexItem>
              <Button variant="primary" size="sm" onClick={onAccept} isLoading={isAccepting} isDisabled={isAccepting || isRejecting}>
                Accept
              </Button>
            </FlexItem>
            <FlexItem>
              <Button variant="danger" size="sm" onClick={onReject} isLoading={isRejecting} isDisabled={isAccepting || isRejecting}>
                Reject
              </Button>
            </FlexItem>
          </Flex>
        </Flex>
        <Content component="small" style={{ color: 'var(--pf-t--global--text--color--subtle)', marginTop: '0.25rem' }}>
          {proposal.error_signature}
        </Content>
        {proposal.reasoning && (
          <Content component="small" style={{ color: 'var(--pf-t--global--text--color--subtle)', marginTop: '0.25rem' }}>
            {proposal.reasoning}
          </Content>
        )}
        {proposal.investigation_recipe && (
          <details style={{ marginTop: '0.5rem' }}>
            <summary style={{ cursor: 'pointer', fontSize: '0.85em', color: 'var(--pf-t--global--text--color--subtle)' }}>
              Investigation Recipe
            </summary>
            <pre style={{
              whiteSpace: 'pre-wrap',
              fontSize: '0.85em',
              background: 'var(--pf-t--global--background--color--secondary--default)',
              padding: '0.5rem',
              borderRadius: '4px',
              marginTop: '0.25rem',
            }}>
              {proposal.investigation_recipe}
            </pre>
          </details>
        )}
        {proposal.pipeline_run_id && (
          <Content component="small" style={{ color: 'var(--pf-t--global--text--color--subtle)', marginTop: '0.25rem' }}>
            From: <code>{proposal.pipeline_run_id}</code>
          </Content>
        )}
      </CardBody>
    </Card>
  );
}
