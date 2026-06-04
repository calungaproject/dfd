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
  Split,
  SplitItem,
} from '@patternfly/react-core';
import { useMemo } from 'react';
import { useStats } from '../../hooks/useStats';
import { useRuns } from '../../hooks/useRuns';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { usePipelineTypes } from '../../hooks/usePipelineTypes';
import StatsCards from './StatsCards';
import DailyChart from './DailyChart';
import RootCauseChart from './RootCauseChart';
import RunList from './RunList';
const DAYS_OPTIONS = [7, 14, 30, 60, 90];

type RunFilter = 'all' | 'failed' | 'succeeded' | 'aborted' | 'unknown' | 'novel';

interface OverviewTabProps {
  onAskAboutRun: (pipelineRunId: string) => void;
  hashParams: URLSearchParams;
  onHashParamsChange: (updates: Record<string, string>) => void;
}

export default function OverviewTab({ onAskAboutRun, hashParams, onHashParamsChange }: OverviewTabProps) {
  const pipelineTypesQuery = usePipelineTypes();
  const pipelineType = hashParams.get('pipeline_type') || '';
  const days = Number(hashParams.get('days')) || 30;
  const statusFilter = hashParams.get('status') || '';
  const runFilter = (hashParams.get('filter') || 'all') as RunFilter;
  const rootCauseSearch = hashParams.get('rootCause') || '';
  const expandedRunId = hashParams.get('run') || '';

  const updateParams = (updates: Record<string, string>) => {
    const merged: Record<string, string> = {};
    hashParams.forEach((v, k) => { merged[k] = v; });
    Object.assign(merged, updates);
    onHashParamsChange(merged);
  };

  const debouncedRootCause = useDebouncedValue(rootCauseSearch, 300, 3);

  const runsParams = useMemo(() => {
    const p: Record<string, unknown> = {
      pipeline_type: pipelineType || undefined,
      days,
      status: statusFilter || undefined,
    };

    switch (runFilter) {
      case 'failed':
        p.status = 'failed';
        break;
      case 'succeeded':
        p.status = 'succeeded';
        break;
      case 'aborted':
        p.status = 'aborted';
        break;
      case 'unknown':
        p.status = 'failed';
        p.has_root_cause = false;
        break;
      case 'novel':
        p.status = 'failed';
        p.taxonomy_matched = false;
        break;
    }

    if (debouncedRootCause) {
      p.root_cause_search = debouncedRootCause;
    }

    return p;
  }, [pipelineType, days, statusFilter, runFilter, debouncedRootCause]);

  const statsQuery = useStats({ pipeline_type: pipelineType || undefined, days });
  const runsQuery = useRuns(runsParams);

  return (
    <PageSection>
      <Toolbar>
        <ToolbarContent>
          <ToolbarItem>
            <FormGroup label="Pipeline Type" fieldId="pipeline-type-select">
              <FormSelect
                id="pipeline-type-select"
                value={pipelineType}
                onChange={(_e, val) => updateParams({ pipeline_type: val })}
              >
                <FormSelectOption value="" label="All pipeline types" />
                {(pipelineTypesQuery.data ?? []).map((pt) => (
                  <FormSelectOption key={pt.id} value={pt.id} label={pt.display_name} />
                ))}
              </FormSelect>
            </FormGroup>
          </ToolbarItem>
          <ToolbarItem>
            <FormGroup label="Days" fieldId="days-select">
              <FormSelect
                id="days-select"
                value={String(days)}
                onChange={(_e, val) => updateParams({ days: val })}
              >
                {DAYS_OPTIONS.map((d) => (
                  <FormSelectOption key={d} value={String(d)} label={`Last ${d} days`} />
                ))}
              </FormSelect>
            </FormGroup>
          </ToolbarItem>
        </ToolbarContent>
      </Toolbar>

      {statsQuery.isLoading ? (
        <Bullseye><Spinner /></Bullseye>
      ) : statsQuery.data ? (
        <>
          <StatsCards stats={statsQuery.data} />
          <Split hasGutter style={{ marginTop: '1rem' }}>
            <SplitItem isFilled>
              <DailyChart data={statsQuery.data.daily} />
            </SplitItem>
            <SplitItem isFilled>
              <RootCauseChart data={statsQuery.data.root_causes} />
            </SplitItem>
          </Split>
        </>
      ) : null}

      <div style={{ marginTop: '1rem' }}>
        {runsQuery.isLoading ? (
          <Bullseye><Spinner /></Bullseye>
        ) : runsQuery.data ? (
          <RunList
            runs={runsQuery.runs}
            total={runsQuery.total}
            counts={runsQuery.counts}
            hasNextPage={!!runsQuery.hasNextPage}
            isFetchingNextPage={runsQuery.isFetchingNextPage}
            fetchNextPage={runsQuery.fetchNextPage}
            onAskAboutRun={onAskAboutRun}
            activeFilter={runFilter}
            onFilterChange={(f) => updateParams({ filter: f })}
            rootCauseSearch={rootCauseSearch}
            onRootCauseSearchChange={(v) => updateParams({ rootCause: v })}
            expandedRunId={expandedRunId}
            onExpandRun={(id) => updateParams({ run: id })}
          />
        ) : null}
      </div>
    </PageSection>
  );
}
