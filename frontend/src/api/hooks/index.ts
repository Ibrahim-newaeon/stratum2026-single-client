/**
 * Stratum AI - React Query Hooks
 *
 * Centralized exports for all API hooks.
 */

// Account Dashboard hooks
export {
  useAccountOverview,
  useAccountRecommendations,
  useAccountAlerts,
  useAccountSettings,
  useUpdateAccountSettings,
  useAcknowledgeAlert,
  useResolveAlert,
  useCommandCenter,
  accountQueryKeys,
  type DashboardOverview,
  type Recommendation,
  type Alert,
  type AccountSettings,
  type CommandCenterItem,
  type CommandCenterResponse,
} from './useAccountDashboard'

// Re-export from API modules
// Note: Some modules export conflicting types (User, AlertSeverity)
// Import directly from specific modules if you need to disambiguate
export * from '../auth'
export * from '../emqV2'
export * from '../campaigns'
export * from '../assets'
export * from '../rules'
export * from '../competitors'
export * from '../predictions'
export * from '../gdpr'
export * from '../attribution'
export * from '../profit'
export * from '../reporting'
export * from '../abTesting'

// Admin module - export with renamed User type to avoid conflict
export {
  useUsers,
  useUser,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
  type UserRole,
  type User as AdminUser,
  type UserFilters,
  type CreateUserRequest,
  type UpdateUserRequest,
} from '../admin'

// Pacing module - export with renamed AlertSeverity to avoid conflict
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
  useAcknowledgeAlert as useAcknowledgePacingAlert,
  useResolveAlert as useResolvePacingAlert,
  useDismissAlert as useDismissPacingAlert,
  useAlertStats,
  pacingApi,
  type Target,
  type TargetPeriod,
  type TargetMetric,
  type AlertSeverity as PacingAlertSeverity,
  type AlertType as PacingAlertType,
  type AlertStatus as PacingAlertStatus,
  type PacingStatus,
  type PacingAlert,
  type Forecast,
  type ForecastPrediction,
  type PacingSummary,
  type DailyKPI,
  type CreateTargetRequest,
} from '../pacing'
