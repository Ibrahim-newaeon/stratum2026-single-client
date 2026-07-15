/**
 * Stratum AI - LegacySuperadminRedirect Tests
 *
 * The old superadmin shell lived at /dashboard/superadmin/*. Bookmarks
 * and external links to those URLs should land on the platform console
 * at /console/*, with the trailing segment mapped through.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import LegacySuperadminRedirect from './LegacySuperadminRedirect';

function ConsoleProbe() {
  const { pathname, search } = useLocation();
  return <div data-testid="console-page">{`${pathname}${search}`}</div>;
}

function renderAt(initialEntry: string) {
  // Wrap in Routes/Route so <Navigate> redirects land on a real path
  // (matches the pattern used by LegacyTenantRedirect.test.tsx).
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/dashboard/superadmin/*" element={<LegacySuperadminRedirect />} />
        <Route path="/console/*" element={<ConsoleProbe />} />
        <Route path="/console" element={<ConsoleProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('LegacySuperadminRedirect', () => {
  it('redirects /dashboard/superadmin/users to /console/users', () => {
    renderAt('/dashboard/superadmin/users');

    expect(screen.getByTestId('console-page')).toHaveTextContent('/console/users');
  });

  it('redirects the bare superadmin root to /console', () => {
    renderAt('/dashboard/superadmin');

    expect(screen.getByTestId('console-page').textContent).toBe('/console');
  });

  it('preserves the search string on redirect', () => {
    renderAt('/dashboard/superadmin/audit?range=30d');

    expect(screen.getByTestId('console-page').textContent).toBe('/console/audit?range=30d');
  });
});
