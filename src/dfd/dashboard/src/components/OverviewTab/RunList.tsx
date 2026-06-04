import { useRef, useEffect, useCallback } from 'react';
import {
  Flex,
  FlexItem,
  SearchInput,
  ToggleGroup,
  ToggleGroupItem,
  EmptyState,
  EmptyStateBody,
  Spinner,
  Title,
} from '@patternfly/react-core';
import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
} from '@patternfly/react-table';
import type { PipelineRun, RunsCounts } from '../../api/types';
import RunRow from './RunRow';

type Filter = 'all' | 'failed' | 'succeeded' | 'aborted' | 'unknown' | 'novel';

const VALID_FILTERS: readonly string[] = ['all', 'failed', 'succeeded', 'aborted', 'unknown', 'novel'];

interface RunListProps {
  runs: PipelineRun[];
  total: number;
  counts: RunsCounts;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
  onAskAboutRun: (pipelineRunId: string) => void;
  activeFilter: string;
  onFilterChange: (filter: string) => void;
  rootCauseSearch: string;
  onRootCauseSearchChange: (value: string) => void;
  expandedRunId: string;
  onExpandRun: (runId: string) => void;
}

export default function RunList({ runs, total, counts, hasNextPage, isFetchingNextPage, fetchNextPage, onAskAboutRun, activeFilter, onFilterChange, rootCauseSearch, onRootCauseSearchChange, expandedRunId, onExpandRun }: RunListProps) {
  const filter: Filter = VALID_FILTERS.includes(activeFilter) ? (activeFilter as Filter) : 'all';

  const sentinelRef = useRef<HTMLDivElement>(null);

  const handleIntersect = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    [hasNextPage, isFetchingNextPage, fetchNextPage],
  );

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(handleIntersect, {
      rootMargin: '200px',
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [handleIntersect]);

  return (
    <>
      <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsMd' }} style={{ marginBottom: '1rem' }}>
        <FlexItem>
          <ToggleGroup aria-label="Run status filter">
            {(['all', 'failed', 'succeeded', 'aborted', 'unknown', 'novel'] as const).map((f) => (
              <ToggleGroupItem
                key={f}
                text={`${f.charAt(0).toUpperCase() + f.slice(1)} (${counts[f]})`}
                isSelected={filter === f}
                onChange={() => onFilterChange(f)}
              />
            ))}
          </ToggleGroup>
        </FlexItem>
        <FlexItem>
          <SearchInput
            placeholder="Filter by root cause..."
            value={rootCauseSearch}
            onChange={(_e, value) => onRootCauseSearchChange(value)}
            onClear={() => onRootCauseSearchChange('')}
            resultsCount={rootCauseSearch && rootCauseSearch.length >= 3 ? `${total}` : undefined}
            style={{ minWidth: '250px' }}
          />
        </FlexItem>
        {runs.length < total && (
          <FlexItem>
            <span style={{ fontSize: '0.85em', color: 'var(--pf-t--global--color--nonstatus--gray--default)' }}>
              Loaded {runs.length} of {total}
            </span>
          </FlexItem>
        )}
      </Flex>

      {runs.length === 0 && !hasNextPage ? (
        <EmptyState>
          <Title headingLevel="h4" size="lg">No runs found</Title>
          <EmptyStateBody>Try adjusting your filters.</EmptyStateBody>
        </EmptyState>
      ) : (
        <>
          <Table aria-label="Pipeline runs" variant="compact">
            <Thead>
              <Tr>
                <Th width={10}></Th>
                <Th width={10}>Status</Th>
                <Th width={15}>Pipeline Run</Th>
                <Th width={10}>Package</Th>
                <Th width={20}>Root Cause</Th>
                <Th width={10}>Pipeline Type</Th>
                <Th width={15}>Time</Th>
                <Th width={10}>Failed Task</Th>
              </Tr>
            </Thead>
            <Tbody>
              {runs.map((run) => (
                <RunRow
                  key={run.id}
                  run={run}
                  onAskAboutRun={onAskAboutRun}
                  isExpanded={run.id === expandedRunId}
                  onToggleExpand={() => onExpandRun(run.id === expandedRunId ? '' : run.id)}
                />
              ))}
            </Tbody>
          </Table>
          <div ref={sentinelRef} style={{ height: '1px' }} />
          {isFetchingNextPage && (
            <Flex justifyContent={{ default: 'justifyContentCenter' }} style={{ padding: '1rem' }}>
              <Spinner size="md" />
            </Flex>
          )}
        </>
      )}
    </>
  );
}
