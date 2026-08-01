/**
 * ADs Growth System - Console (Owner) Analytics API Hooks
 *
 * React Query hooks for platform-owner console analytics:
 * - Platform overview
 * - Signal health trends
 * - Actions analytics
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';

// =============================================================================
// Types
// =============================================================================

export interface PlatformOverview {
  period_days: number;
  start_date: string;
  total_actions: number;
  applied_actions: number;
  failed_actions: number;
  success_rate: number;
  signal_health_summary: Record<string, number>;
  platform_breakdown: Array<{
    platform: string;
    record_count: number;
    avg_emq: number | null;
  }>;
}

export interface SignalHealthTrend {
  date: string;
  avg_emq: number | null;
  avg_event_loss: number | null;
  avg_freshness_minutes: number | null;
  avg_api_error_rate: number | null;
  record_count: number;
}

export interface SignalHealthTrendsResponse {
  period_days: number;
  trends: SignalHealthTrend[];
  trend_direction: 'improving' | 'declining' | 'stable' | 'insufficient_data';
}

export interface ActionsAnalytics {
  period_days: number;
  total_actions: number;
  type_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  platform_breakdown: Record<string, number>;
  daily_counts: Array<{ date: string; count: number }>;
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Get platform-wide overview metrics.
 */
export function usePlatformOverview(days: number = 7) {
  return useQuery({
    queryKey: ['console-platform-overview', days],
    queryFn: async () => {
      const response = await apiClient.get<{ data: PlatformOverview }>(
        `/console/platform-overview?days=${days}`
      );
      return response.data.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Get signal health trends.
 */
export function useSignalHealthTrends(days: number = 14) {
  return useQuery({
    queryKey: ['console-signal-health-trends', days],
    queryFn: async () => {
      const response = await apiClient.get<{ data: SignalHealthTrendsResponse }>(
        `/console/signal-health-trends?days=${days}`
      );
      return response.data.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Get actions analytics.
 */
export function useActionsAnalytics(days: number = 7) {
  return useQuery({
    queryKey: ['console-actions-analytics', days],
    queryFn: async () => {
      const response = await apiClient.get<{ data: ActionsAnalytics }>(
        `/console/actions-analytics?days=${days}`
      );
      return response.data.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// =============================================================================
// Cross-Account Anomalies Rollup
// =============================================================================

export interface CrossAccountAnomaly {
  id: string;
  detected_at: string;
  metric: string;
  entity_type: string;
  entity_id: string;
  entity_name: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  direction: 'spike' | 'drop';
  current_value: number;
  expected_value: number | null;
  description: string;
  possible_causes: string[];
  recommended_actions: string[];
}

export interface AnomaliesRollupResponse {
  date: string;
  anomalies: CrossAccountAnomaly[];
  total: number;
  by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
}

/**
 * Scan every top-spend campaign for anomalies in one backend call.
 * Single-org deployment — no per-tenant fan-out needed.
 */
export function useAnomaliesRollup(severity?: 'critical' | 'high' | 'medium' | 'low') {
  return useQuery({
    queryKey: ['console-anomalies-rollup', severity ?? 'all'],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (severity) params.set('severity', severity);
      const qs = params.toString();
      const response = await apiClient.get<{ data: AnomaliesRollupResponse }>(
        `/console/anomalies-rollup${qs ? `?${qs}` : ''}`
      );
      return response.data.data;
    },
    staleTime: 60 * 1000,
  });
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Get health score color.
 */
export function getHealthScoreColor(score: number): string {
  if (score >= 80) return 'green';
  if (score >= 60) return 'yellow';
  if (score >= 40) return 'orange';
  return 'red';
}

/**
 * Get trend direction icon.
 */
export function getTrendIcon(direction: string): string {
  const icons: Record<string, string> = {
    improving: '📈',
    declining: '📉',
    stable: '➡️',
    insufficient_data: '❓',
  };
  return icons[direction] || '❓';
}

/**
 * Format platform name.
 */
export function formatPlatformName(platform: string): string {
  const names: Record<string, string> = {
    meta: 'Meta (Facebook/Instagram)',
    google: 'Google Ads',
    tiktok: 'TikTok Ads',
    snapchat: 'Snapchat Ads',
  };
  return names[platform] || platform;
}
