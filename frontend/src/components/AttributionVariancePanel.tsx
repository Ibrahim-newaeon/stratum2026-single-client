/**
 * Stratum AI - Attribution Variance Panel Component
 *
 * Displays attribution variance between ad platforms and GA4.
 * Helps identify discrepancies in revenue and conversion tracking.
 */

import React, { useState } from 'react'
import {
  useAttributionVariance,
  PlatformVarianceRow,
  MetricCard,
  getStatusLabel,
} from '@/api/trustLayer'
import { useCanFeature } from '@/stores/featureFlagsStore'

// =============================================================================
// Types
// =============================================================================

interface AttributionVariancePanelProps {
  tenantId: number
  date?: string
  compact?: boolean
}

// =============================================================================
// Sub-components
// =============================================================================

const MetricCardComponent: React.FC<{ card: MetricCard }> = ({ card }) => {
  const statusColors: Record<string, string> = {
    ok: 'border-green-200 bg-green-50',
    risk: 'border-yellow-200 bg-yellow-50',
    degraded: 'border-orange-200 bg-orange-50',
    neutral: 'border-border bg-muted',
  }

  const valueColors: Record<string, string> = {
    ok: 'text-green-700',
    risk: 'text-yellow-700',
    degraded: 'text-orange-700',
    neutral: 'text-muted-foreground',
  }

  return (
    <div className={`rounded-lg border p-4 ${statusColors[card.status]}`}>
      <div className="text-sm font-medium text-muted-foreground">{card.title}</div>
      <div className={`text-2xl font-bold mt-1 ${valueColors[card.status]}`}>
        {card.value}
      </div>
    </div>
  )
}

const VarianceBar: React.FC<{ variance: number }> = ({ variance }) => {
  const absVariance = Math.abs(variance)
  const width = Math.min(absVariance, 100)
  const isPositive = variance >= 0

  return (
    <div className="flex items-center space-x-2">
      <div className="w-24 h-4 bg-muted rounded-full overflow-hidden relative">
        <div className="absolute inset-y-0 left-1/2 w-0.5 bg-border" />
        <div
          className={`absolute inset-y-0 ${isPositive ? 'left-1/2' : 'right-1/2'} ${
            absVariance < 15 ? 'bg-green-400' :
            absVariance < 30 ? 'bg-yellow-400' :
            'bg-red-400'
          }`}
          style={{ width: `${width / 2}%` }}
        />
      </div>
      <span className={`text-sm font-medium ${
        absVariance < 15 ? 'text-green-600' :
        absVariance < 30 ? 'text-yellow-600' :
        'text-red-600'
      }`}>
        {variance >= 0 ? '+' : ''}{variance.toFixed(1)}%
      </span>
    </div>
  )
}

