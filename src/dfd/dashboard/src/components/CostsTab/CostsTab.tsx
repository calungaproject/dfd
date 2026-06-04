import { useState } from 'react';
import {
  PageSection,
  Spinner,
  Bullseye,
  Title,
  FormGroup,
  FormSelect,
  FormSelectOption,
} from '@patternfly/react-core';
import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from '@patternfly/react-table';
import { useCosts } from '../../hooks/useCosts';
import { formatDate, formatCost, formatTokens, formatDuration } from '../../utils/formatters';
import CostCards from './CostCards';
import CostChart from './CostChart';

const DAYS_OPTIONS = [7, 14, 30, 60, 90];

export default function CostsTab() {
  const [days, setDays] = useState(30);
  const costsQuery = useCosts(days);

  return (
    <PageSection>
      <FormGroup label="Period" fieldId="cost-days" style={{ maxWidth: 200, marginBottom: '1rem' }}>
        <FormSelect
          id="cost-days"
          value={String(days)}
          onChange={(_e, val) => setDays(Number(val))}
        >
          {DAYS_OPTIONS.map((d) => (
            <FormSelectOption key={d} value={String(d)} label={`Last ${d} days`} />
          ))}
        </FormSelect>
      </FormGroup>

      {costsQuery.isLoading ? (
        <Bullseye><Spinner /></Bullseye>
      ) : costsQuery.data ? (
        <>
          <CostCards data={costsQuery.data.by_type} />
          <div style={{ marginTop: '1rem' }}>
            <CostChart data={costsQuery.data.daily} />
          </div>

          <Title headingLevel="h3" style={{ marginTop: '2rem', marginBottom: '0.5rem' }}>Recent API Calls</Title>
          <Table aria-label="Recent API calls" variant="compact">
            <Thead>
              <Tr>
                <Th>Type</Th>
                <Th>Model</Th>
                <Th>Cost</Th>
                <Th>Input</Th>
                <Th>Output</Th>
                <Th>Cache Read</Th>
                <Th>Duration</Th>
                <Th>Time</Th>
              </Tr>
            </Thead>
            <Tbody>
              {costsQuery.data.recent.map((entry) => (
                <Tr key={entry.id}>
                  <Td>{entry.invocation_type}</Td>
                  <Td>{entry.model ?? '—'}</Td>
                  <Td>{formatCost(entry.cost_usd)}</Td>
                  <Td>{entry.input_tokens != null ? formatTokens(entry.input_tokens) : '—'}</Td>
                  <Td>{entry.output_tokens != null ? formatTokens(entry.output_tokens) : '—'}</Td>
                  <Td>{entry.cache_read_tokens != null ? formatTokens(entry.cache_read_tokens) : '—'}</Td>
                  <Td>{entry.duration_ms != null ? formatDuration(entry.duration_ms) : '—'}</Td>
                  <Td>{formatDate(entry.created_at)}</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </>
      ) : null}
    </PageSection>
  );
}
