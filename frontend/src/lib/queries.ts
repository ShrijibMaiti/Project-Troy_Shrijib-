import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as api from './api';

export const useVendors = () => useQuery({ queryKey: ['vendors'], queryFn: api.getVendors });
export const useAlerts = () => useQuery({ queryKey: ['alerts'], queryFn: api.getAlerts });
export const useVendorDetail = (id: string) =>
  useQuery({ queryKey: ['vendor', id], queryFn: () => api.getVendorDetail(id) });
export const useEvidence = () => useQuery({ queryKey: ['evidence'], queryFn: api.getEvidence });
export const useMethodology = () => useQuery({ queryKey: ['methodology'], queryFn: api.getMethodology });
export const useRegister = () => useQuery({ queryKey: ['register'], queryFn: api.getRegister });
export const useCompare = () => useQuery({ queryKey: ['compare'], queryFn: api.getCompare });

export function useAddVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.addVendor,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendors'] }),
  });
}

export function useUpdateVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<api.VendorInput> }) => api.updateVendor(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendors'] }),
  });
}

export function useSetVendorArchived() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, archived }: { id: string; archived: boolean }) => api.setVendorArchived(id, archived),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendors'] }),
  });
}

export function useAppendSupersede() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.appendSupersede,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['evidence'] }),
  });
}
