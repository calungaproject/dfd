import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchPipelineTypes,
  fetchTaxonomyRules,
  fetchTaxonomyProposals,
  acceptProposal,
  rejectProposal,
  updateRule,
  deleteRule,
  mergeRule,
} from '../api/client';

export function useTaxonomyRules(pipelineTypeId: string) {
  return useQuery({
    queryKey: ['taxonomyRules', pipelineTypeId],
    queryFn: async () => {
      if (pipelineTypeId) return fetchTaxonomyRules(pipelineTypeId);
      const types = await fetchPipelineTypes();
      const results = await Promise.all(types.map((pt) => fetchTaxonomyRules(pt.id).catch(() => [])));
      return results.flat();
    },
  });
}

export function useTaxonomyProposals(pipelineTypeId: string) {
  return useQuery({
    queryKey: ['taxonomyProposals', pipelineTypeId],
    queryFn: async () => {
      if (pipelineTypeId) return fetchTaxonomyProposals(pipelineTypeId);
      const types = await fetchPipelineTypes();
      const results = await Promise.all(types.map((pt) => fetchTaxonomyProposals(pt.id).catch(() => [])));
      return results.flat();
    },
  });
}

export function useAcceptProposal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineTypeId, proposalId }: { pipelineTypeId: string; proposalId: number }) =>
      acceptProposal(pipelineTypeId, proposalId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['taxonomyRules', vars.pipelineTypeId] });
      qc.invalidateQueries({ queryKey: ['taxonomyProposals', vars.pipelineTypeId] });
    },
  });
}

export function useRejectProposal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineTypeId, proposalId }: { pipelineTypeId: string; proposalId: number }) =>
      rejectProposal(pipelineTypeId, proposalId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['taxonomyProposals', vars.pipelineTypeId] });
    },
  });
}

export function useUpdateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      pipelineTypeId,
      ruleId,
      data,
    }: {
      pipelineTypeId: string;
      ruleId: number;
      data: Partial<{
        root_cause: string;
        category: string;
        error_signature: string;
        priority_rule: string;
        investigation_recipe: string;
      }>;
    }) => updateRule(pipelineTypeId, ruleId, data),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['taxonomyRules', vars.pipelineTypeId] });
      qc.invalidateQueries({ queryKey: ['taxonomyRules', ''] });
    },
  });
}

export function useDeleteRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pipelineTypeId, ruleId }: { pipelineTypeId: string; ruleId: number }) =>
      deleteRule(pipelineTypeId, ruleId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['taxonomyRules', vars.pipelineTypeId] });
      qc.invalidateQueries({ queryKey: ['taxonomyRules', ''] });
    },
  });
}

export function useMergeRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      pipelineTypeId,
      sourceRuleId,
      targetRuleId,
    }: {
      pipelineTypeId: string;
      sourceRuleId: number;
      targetRuleId: number;
    }) => mergeRule(pipelineTypeId, sourceRuleId, targetRuleId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['taxonomyRules', vars.pipelineTypeId] });
      qc.invalidateQueries({ queryKey: ['taxonomyRules', ''] });
    },
  });
}
