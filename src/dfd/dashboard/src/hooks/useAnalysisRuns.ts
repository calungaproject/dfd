import { useQuery } from '@tanstack/react-query';
import { fetchAnalysisRuns, fetchAnalysisRunDetail, fetchReanalysisQueue } from '../api/client';

export function useAnalysisRuns(limit = 20) {
  return useQuery({
    queryKey: ['analysisRuns', limit],
    queryFn: () => fetchAnalysisRuns(limit),
    refetchInterval: 15_000,
  });
}

export function useAnalysisRunDetail(runId: number | undefined) {
  return useQuery({
    queryKey: ['analysisRunDetail', runId],
    queryFn: () => fetchAnalysisRunDetail(runId!),
    enabled: !!runId,
    refetchInterval: 15_000,
  });
}

export function useReanalysisQueue() {
  return useQuery({
    queryKey: ['reanalysisQueue'],
    queryFn: fetchReanalysisQueue,
    refetchInterval: 15_000,
  });
}
