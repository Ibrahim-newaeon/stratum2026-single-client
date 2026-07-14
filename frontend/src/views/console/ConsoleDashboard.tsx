/**
 * Owner Console Dashboard
 * System-wide monitoring for the single-org deployment: usage, platform
 * health, and audit trail.
 *
 * NOTE(STRAT-SC-001/D3): the revenue/tenant-portfolio/churn-risk/billing
 * tabs and panels that used to live here were removed. Their sole data
 * source was the deleted Tenant model + Stripe billing tables — C3
 * deleted the backing routes (/console/revenue, /console/tenants/portfolio,
 * /console/churn/risks, /console/billing/*) since a single-org deployment
 * has no MRR, tenant portfolio, churn, or subscription concept. See
 * task-C3-report.md's console.py route disposition table.
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Server,
  Activity,
  AlertTriangle,
  Globe,
  Database,
  Cpu,
  HardDrive,
  Zap,
  RefreshCw,
  Search,
  CheckCircle2,
  XCircle,
  Settings,
  Key,
  AlertCircle,
  Loader2,
  Crown,
  FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { useAuth } from '@/contexts/AuthContext'
import apiClient from '@/api/client'

// =============================================================================
// Types
// =============================================================================
interface DashboardSummary {
  usage: { total_users: number; total_campaigns: number }
  health: {
    platform_status: string
    pipeline_success_rate: number | null
    api_uptime: number | null
  }
  alerts: { critical: number; high: number; medium: number }
}

interface SystemHealth {
  pipeline: { success_rate_24h: number; jobs_total_24h: number; jobs_failed_24h: number }
  api: { requests_24h: number; error_rate: number; latency_p50_ms: number; latency_p99_ms?: number }
  platforms: Record<string, { status: string; success_rate: number }>
  resources?: { cpu_percent: number; memory_percent: number; disk_percent: number }
}

interface SystemAlert {
  id: string
  type: 'error' | 'warning' | 'info'
  message: string
  component: string
  timestamp: string
}

interface AuditLogEntry {
  id: string
  timestamp?: string
  action: string
  user_email?: string
  user_id?: number
  resource_type?: string
  resource_id?: number
  success?: boolean
  details?: Record<string, unknown>
}

/** Derive system alerts from live health + dashboard summary data. */
function deriveAlerts(health: SystemHealth | null, alertCounts: DashboardSummary['alerts'] | null): SystemAlert[] {
  const alerts: SystemAlert[] = []

  if (health) {
    if (health.pipeline.success_rate_24h < 99) {
      alerts.push({
        id: 'pipe-1',
        type: health.pipeline.success_rate_24h < 95 ? 'error' : 'warning',
        message: `Pipeline success rate at ${health.pipeline.success_rate_24h}% — ${health.pipeline.jobs_failed_24h} jobs failed in 24h`,
        component: 'Pipeline',
        timestamp: 'Last 24h',
      })
    }
    if (health.api.error_rate >= 1) {
      alerts.push({
        id: 'api-1',
        type: health.api.error_rate >= 5 ? 'error' : 'warning',
        message: `API error rate at ${health.api.error_rate}% (${health.api.requests_24h.toLocaleString()} requests in 24h)`,
        component: 'API Gateway',
        timestamp: 'Last 24h',
      })
    }
    if (health.api.latency_p50_ms > 200) {
      alerts.push({
        id: 'api-2',
        type: 'warning',
        message: `High API latency detected — p50 at ${health.api.latency_p50_ms}ms`,
        component: 'API Gateway',
        timestamp: 'Current',
      })
    }
    if (health.resources && health.resources.cpu_percent >= 80) {
      alerts.push({
        id: 'res-1',
        type: health.resources.cpu_percent >= 90 ? 'error' : 'warning',
        message: `CPU usage at ${health.resources.cpu_percent}% — consider scaling`,
        component: 'Infrastructure',
        timestamp: 'Current',
      })
    }
    if (health.resources && health.resources.memory_percent >= 80) {
      alerts.push({
        id: 'res-2',
        type: health.resources.memory_percent >= 90 ? 'error' : 'warning',
        message: `Memory usage at ${health.resources.memory_percent}% — monitor closely`,
        component: 'Infrastructure',
        timestamp: 'Current',
      })
    }
    Object.entries(health.platforms).forEach(([platform, data]) => {
      if (data.success_rate < 95) {
        alerts.push({
          id: `plat-${platform}`,
          type: data.success_rate < 80 ? 'error' : 'warning',
          message: `${platform} sync success rate at ${data.success_rate}%`,
          component: 'Sync Service',
          timestamp: 'Last 24h',
        })
      }
    })
  }

  if (alertCounts && (alertCounts.critical > 0 || alertCounts.high > 0)) {
    alerts.push({
      id: 'enforcement-1',
      type: alertCounts.critical > 0 ? 'error' : 'warning',
      message: `${alertCounts.critical} critical, ${alertCounts.high} high-severity enforcement alerts in the last 24h`,
      component: 'Trust Engine',
      timestamp: 'Last 24h',
    })
  }

  if (alerts.length === 0) {
    alerts.push({
      id: 'ok-1',
      type: 'info',
      message: 'All systems operating normally',
      component: 'System',
      timestamp: new Date().toLocaleTimeString(),
    })
  }

  return alerts
}

