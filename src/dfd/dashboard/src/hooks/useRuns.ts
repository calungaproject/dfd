import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchRuns, fetchRun, fetchRunHistory, reanalyzeSingleRun } from '../api/client';
import type { RunsResponse, RunsCounts, PipelineRun } from '../api/types';
import { useMemo } from 'react';

interface UseRunsParams {
  pipeline_type?: string;
  status?: string;
  package_name?: string;
  days?: number;
  from?: string;
  to?: string;
  root_cause?: string;
  root_cause_search?: string;
  has_root_cause?: boolean;
  taxonomy_matched?: boolean;
  name_search?: string;
}

const PAGE_SIZE = 50;

const EMPTY_COUNTS: RunsCounts = { all: 0, failed: 0, succeeded: 0, aborted: 0, unknown: 0, novel: 0 };

export function useRuns(params: UseRunsParams = {}) {
  const query = useInfiniteQuery<RunsResponse>({
    queryKey: ['runs', params],
    queryFn: ({ pageParam }) => fetchRuns({ ...params, page: pageParam as number, per_page: PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const loaded = lastPage.page * lastPage.per_page;
      return loaded < lastPage.total ? lastPage.page + 1 : undefined;
    },
    refetchInterval: 30_000,
  });

  const runs = useMemo<PipelineRun[]>(
    () => query.data?.pages.flatMap((p) => p.runs) ?? [],
    [query.data],
  );

  const total = query.data?.pages[0]?.total ?? 0;
  const counts = query.data?.pages[0]?.counts ?? EMPTY_COUNTS;

  return { ...query, runs, total, counts };
}

export function useRunDetail(pipelineRunId: string | undefined) {
  return useQuery({
    queryKey: ['run', pipelineRunId],
    queryFn: () => fetchRun(pipelineRunId!),
    enabled: !!pipelineRunId,
  });
}

export function useRunHistory(pipelineRunId: string | undefined) {
  return useQuery({
    queryKey: ['runHistory', pipelineRunId],
    queryFn: () => fetchRunHistory(pipelineRunId!),
    enabled: !!pipelineRunId,
  });
}

export function useReanalyzeRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (pipelineRunId: string) => reanalyzeSingleRun(pipelineRunId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}
