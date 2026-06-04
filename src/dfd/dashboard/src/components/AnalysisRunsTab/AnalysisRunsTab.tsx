import {
  PageSection,
  Spinner,
  Bullseye,
  Title,
} from '@patternfly/react-core';
import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
} from '@patternfly/react-table';
import { useAnalysisRuns, useReanalysisQueue } from '../../hooks/useAnalysisRuns';
import ReanalysisQueue from './ReanalysisQueue';
import AnalysisRunRow from './AnalysisRunRow';

export default function AnalysisRunsTab() {
  const runsQuery = useAnalysisRuns(20);
  const queueQuery = useReanalysisQueue();

  return (
    <PageSection>
      <Title headingLevel="h3" style={{ marginBottom: '0.5rem' }}>Recent Analysis Runs</Title>

      {runsQuery.isLoading ? (
        <Bullseye><Spinner /></Bullseye>
      ) : runsQuery.data ? (
        <Table aria-label="Analysis runs" variant="compact">
          <Thead>
            <Tr>
              <Th screenReaderText="Expand" />
              <Th>ID</Th>
              <Th>Trigger</Th>
              <Th>Pipeline Types</Th>
              <Th>Status</Th>
              <Th>Runs</Th>
              <Th>Analyzed</Th>
              <Th>Cost</Th>
              <Th>Started</Th>
            </Tr>
          </Thead>
          <Tbody>
            {runsQuery.data.map((run) => (
              <AnalysisRunRow key={run.id} run={run} />
            ))}
          </Tbody>
        </Table>
      ) : null}

      <Title headingLevel="h3" style={{ marginTop: '2rem', marginBottom: '0.5rem' }}>Re-analysis Queue</Title>
      {queueQuery.isLoading ? (
        <Bullseye><Spinner /></Bullseye>
      ) : queueQuery.data ? (
        <ReanalysisQueue items={queueQuery.data} />
      ) : null}
    </PageSection>
  );
}
