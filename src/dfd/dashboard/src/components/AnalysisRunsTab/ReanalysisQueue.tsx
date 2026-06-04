import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from '@patternfly/react-table';
import { EmptyState, EmptyStateBody, Label, Title } from '@patternfly/react-core';
import type { ReanalysisItem } from '../../api/types';
import { formatDate } from '../../utils/formatters';

interface ReanalysisQueueProps {
  items: ReanalysisItem[];
}

export default function ReanalysisQueue({ items }: ReanalysisQueueProps) {
  if (items.length === 0) {
    return (
      <EmptyState>
        <Title headingLevel="h4" size="lg">Queue empty</Title>
        <EmptyStateBody>No runs are queued for re-analysis.</EmptyStateBody>
      </EmptyState>
    );
  }

  return (
    <Table aria-label="Re-analysis queue" variant="compact">
      <Thead>
        <Tr>
          <Th>Pipeline Run</Th>
          <Th>Pipeline Type</Th>
          <Th>Reason</Th>
          <Th>Triggered By</Th>
          <Th>Status</Th>
          <Th>Created</Th>
        </Tr>
      </Thead>
      <Tbody>
        {items.map((item) => (
          <Tr key={item.id}>
            <Td><code>{item.pipeline_run_id}</code></Td>
            <Td>{item.pipeline_type_id}</Td>
            <Td>{item.reason}</Td>
            <Td>{item.triggered_by}</Td>
            <Td><Label color={item.status === 'pending' ? 'orange' : 'green'} isCompact>{item.status}</Label></Td>
            <Td>{formatDate(item.created_at)}</Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}
