/**
 * ADs Growth System - API Hooks
 *
 * Centralized barrel file that re-exports all API hooks
 * and adds new hooks for platform owner console endpoints.
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient, ApiResponse, PaginatedResponse } from './client'

// =============================================================================
// Re-exports from other API files
// =============================================================================

// EMQ V2 hooks
export {
  useEmqScore,
  useConfidence,
  useEmqPlaybook,
  useUpdatePlaybookItem,
  useEmqIncidents,
  useEmqImpact,
  useEmqVolatility,
  useAutopilotState,
  useUpdateAutopilotMode,
  useEmqBenchmarks,
  useEmqPortfolio,
} from './emqV2'

// Admin hooks
export {
  useUsers,
  useUser,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
  useResetUserPassword,
} from './admin'

// Console (Owner) Analytics hooks
export {
  usePlatformOverview,
  useSignalHealthTrends,
  useActionsAnalytics,
} from './consoleAnalytics'

// Competitors hooks
export {
  useCompetitors,
  useCompetitor,
  useCreateCompetitor,
  useUpdateCompetitor,
  useDeleteCompetitor,
  useShareOfVoice,
  useCompetitorKeywords,
  useCompetitorMetrics,
  useRefreshCompetitor,
  useScanCompetitor,
} from './competitors'

// Predictions hooks
export {
  useLivePredictions,
  useCampaignPredictions,
  usePredictionAlerts,
  useMarkAlertRead,
  useRefreshPredictions,
  useBudgetOptimization,
  useApplyBudgetOptimization,
  useScenarios,
  useScenario,
  useCreateScenario,
  useDeleteScenario,
} from './predictions'

// Insights hooks
export {
  useInsights,
  useRecommendations,
  useAnomalies,
  useKPIs,
} from './insights'

// Trust Layer hooks
export {
  useSignalHealth,
  useSignalHealthHistory,
  useAttributionVariance,
  useTrustStatus,
} from './trustLayer'

// Autopilot hooks
export {
  useAutopilotStatus,
  useAutopilotActions,
  useActionsSummary,
  useAutopilotAction,
  useQueueAction,
  useApproveAction,
  useApproveAllActions,
  useDismissAction,
} from './autopilot'

// Campaigns hooks
export {
  useCampaigns,
  useCampaign,
  useCreateCampaign,
  useUpdateCampaign,
  useDeleteCampaign,
  useCampaignMetrics,
  useSyncCampaign,
  useBulkUpdateCampaignStatus,
  usePauseCampaign,
  useActivateCampaign,
} from './campaigns'

// Assets hooks
export {
  useAssets,
  useAsset,
  useCreateAsset,
  useUploadAsset,
  useUpdateAsset,
  useDeleteAsset,
  useAssetFolders,
  useCreateFolder,
  useFatiguedAssets,
  useCalculateFatigue,
  useBulkArchiveAssets,
} from './assets'

// Rules hooks
export {
  useRules,
  useRule,
  useCreateRule,
  useUpdateRule,
  useDeleteRule,
  useToggleRule,
  useDuplicateRule,
  useExecuteRule,
  useRuleExecutions,
  useRuleTemplates,
  useValidateConditions,
} from './rules'

// Feature flags hooks
export {
  useFeatureFlags,
  useUpdateFeatureFlags,
  useConsoleFeatureFlags,
  useConsoleUpdateFeatureFlags,
  useConsoleResetFeatureFlags,
} from './featureFlags'

// GDPR hooks (exclude useAuditLogs since we have our own)
export {
  useExportData,
  useExportStatus,
  useExportHistory,
  useAnonymizeData,
  useAnonymizationStatus,
  useConsentRecords,
  useUpdateConsent,
  useDataCategories,
  useRequestDeletion,
  useCancelDeletion,
} from './gdpr'

// CRM/HubSpot Integration hooks
export {
  useCRMConnections,
  useCRMConnection,
  useConnectHubSpot,
  useDisconnectCRM,
  useTriggerCRMSync,
  useCRMContacts,
  useCRMContact,
  useContactJourney,
  useCRMDeals,
  useCRMDeal,
  usePipelineMetrics,
  usePipelineSummary,
  useWritebackConfig,
  useUpdateWritebackConfig,
  useWritebackHistory,
  useRetryWriteback,
} from './crm'

// Pacing & Forecasting hooks
export {
  useTargets,
  useTarget,
  useCreateTarget,
  useUpdateTarget,
  useDeleteTarget,
  usePacingStatus,
  useAllPacingStatus,
  usePacingSummary,
  useDailyKPIs,
  useForecast,
  useMetricForecast,
  useGenerateForecast,
  usePacingAlerts,
  usePacingAlert,
  useAcknowledgeAlert,
  useResolveAlert,
  useDismissAlert,
  useAlertStats,
} from './pacing'

// Profit ROAS hooks
export {
  useProducts,
  useProduct,
  useCreateProduct,
  useUpdateProduct,
  useDeleteProduct,
  useImportProducts,
  useProductMargins,
  useSetProductMargin,
  useMarginRules,
  useMarginRule,
  useCreateMarginRule,
  useUpdateMarginRule,
  useDeleteMarginRule,
  useUploadCOGS,
  useCOGSUploads,
  useCOGSUpload,
  useDailyProfitMetrics,
  useProfitSummary,
  useGenerateProfitReport,
  useProfitReports,
  useProfitReport,
  useTrueROAS,
} from './profit'

// Attribution hooks
export {
  useAttributionSummary,
  useDailyAttributedRevenue,
  useChannelTransitions,
  useTopConversionPaths,
  useAssistedConversions,
  useTimeLagReport,
  useTrainedModels,
  useTrainedModel,
  useTrainMarkovModel,
  useTrainShapleyModel,
  useCompareModels,
  useArchiveModel,
  useActivateModel,
} from './attribution'

// Reporting hooks
export {
  useReportTemplates,
  useReportTemplate,
  useCreateReportTemplate,
  useUpdateReportTemplate,
  useDeleteReportTemplate,
  useReportSchedules,
  useReportSchedule,
  useCreateReportSchedule,
  useUpdateReportSchedule,
  useDeleteReportSchedule,
  usePauseReportSchedule,
  useResumeReportSchedule,
  useGenerateReport,
  useReportExecutions,
  useReportExecution,
  useDeliveryStatus,
  useDeliveryChannelConfigs,
  useUpdateDeliveryChannelConfig,
  useVerifyDeliveryChannel,
} from './reporting'

// Account Dashboard hooks
export {
  useUpdateAccountSettings,
} from './hooks/useAccountDashboard'

// =============================================================================
// Account Overview Hooks (for account dashboard)
// =============================================================================

/**
 * Get account overview KPIs for the dashboard.
 *
 * Adapts the flat `/dashboard/overview` payload into the `{ kpis }`
 * shape this hook's consumers expect. (The previous
 * `/analytics/tenant-overview` endpoint returned a LIST of accounts,
 * which crashed every consumer that read `data.kpis` off it.)
 */
