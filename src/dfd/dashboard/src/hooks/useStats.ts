import { useQuery } from '@tanstack/react-query';
import { fetchStats } from '../api/client';

export function useStats(params: { pipeline_type?: string; days?: number } = {}) {
  return useQuery({
    queryKey: ['stats', params],
    queryFn: () => fetchStats(params),
    refetchInterval: 30_000,
  });
}