// =============================================================================
// Main Component
// =============================================================================
export default function ConsoleDashboard() {
  const { user } = useAuth()
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'system' | 'audit'>('overview')
  const [auditFilter, setAuditFilter] = useState({ action: '' })

  // API Data
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null)
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([])

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const [dashboardRes, healthRes, auditRes] = await Promise.allSettled([
        apiClient.get('/console/dashboard'),
        apiClient.get('/console/system/health'),
        apiClient.get('/console/audit', { params: { limit: 100 } }),
      ])

      if (dashboardRes.status === 'fulfilled' && dashboardRes.value.data.success) {
        setDashboard(dashboardRes.value.data.data)
      }
      if (healthRes.status === 'fulfilled' && healthRes.value.data.success) {
        setSystemHealth(healthRes.value.data.data)
      }
      if (auditRes.status === 'fulfilled' && auditRes.value.data.success) {
        setAuditLogs(auditRes.value.data.data.logs || [])
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Failed to load dashboard data')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleRefresh = () => {
    setIsRefreshing(true)
    fetchData().finally(() => setIsRefreshing(false))
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96 motion-enter">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-3 text-muted-foreground">Loading Owner Console Dashboard...</span>
      </div>
    )
  }

  return (
    <ErrorBoundary>
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 motion-enter">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Crown className="w-7 h-7 text-warning" />
            Owner Console Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">
            System-wide monitoring • Welcome back, {user?.name}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border hover:bg-muted transition-colors motion-card"
          >
            <RefreshCw className={cn('w-4 h-4', isRefreshing && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-destructive/10 text-destructive border border-destructive/20 motion-critical">
          <AlertTriangle className="h-5 w-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 p-1 rounded-lg bg-muted/50 w-fit motion-enter overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview', icon: Activity },
          { id: 'system', label: 'System', icon: Server },
          { id: 'audit', label: 'Audit Log', icon: FileText },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap',
              activeTab === tab.id
                ? 'bg-background shadow text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* =========================================================================
          Overview Tab - Usage + System Health Summary + Alerts
      ========================================================================= */}
      {activeTab === 'overview' && (
        <div className="space-y-6 motion-enter">
          {/* Usage Snapshot */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <MetricCard label="Total Users" value={dashboard?.usage.total_users ?? 0} status="blue" />
            <MetricCard label="Total Campaigns" value={dashboard?.usage.total_campaigns ?? 0} status="blue" />
            <MetricCard
              label="Platform Status"
              value={dashboard?.health.platform_status ?? 'unknown'}
              status={dashboard?.health.platform_status === 'operational' ? 'green' : 'amber'}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* System Health Summary */}
            <div className="rounded-xl border bg-card p-5 shadow-card motion-card">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-success" />
                System Health
              </h3>
              {systemHealth ? (
                <div className="space-y-3">
                  <HealthRow
                    label="Pipeline Success Rate"
                    value={`${systemHealth.pipeline.success_rate_24h}%`}
                    status={systemHealth.pipeline.success_rate_24h >= 99 ? 'green' : 'amber'}
                  />
                  <HealthRow
                    label="API Error Rate"
                    value={`${systemHealth.api.error_rate}%`}
                    status={systemHealth.api.error_rate < 1 ? 'green' : 'amber'}
                  />
                  <HealthRow
                    label="API Latency (p50)"
                    value={`${systemHealth.api.latency_p50_ms}ms`}
                    status={systemHealth.api.latency_p50_ms < 100 ? 'green' : 'amber'}
                  />
                  <HealthRow
                    label="CPU Usage"
                    value={`${systemHealth.resources?.cpu_percent ?? 0}%`}
                    status={(systemHealth.resources?.cpu_percent ?? 0) < 70 ? 'green' : 'amber'}
                  />
                </div>
              ) : (
                <p className="text-muted-foreground py-4 text-center">Loading health metrics...</p>
              )}
            </div>

            {/* Alert Counts */}
            <div className="rounded-xl border bg-card p-5 shadow-card motion-card">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-warning" />
                Enforcement Alerts (24h)
              </h3>
              <div className="space-y-3">
                <HealthRow label="Critical" value={String(dashboard?.alerts.critical ?? 0)} status={((dashboard?.alerts.critical ?? 0) > 0) ? 'red' : 'green'} />
                <HealthRow label="High" value={String(dashboard?.alerts.high ?? 0)} status={((dashboard?.alerts.high ?? 0) > 0) ? 'amber' : 'green'} />
                <HealthRow label="Medium" value={String(dashboard?.alerts.medium ?? 0)} status="green" />
              </div>
            </div>
          </div>

          {/* System Alerts */}
          <div className="rounded-xl border bg-card p-6 shadow-card motion-card">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-primary" />
              System Alerts
            </h3>
            <div className="space-y-3">
              {deriveAlerts(systemHealth, dashboard?.alerts ?? null).map((alert, idx) => (
                <div
                  key={alert.id}
                  className={cn(
                    'flex items-start gap-3 p-3 rounded-lg border motion-enter',
                    alert.type === 'error' && 'bg-danger/5 border-red-500/20',
                    alert.type === 'warning' && 'bg-warning/5 border-amber-500/20',
                    alert.type === 'info' && 'bg-info/5 border-blue-500/20'
                  )}
                  style={{ animationDelay: `${idx * 30}ms` }}
                >
                  {alert.type === 'error' && <XCircle className="w-5 h-5 text-danger flex-shrink-0" />}
                  {alert.type === 'warning' && <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0" />}
                  {alert.type === 'info' && <CheckCircle2 className="w-5 h-5 text-info flex-shrink-0" />}
                  <div className="flex-1">
                    <p className="text-sm font-medium">{alert.message}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {alert.component} • {alert.timestamp}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          System Tab - Infrastructure Status & Platform Health
      ========================================================================= */}
      {activeTab === 'system' && (
        <div className="space-y-6 motion-enter">
          {/* Platform Health Grid */}
          {systemHealth && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(systemHealth.platforms).map(([platform, data], idx) => (
                <div
                  key={platform}
                  className="rounded-xl border bg-card p-4 shadow-card motion-card"
                  style={{ animationDelay: `${idx * 50}ms` }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-medium capitalize">{platform}</span>
                    <HealthBadge status={data.status} />
                  </div>
                  <p className="text-2xl font-bold">{data.success_rate}%</p>
                  <p className="text-xs text-muted-foreground">Success Rate</p>
                </div>
              ))}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Infrastructure Status */}
            <div className="rounded-xl border bg-card p-6 shadow-card motion-card">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <Server className="w-5 h-5 text-primary" />
                Infrastructure Status
              </h3>
              <div className="space-y-4">
                {(() => {
                  const cpu = systemHealth?.resources?.cpu_percent ?? 45
                  const mem = systemHealth?.resources?.memory_percent ?? 62
                  const disk = systemHealth?.resources?.disk_percent ?? 30
                  const apiOk = systemHealth ? systemHealth.api.error_rate < 5 : true
                  const pipeOk = systemHealth ? systemHealth.pipeline.success_rate_24h >= 95 : true
                  return [
                    { name: 'API Server', status: apiOk ? 'healthy' : 'degraded', cpu: Math.round(cpu * 0.85), memory: Math.round(mem * 0.9) },
                    { name: 'Worker Nodes', status: pipeOk ? 'healthy' : 'degraded', cpu: Math.round(Math.min(100, cpu * 1.2)), memory: Math.round(Math.min(100, mem * 1.15)) },
                    { name: 'Database', status: disk < 80 ? 'healthy' : 'degraded', cpu: Math.round(cpu * 0.5), memory: Math.round(mem * 0.75) },
                    { name: 'Redis Cache', status: 'healthy', cpu: Math.round(cpu * 0.25), memory: Math.round(mem * 0.6) },
                    { name: 'ML Service', status: 'healthy', cpu: Math.round(Math.min(100, cpu * 1.1)), memory: Math.round(Math.min(100, mem * 1.05)) },
                  ]
                })().map((service, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 rounded-lg bg-muted/30 motion-enter"
                    style={{ animationDelay: `${idx * 30}ms` }}
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn('w-2 h-2 rounded-full', service.status === 'healthy' ? 'bg-success' : 'bg-danger')} />
                      <span className="font-medium">{service.name}</span>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="flex items-center gap-1">
                        <Cpu className="w-4 h-4 text-muted-foreground" />
                        {service.cpu}%
                      </span>
                      <span className="flex items-center gap-1">
                        <HardDrive className="w-4 h-4 text-muted-foreground" />
                        {service.memory}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Detailed API Metrics */}
            {systemHealth && (
              <div className="rounded-xl border bg-card p-6 shadow-card motion-card">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-warning" />
                  API Metrics (24h)
                </h3>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="p-4 rounded-lg bg-muted/30">
                    <p className="text-2xl font-bold">{systemHealth.api.requests_24h.toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground">Total Requests</p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/30">
                    <p className={cn(
                      'text-2xl font-bold',
                      systemHealth.api.error_rate < 1 ? 'text-success' : 'text-danger'
                    )}>
                      {systemHealth.api.error_rate}%
                    </p>
                    <p className="text-xs text-muted-foreground">Error Rate</p>
                  </div>
                </div>
                <div className="space-y-3">
                  <ResourceBar label="Latency p50" value={systemHealth.api.latency_p50_ms} max={500} unit="ms" />
                  <ResourceBar label="CPU" value={systemHealth.resources?.cpu_percent ?? 0} max={100} unit="%" />
                  <ResourceBar label="Memory" value={systemHealth.resources?.memory_percent ?? 0} max={100} unit="%" />
                  <ResourceBar label="Disk" value={systemHealth.resources?.disk_percent ?? 0} max={100} unit="%" />
                </div>
              </div>
            )}
          </div>

          {/* Quick Actions */}
          <div className="rounded-xl border bg-card p-6 shadow-card motion-card">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5 text-primary" />
              Quick Actions
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {[
                { icon: Database, label: 'Backup Database', color: 'text-info' },
                { icon: RefreshCw, label: 'Clear Cache', color: 'text-success' },
                { icon: Key, label: 'Rotate Keys', color: 'text-warning' },
                { icon: Globe, label: 'CDN Purge', color: 'text-purple-500' },
                { icon: Activity, label: 'Health Check', color: 'text-cyan-500' },
              ].map((action, idx) => (
                <button
                  key={idx}
                  className="flex flex-col items-center gap-2 p-4 rounded-lg border hover:bg-muted transition-colors motion-card"
                >
                  <action.icon className={cn('w-6 h-6', action.color)} />
                  <span className="text-xs font-medium text-center">{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          Audit Log Tab
      ========================================================================= */}
      {activeTab === 'audit' && (
        <div className="space-y-4 motion-enter">
          {/* Filters */}
          <div className="flex items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search actions..."
                value={auditFilter.action}
                onChange={(e) => setAuditFilter(f => ({ ...f, action: e.target.value }))}
                className="w-full pl-10 pr-4 py-2 rounded-lg border bg-background focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <button
              onClick={handleRefresh}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border hover:bg-muted"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>

          {/* Audit Log Table */}
          <div className="rounded-xl border bg-card shadow-card overflow-hidden">
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/30">
                <tr>
                  <th scope="col" className="text-left py-3 px-4 font-medium">Timestamp</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium">Action</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium">User</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium">Resource</th>
                  <th scope="col" className="text-center py-3 px-4 font-medium">Status</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-muted-foreground">
                      <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>No audit logs found</p>
                      <p className="text-xs mt-1">Admin actions will appear here after the database migration</p>
                    </td>
                  </tr>
                ) : (
                  auditLogs
                    .filter(log => {
                      if (auditFilter.action && !log.action?.toLowerCase().includes(auditFilter.action.toLowerCase())) return false
                      return true
                    })
                    .map((log, idx) => (
                      <tr key={log.id} className="hover:bg-muted/30 motion-enter" style={{ animationDelay: `${idx * 10}ms` }}>
                        <td className="py-3 px-4 text-muted-foreground">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString() : '-'}
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-medium">{log.action}</span>
                        </td>
                        <td className="py-3 px-4">{log.user_email || `User #${log.user_id}`}</td>
                        <td className="py-3 px-4">
                          {log.resource_type && (
                            <span className="text-muted-foreground">
                              {log.resource_type}
                              {log.resource_id && <span className="ml-1">#{log.resource_id}</span>}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {log.success ? (
                            <CheckCircle2 className="w-4 h-4 text-success mx-auto" />
                          ) : (
                            <XCircle className="w-4 h-4 text-danger mx-auto" />
                          )}
                        </td>
                        <td className="py-3 px-4 text-muted-foreground text-xs max-w-52 truncate">
                          {log.details ? JSON.stringify(log.details) : '-'}
                        </td>
                      </tr>
                    ))
                )}
              </tbody>
            </table>
            </div>
          </div>
        </div>
      )}
    </div>
    </ErrorBoundary>
  )
}

// =============================================================================
// Sub-Components
// =============================================================================
function MetricCard({
  label,
  value,
  status,
}: {
  label: string
  value: string | number
  status: 'green' | 'amber' | 'red' | 'blue'
}) {
  const statusColors = {
    green: 'text-success',
    amber: 'text-warning',
    red: 'text-danger',
    blue: 'text-info',
  }

  return (
    <div className="rounded-xl border bg-card p-4 shadow-card motion-card">
      <p className="text-sm text-muted-foreground mb-1">{label}</p>
      <p className={cn('text-xl font-bold capitalize', statusColors[status])}>{value}</p>
    </div>
  )
}

function HealthRow({
  label,
  value,
  status,
}: {
  label: string
  value: string
  status: 'green' | 'amber' | 'red'
}) {
  const icons = {
    green: <CheckCircle2 className="w-4 h-4 text-success" />,
    amber: <AlertCircle className="w-4 h-4 text-warning" />,
    red: <AlertTriangle className="w-4 h-4 text-danger" />,
  }

  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
      <span className="text-sm">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-medium">{value}</span>
        {icons[status]}
      </div>
    </div>
  )
}

function HealthBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    healthy: 'bg-success/10 text-success',
    risk: 'bg-warning/10 text-warning',
    degraded: 'bg-orange-500/10 text-orange-500',
    critical: 'bg-danger/10 text-danger',
  }

  const icons: Record<string, React.ReactNode> = {
    healthy: <CheckCircle2 className="w-3 h-3" />,
    risk: <AlertCircle className="w-3 h-3" />,
    degraded: <AlertTriangle className="w-3 h-3" />,
    critical: <XCircle className="w-3 h-3" />,
  }

  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium capitalize', colors[status] || colors.healthy)}>
      {icons[status]}
      {status}
    </span>
  )
}

function ResourceBar({
  label,
  value,
  max = 100,
  unit = '%',
}: {
  label: string
  value: number
  max?: number
  unit?: string
}) {
  const percentage = (value / max) * 100
  const getColor = (v: number) => {
    if (v >= 80) return 'bg-danger'
    if (v >= 60) return 'bg-warning'
    return 'bg-success'
  }

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{value}{unit}</span>
      </div>
      <div className="w-full h-2 bg-muted rounded-full">
        <div
          className={cn('h-full rounded-full transition-[width]', getColor(percentage))}
          style={{ width: `${Math.min(100, percentage)}%` }}
        />
      </div>
    </div>
  )
}
