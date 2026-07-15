/**
 * Stratum AI - LegacyAmTenantRedirect Tests
 *
 * The Account Manager narrative used to live at /dashboard/am/tenant/:tenantId.
 * Bookmarks and external links to those URLs should still land on the renamed
 * /dashboard/am/account/:accountId route, keeping the same ID segment.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import LegacyAmTenantRedirect from './LegacyAmTenantRedirect';

function NarrativeProbe() {
  const { pathname, search } = useLocation();
  return <div data-testid="narrative-page">{`${pathname}${search}`}</div>;
}

function renderAt(initialEntry: string) {
  // Wrap in Routes/Route so <Navigate> redirects land on a real path
  // (matches the pattern used by LegacyTenantRedirect.test.tsx).
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/dashboard/am/tenant/:tenantId" element={<LegacyAmTenantRedirect />} />
        <Route path="/dashboard/am/account/:accountId" element={<NarrativeProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('LegacyAmTenantRedirect', () => {
  it('redirects /dashboard/am/tenant/7 to /dashboard/am/account/7', () => {
    renderAt('/dashboard/am/tenant/7');

    expect(screen.getByTestId('narrative-page')).toHaveTextContent('/dashboard/am/account/7');
  });

  it('keeps the original ID segment on redirect', () => {
    renderAt('/dashboard/am/tenant/42');

    expect(screen.getByTestId('narrative-page').textContent).toBe('/dashboard/am/account/42');
  });

  it('preserves the search string on redirect', () => {
    renderAt('/dashboard/am/tenant/7?tab=playbook');

    expect(screen.getByTestId('narrative-page').textContent).toBe(
      '/dashboard/am/account/7?tab=playbook'
    );
  });
});
