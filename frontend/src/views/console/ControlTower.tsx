/**
 * Platform Owner Control Tower
 *
 * Primary goal: platform-wide signal health + systemic risk visibility.
 *
 * NOTE(STRAT-SC-001/D3): the per-tenant portfolio KPIs (MRR, active
 * tenants, churn risk, tenant health list) that used to live here read
 * from console routes C3 deleted (/console/revenue, /console/tenants/
 * portfolio, /console/churn/risks — their sole data source was the
 * deleted Tenant model). Replaced with the still-alive EMQ portfolio
 * rollup (/emq/portfolio, /emq/benchmarks) and the reduced owner
 * dashboard summary (/console/dashboard: usage/health/alerts).
 */

import {
  useEmqBenchmarks,
  useEmqPortfolio,
  useConsoleOverview,
} from '@/api/hooks'
import {
  ExclamationTriangleIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  UsersIcon,
  Squares2X2Icon,
} from '@heroicons/react/24/outline'
import { useNavigate } from 'react-router-dom'

export default function ControlTower() {
  const navigate = useNavigate()

  // Fetch data from multiple endpoints
  const { data: portfolioData } = useEmqPortfolio()
  const { data: benchmarksData } = useEmqBenchmarks()
  const { data: overviewData } = useConsoleOverview()

  // EMQ benchmarks
  const benchmarks = benchmarksData ?? []

  // Top issues
  const topIssues = portfolioData?.topIssues ?? []

  const byBand = portfolioData?.byBand ?? { reliable: 0, directional: 0, unsafe: 0 }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Control Tower</h1>
          <p className="text-muted-foreground">Platform overview & account health</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard/owner')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-secondary border border-foreground/10 text-muted-foreground hover:text-white transition-colors"
          >
            <Cog6ToothIcon className="w-4 h-4" />
            System Settings
          </button>
        </div>
      </div>

      {/* Platform KPIs */}
      <div data-tour="portfolio-kpis" className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-surface-secondary border border-foreground/10">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <ChartBarIcon className="w-4 h-4" />
            <span className="text-sm">Avg EMQ Score</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {portfolioData?.avgScore ?? '—'}
          </div>
          <div className="text-sm text-muted-foreground mt-1">
            across tracked accounts
          </div>
        </div>

        <div className="p-4 rounded-xl bg-surface-secondary border border-foreground/10">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <Squares2X2Icon className="w-4 h-4" />
            <span className="text-sm">Campaigns</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {overviewData?.usage.total_campaigns ?? 0}
          </div>
          <div className="text-sm text-muted-foreground mt-1">
            {overviewData?.usage.total_users ?? 0} users
          </div>
        </div>

        <div className="p-4 rounded-xl bg-surface-secondary border border-foreground/10">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <UsersIcon className="w-4 h-4" />
            <span className="text-sm">Confidence Bands</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {byBand.reliable}/{byBand.directional}/{byBand.unsafe}
          </div>
          <div className="text-sm text-muted-foreground mt-1">
            reliable / directional / unsafe
          </div>
        </div>

        <div className="p-4 rounded-xl bg-surface-secondary border border-danger/20">
          <div className="flex items-center gap-2 text-muted-foreground mb-2">
            <ExclamationTriangleIcon className="w-4 h-4 text-danger" />
            <span className="text-sm">Budget at Risk</span>
          </div>
          <div className="text-2xl font-bold text-danger">
            ${((portfolioData?.atRiskBudget ?? 0) / 1000).toFixed(0)}K
          </div>
          <div className="text-sm text-muted-foreground mt-1">
            {overviewData?.alerts.critical ?? 0} critical alerts (24h)
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* EMQ Benchmarks */}
          <div data-tour="emq-benchmarks" className="rounded-2xl bg-surface-secondary border border-foreground/10 overflow-hidden">
            <div className="p-4 border-b border-foreground/10">
              <h3 className="font-semibold text-white">EMQ Benchmarks</h3>
              <p className="text-sm text-muted-foreground">P25 / P50 / P75 by platform</p>
            </div>
            <div className="p-4 space-y-4">
              {benchmarks.map((b) => (
                <div key={b.platform}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white">{b.platform}</span>
                    <span className="text-sm text-muted-foreground">
                      {b.p25} / {b.p50} / {b.p75}
                    </span>
                  </div>
                  <div className="relative h-2 bg-foreground/10 rounded-full">
                    {/* P25 marker */}
                    <div
                      className="absolute top-0 h-2 bg-danger/50 rounded-l-full"
                      style={{ width: `${b.p25}%` }}
                    />
                    {/* P50 marker */}
                    <div
                      className="absolute top-0 h-2 bg-warning/50"
                      style={{ left: `${b.p25}%`, width: `${b.p50 - b.p25}%` }}
                    />
                    {/* P75 marker */}
                    <div
                      className="absolute top-0 h-2 bg-success/50 rounded-r-full"
                      style={{ left: `${b.p50}%`, width: `${b.p75 - b.p50}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Top Issues */}
          <div data-tour="top-issues" className="rounded-2xl bg-surface-secondary border border-foreground/10 overflow-hidden">
            <div className="p-4 border-b border-foreground/10">
              <h3 className="font-semibold text-white">Top Issues</h3>
              <p className="text-sm text-muted-foreground">Affecting the most accounts</p>
            </div>
            <div className="p-4 space-y-3">
              {topIssues.map((issue, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-sm text-white">{issue.driver}</span>
                  <span className="text-sm text-danger">
                    {issue.affectedTenants} accounts
                  </span>
                </div>
              ))}
            </div>
          </div>
      </div>

      {/* Autopilot Distribution */}
      <div data-tour="autopilot-distribution" className="rounded-2xl bg-surface-secondary border border-foreground/10 overflow-hidden">
        <div className="p-4 border-b border-foreground/10">
          <h3 className="font-semibold text-white">Autopilot Modes</h3>
        </div>
        <div className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="flex-1 h-3 rounded-full overflow-hidden flex">
              <div className="bg-success h-full" style={{ width: '60%' }} />
              <div className="bg-warning h-full" style={{ width: '20%' }} />
              <div className="bg-orange-500 h-full" style={{ width: '10%' }} />
              <div className="bg-danger h-full" style={{ width: '10%' }} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-success" />
              <span className="text-muted-foreground">Normal (60%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-warning" />
              <span className="text-muted-foreground">Limited (20%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-orange-500" />
              <span className="text-muted-foreground">Cuts Only (10%)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-danger" />
              <span className="text-muted-foreground">Frozen (10%)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