export function useAccountOverview(accountId: number) {
  return useQuery({
    queryKey: ['account', 'overview', accountId],
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<{
        total_spend: number
        total_revenue: number
        portfolio_roas: number
        avg_cpa: number
      }>>(`/dashboard/overview`)
      const overview = response.data.data
      return {
        kpis: {
          total_spend: overview.total_spend,
          total_revenue: overview.total_revenue,
          roas: overview.portfolio_roas,
          cpa: overview.avg_cpa,
        },
      }
    },
    enabled: !!accountId,
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  })
}

/**
 * Get account recommendations
 */
export function useAccountRecommendations(accountId: number, options?: { limit?: number }) {
  return useQuery({
    queryKey: ['account', 'recommendations', accountId, options],
    queryFn: async () => {
      const params = options?.limit ? `?limit=${options.limit}` : ''
      const response = await apiClient.get<ApiResponse<{
        recommendations: Array<{
          id: string
          type: string
          priority: string
          title: string
          description: string
          expected_impact: number
        }>
        total: number
      }>>(`/insights/recommendations${params}`)
      return response.data.data
    },
    staleTime: 60 * 1000,
  })
}

// =============================================================================
// Console (Owner) Dashboard Types
// =============================================================================

export interface SystemHealthMetrics {
  overallStatus: 'healthy' | 'degraded' | 'down'
  services: Array<{
    name: string
    status: 'healthy' | 'degraded' | 'down'
    uptime: number
    latency: number
    version: string
  }>
  connectors: Array<{
    platform: string
    status: 'healthy' | 'degraded' | 'down'
    lastSync: string
    errors: number
    recordsProcessed: number
  }>
  queues: Array<{
    name: string
    status: 'running' | 'paused' | 'stalled'
    pending: number
    processing: number
    completed: number
    failed: number
    avgProcessTime: number
  }>
  metrics: {
    cpu: number
    memory: number
    disk: number
    network: number
    activeConnections: number
    requestsPerMinute: number
    errorRate: number
  }
}

export interface AuditLogEntry {
  id: string
  timestamp: string
  action: string
  details: string
  userId: string
  userName: string | null
  ipAddress: string | null
  userAgent: string | null
  severity: 'info' | 'warning' | 'error' | 'critical'
  metadata: Record<string, unknown>
}