const PlatformVarianceRowComponent: React.FC<{ row: PlatformVarianceRow }> = ({ row }) => {
  const statusColors: Record<string, string> = {
    healthy: 'bg-green-100 text-green-800',
    minor_variance: 'bg-yellow-100 text-yellow-800',
    moderate_variance: 'bg-orange-100 text-orange-800',
    high_variance: 'bg-red-100 text-red-800',
    no_data: 'bg-muted text-muted-foreground',
  }

  const platformIcons: Record<string, string> = {
    meta: '📘',
    google: '🔴',
    tiktok: '🎵',
    snapchat: '👻',
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value)
  }

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat('en-US').format(value)
  }

  return (
    <tr className="border-b border-border hover:bg-muted">
      <td className="py-3 px-4">
        <div className="flex items-center space-x-2">
          <span className="text-lg">{platformIcons[row.platform] || '📊'}</span>
          <span className="font-medium text-foreground capitalize">{row.platform}</span>
        </div>
      </td>
      <td className="py-3 px-4 text-right">
        <div className="text-sm text-foreground">{formatCurrency(row.ga4_revenue)}</div>
        <div className="text-xs text-muted-foreground">{formatNumber(row.ga4_conversions)} conv</div>
      </td>
      <td className="py-3 px-4 text-right">
        <div className="text-sm text-foreground">{formatCurrency(row.platform_revenue)}</div>
        <div className="text-xs text-muted-foreground">{formatNumber(row.platform_conversions)} conv</div>
      </td>
      <td className="py-3 px-4">
        <VarianceBar variance={row.revenue_delta_pct} />
      </td>
      <td className="py-3 px-4 text-center">
        <div className="flex items-center justify-center">
          <div className="w-16 bg-muted rounded-full h-2 mr-2">
            <div
              className={`h-2 rounded-full ${
                row.confidence >= 0.8 ? 'bg-green-500' :
                row.confidence >= 0.5 ? 'bg-yellow-500' :
                'bg-red-500'
              }`}
              style={{ width: `${row.confidence * 100}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground">{(row.confidence * 100).toFixed(0)}%</span>
        </div>
      </td>
      <td className="py-3 px-4 text-center">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[row.status]}`}>
          {getStatusLabel(row.status)}
        </span>
      </td>
    </tr>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export const AttributionVariancePanel: React.FC<AttributionVariancePanelProps> = ({
  tenantId,
  date,
  compact = false,
}) => {
  const canAttributionVariance = useCanFeature('attribution_variance')
  const [expanded, setExpanded] = useState(!compact)

  const { data, isLoading, error, refetch } = useAttributionVariance(tenantId, date)

  if (!canAttributionVariance) {
    return (
      <div className="bg-muted rounded-lg border border-border p-6 text-center">
        <div className="text-muted-foreground">
          Attribution Variance feature is not enabled for your plan.
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="bg-card rounded-lg border border-border p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-muted rounded w-1/4" />
          <div className="grid grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 bg-muted rounded" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 rounded-lg border border-red-200 p-6">
        <div className="text-red-700">Failed to load attribution variance data.</div>
        <button
          onClick={() => refetch()}
          className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
        >
          Try again
        </button>
      </div>
    )
  }

  if (!data) {
    return null
  }

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div
        className="px-6 py-4 border-b border-border flex items-center justify-between cursor-pointer hover:bg-muted"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center space-x-3">
          <h3 className="text-lg font-semibold text-foreground">Attribution Variance</h3>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            data.status === 'healthy' ? 'bg-green-100 text-green-800' :
            data.status === 'minor_variance' ? 'bg-yellow-100 text-yellow-800' :
            data.status === 'moderate_variance' ? 'bg-orange-100 text-orange-800' :
            data.status === 'high_variance' ? 'bg-red-100 text-red-800' :
            'bg-muted text-muted-foreground'
          }`}>
            {getStatusLabel(data.status)}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-muted-foreground">{data.date}</span>
          <svg
            className={`w-5 h-5 text-muted-foreground transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </div>
      </div>

      {/* Content */}
      {expanded && (
        <div className="p-6 space-y-6">
          {/* Metric Cards */}
          {data.cards.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {data.cards.map((card, index) => (
                <MetricCardComponent key={index} card={card} />
              ))}
            </div>
          )}

          {/* Variance Summary */}
          <div className="bg-muted rounded-lg p-4">
            <div className="grid grid-cols-2 gap-6">
              <div>
                <div className="text-sm text-muted-foreground mb-1">Overall Revenue Variance</div>
                <div className="flex items-center space-x-3">
                  <span className={`text-2xl font-bold ${
                    Math.abs(data.overall_revenue_variance_pct) < 15 ? 'text-green-600' :
                    Math.abs(data.overall_revenue_variance_pct) < 30 ? 'text-yellow-600' :
                    'text-red-600'
                  }`}>
                    {data.overall_revenue_variance_pct >= 0 ? '+' : ''}
                    {data.overall_revenue_variance_pct.toFixed(1)}%
                  </span>
                  <span className="text-sm text-muted-foreground">
                    Platform {data.overall_revenue_variance_pct >= 0 ? 'over' : 'under'}-reports vs GA4
                  </span>
                </div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Overall Conversion Variance</div>
                <div className="flex items-center space-x-3">
                  <span className={`text-2xl font-bold ${
                    Math.abs(data.overall_conversion_variance_pct) < 15 ? 'text-green-600' :
                    Math.abs(data.overall_conversion_variance_pct) < 30 ? 'text-yellow-600' :
                    'text-red-600'
                  }`}>
                    {data.overall_conversion_variance_pct >= 0 ? '+' : ''}
                    {data.overall_conversion_variance_pct.toFixed(1)}%
                  </span>
                  <span className="text-sm text-muted-foreground">
                    Platform {data.overall_conversion_variance_pct >= 0 ? 'over' : 'under'}-reports vs GA4
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Platform Table */}
          {data.platform_rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-muted border-b border-border">
                    <th scope="col" className="py-3 px-4 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Platform
                    </th>
                    <th scope="col" className="py-3 px-4 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      GA4
                    </th>
                    <th scope="col" className="py-3 px-4 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Platform
                    </th>
                    <th scope="col" className="py-3 px-4 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Revenue Variance
                    </th>
                    <th scope="col" className="py-3 px-4 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Confidence
                    </th>
                    <th scope="col" className="py-3 px-4 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.platform_rows.map((row, index) => (
                    <PlatformVarianceRowComponent key={index} row={row} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Banners */}
          {data.banners.length > 0 && (
            <div className="space-y-2">
              {data.banners.map((banner, index) => (
                <div
                  key={index}
                  className={`rounded-lg p-4 ${
                    banner.type === 'error' ? 'bg-red-50 border border-red-200' :
                    banner.type === 'warning' ? 'bg-yellow-50 border border-yellow-200' :
                    'bg-blue-50 border border-blue-200'
                  }`}
                >
                  <div className="flex items-start">
                    <div className="flex-1">
                      <h4 className={`text-sm font-medium ${
                        banner.type === 'error' ? 'text-red-800' :
                        banner.type === 'warning' ? 'text-yellow-800' :
                        'text-blue-800'
                      }`}>
                        {banner.title}
                      </h4>
                      <p className="mt-1 text-sm text-muted-foreground">{banner.message}</p>
                      {banner.actions.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {banner.actions.map((action, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-card border border-border text-muted-foreground"
                            >
                              {action}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Empty State */}
          {data.platform_rows.length === 0 && data.cards.length === 0 && (
            <div className="text-center py-8">
              <div className="text-muted-foreground text-4xl mb-3">📈</div>
              <div className="text-muted-foreground">No attribution variance data available for this date.</div>
              <div className="text-sm text-muted-foreground mt-1">
                Ensure GA4 is connected and data has synced.
              </div>
            </div>
          )}

          {/* Info Box */}
          <div className="bg-muted rounded-lg p-4 text-sm text-muted-foreground">
            <div className="flex items-start space-x-2">
              <svg className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <div>
                <strong>About Attribution Variance:</strong> Variance between platform-reported and GA4 data is normal
                due to different attribution windows and tracking methods. Variance under 15% is typically acceptable.
                Higher variance may indicate tracking issues or attribution window mismatches.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AttributionVariancePanel
