import { useQuery } from '@tanstack/react-query';
import { fetchPipelineTypes } from '../api/client';

export function usePipelineTypes() {
  return useQuery({
    queryKey: ['pipelineTypes'],
    queryFn: fetchPipelineTypes,
    staleTime: 5 * 60 * 1000,
  });
}