/**
 * Owner console dashboard summary. Combines usage, health, and alert
 * counts for the single-org deployment (revenue/tenant-portfolio/churn
 * sections were removed in STRAT-SC-001/C3 — their sole data source was
 * the deleted Tenant model).
 */
export interface ConsoleDashboardSummary {
  usage: {
    total_users: number
    total_campaigns: number
  }
  health: {
    platform_status: string
    pipeline_success_rate: number | null
    api_uptime: number | null
  }
  alerts: {
    critical: number
    high: number
    medium: number
  }
}

// =============================================================================
// Console (Owner) API Functions
// =============================================================================

export const consoleApi = {
  // Dashboard
  getDashboard: async (): Promise<ConsoleDashboardSummary> => {
    const response = await apiClient.get<ApiResponse<ConsoleDashboardSummary>>(
      '/console/dashboard'
    )
    return response.data.data
  },

  // System Health
  getSystemHealth: async (): Promise<SystemHealthMetrics> => {
    const response = await apiClient.get<ApiResponse<SystemHealthMetrics>>(
      '/console/system/health'
    )
    return response.data.data
  },

  // Audit Logs
  getAuditLogs: async (params?: {
    startDate?: string
    endDate?: string
    action?: string
    userId?: string
    severity?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedResponse<AuditLogEntry>> => {
    const response = await apiClient.get<ApiResponse<PaginatedResponse<AuditLogEntry>>>(
      '/console/audit',
      { params }
    )
    return response.data.data
  },
}

// =============================================================================
// Console (Owner) React Query Hooks
// =============================================================================

/**
 * Get console dashboard overview
 */
export function useConsoleOverview() {
  return useQuery({
    queryKey: ['console', 'dashboard'],
    queryFn: consoleApi.getDashboard,
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  })
}

/**
 * Get system health metrics
 */
export function useSystemHealth() {
  return useQuery({
    queryKey: ['console', 'system', 'health'],
    queryFn: consoleApi.getSystemHealth,
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000, // Refresh every 30 seconds
  })
}

/**
 * Get audit logs
 */
export function useAuditLogs(params?: {
  startDate?: string
  endDate?: string
  action?: string
  userId?: string
  severity?: string
  skip?: number
  limit?: number
}) {
  return useQuery({
    queryKey: ['console', 'audit', params],
    queryFn: () => consoleApi.getAuditLogs(params),
    staleTime: 30 * 1000,
  })
}

// WhatsApp hooks
export {
  useWhatsAppContacts,
  useCreateWhatsAppContact,
  useWhatsAppContact,
  useUpdateWhatsAppContact,
  useDeleteWhatsAppContact,
  useWhatsAppTemplates,
  useCreateWhatsAppTemplate,
  useWhatsAppMessages,
  useSendWhatsAppMessage,
  useWhatsAppConversations,
} from './whatsapp'

// MFA hooks
export {
  useMFAStatus,
  useMFASetup,
  useMFAVerify,
  useMFADisable,
  useMFABackupCodes,
  useMFAValidate,
} from './mfa'

// Webhooks hooks
export {
  useWebhooks,
  useWebhook,
  useCreateWebhook,
  useUpdateWebhook,
  useDeleteWebhook,
  useTestWebhook,
  useWebhookDeliveries,
} from './webhooks'

// Notifications hooks
export {
  useNotifications,
  useNotificationCount,
  useMarkNotificationsRead,
  useDeleteNotification,
} from './notifications'

// Slack hooks
export {
  useSlackStatus,
  useSlackConnect,
  useSlackDisconnect,
  useSlackNotify,
  useSlackTestConnection,
} from './slack'

// Simulator hooks
export {
  useSimulateScenario,
  useForecastRoas,
  usePredictConversions,
  useModelStatus,
} from './simulator'

// API Keys hooks
export {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
} from './apiKeys'

// CAPI hooks
export {
  useStreamEvent,
  useStreamBatchEvents,
  useCapiDataQualityReport,
  useConnectPlatform,
  useDisconnectPlatform,
  usePlatformsStatus,
} from './capi'

// Meta CAPI hooks
export {
  useMetaCapiSendEvents,
  useMetaCapiValidateEvents,
  useMetaCapiQualityReport,
  useMetaCapiHealth,
} from './metaCapi'

// Clients hooks
export {
  useClients,
  useCreateClient,
  useClient,
  useUpdateClient,
  useDeleteClient,
  useClientUsers,
  useInvitePortalUser,
} from './clients'

// Landing CMS hooks
export {
  useLandingPages,
  useLandingPage,
  useLandingPosts,
  useLandingPost,
  useLandingCategories,
  useLandingTags,
} from './landingCms'
