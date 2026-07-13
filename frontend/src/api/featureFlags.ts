/**
 * Stratum AI - Feature Flags API Hooks
 *
 * React Query hooks for fetching and managing feature flags.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { apiClient } from './client'
import { useFeatureFlagsStore, FeatureFlags } from '@/stores/featureFlagsStore'

// =============================================================================
// Types
// =============================================================================

export interface FeatureFlagsResponse {
  features: FeatureFlags
  categories: Record<string, { name: string; description: string; features: string[] }>
  descriptions: Record<string, string>
}

export interface FeatureFlagsUpdate {
  signal_health?: boolean
  attribution_variance?: boolean
  ai_recommendations?: boolean
  anomaly_alerts?: boolean
  creative_fatigue?: boolean
  campaign_builder?: boolean
  autopilot_level?: number
  owner_profitability?: boolean
  max_campaigns?: number
  max_users?: number
  data_retention_days?: number
  show_price_metrics?: boolean
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Fetch feature flags for a tenant and sync to Zustand store.
 */
export function useFeatureFlags(tenantId: number) {
  const { setFeatures, setMetadata, setLoading, setError } = useFeatureFlagsStore()

  const query = useQuery({
    queryKey: ['feature-flags', tenantId],
    queryFn: async () => {
      const response = await apiClient.get<{ data: FeatureFlagsResponse }>(
        `/tenants/${tenantId}/features`
      )
      return response.data.data
    },
    enabled: !!tenantId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Sync to Zustand store
  useEffect(() => {
    setLoading(query.isLoading)

    if (query.data) {
      setFeatures(query.data.features)
      setMetadata(query.data.categories, query.data.descriptions)
    }

    if (query.error) {
      setError((query.error as Error).message)
    }
  }, [query.data, query.isLoading, query.error, setFeatures, setMetadata, setLoading, setError])

  return query
}

/**
 * Update feature flags for a tenant.
 */
export function useUpdateFeatureFlags(tenantId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (updates: FeatureFlagsUpdate) => {
      const response = await apiClient.put<{ data: { features: FeatureFlags } }>(
        `/tenants/${tenantId}/features`,
        updates
      )
      return response.data.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feature-flags', tenantId] })
    },
  })
}

/**
 * Owner console: Get feature flags for any tenant.
 */
export function useConsoleFeatureFlags(tenantId: number) {
  return useQuery({
    queryKey: ['console-feature-flags', tenantId],
    queryFn: async () => {
      const response = await apiClient.get<{ data: FeatureFlagsResponse }>(
        `/console/tenants/${tenantId}/features`
      )
      return response.data.data
    },
    enabled: !!tenantId,
  })
}

/**
 * Owner console: Update feature flags for any tenant.
 */
export function useConsoleUpdateFeatureFlags(tenantId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (updates: FeatureFlagsUpdate) => {
      const response = await apiClient.put<{ data: { features: FeatureFlags } }>(
        `/console/tenants/${tenantId}/features`,
        updates
      )
      return response.data.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['console-feature-flags', tenantId] })
    },
  })
}

/**
 * Owner console: Reset tenant features to defaults.
 */
export function useConsoleResetFeatureFlags(tenantId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post<{ data: { features: FeatureFlags } }>(
        `/console/tenants/${tenantId}/features/reset`
      )
      return response.data.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['console-feature-flags', tenantId] })
    },
  })
}
