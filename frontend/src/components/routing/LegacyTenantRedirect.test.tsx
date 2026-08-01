/**
 * ADs Growth System - LegacyTenantRedirect Tests
 *
 * The old multi-tenant shell lived at /app/:tenantId/*. Bookmarks and
 * external links to those URLs should still land on the single-client
 * /dashboard/* shell, with the tenant segment discarded.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import LegacyTenantRedirect from './LegacyTenantRedirect';

function DashboardProbe() {
  const { pathname, search } = useLocation();
  return <div data-testid="dashboard-page">{`${pathname}${search}`}</div>;
}

function renderAt(initialEntry: string) {
  // Wrap in Routes/Route so <Navigate> redirects land on a real path
  // (matches the pattern used by ProtectedRoute.test.tsx).
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/app/:tenantId/*" element={<LegacyTenantRedirect />} />
        <Route path="/dashboard/*" element={<DashboardProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('LegacyTenantRedirect', () => {
  it('redirects /app/7/campaigns to /dashboard/campaigns', () => {
    renderAt('/app/7/campaigns');

    expect(screen.getByTestId('dashboard-page')).toHaveTextContent('/dashboard/campaigns');
  });

  it('redirects the bare tenant root to /dashboard/overview', () => {
    renderAt('/app/7');

    expect(screen.getByTestId('dashboard-page')).toHaveTextContent('/dashboard/overview');
  });

  it('preserves the search string on redirect', () => {
    renderAt('/app/7/campaigns?focus=trust-holds');

    expect(screen.getByTestId('dashboard-page').textContent).toBe(
      '/dashboard/campaigns?focus=trust-holds'
    );
  });
});
