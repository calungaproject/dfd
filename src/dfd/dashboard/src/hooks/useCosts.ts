import { useQuery } from '@tanstack/react-query';
import { fetchCosts } from '../api/client';

export function useCosts(days = 30) {
  return useQuery({
    queryKey: ['costs', days],
    queryFn: () => fetchCosts(days),
  });
}
