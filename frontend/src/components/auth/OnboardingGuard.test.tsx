import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const { mockState } = vi.hoisted(() => ({
  mockState: { role: 'owner' as string, required: true },
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { role: mockState.role } }),
}));
vi.mock('@/api/onboarding', () => ({
  useOnboardingCheck: () => ({
    data: { required: mockState.required, redirect_to: null },
    isLoading: false,
    error: null,
  }),
}));

import OnboardingGuard from './OnboardingGuard';

function renderGuarded() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route
          path="/dashboard"
          element={
            <OnboardingGuard>
              <div>DASHBOARD</div>
            </OnboardingGuard>
          }
        />
        <Route path="/onboarding" element={<div>WIZARD</div>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  mockState.role = 'owner';
  mockState.required = true;
});

describe('OnboardingGuard role gating', () => {
  it('redirects owner to the wizard while onboarding is required', () => {
    renderGuarded();
    expect(screen.getByText('WIZARD')).toBeInTheDocument();
  });

  it('redirects admin too', () => {
    mockState.role = 'admin';
    renderGuarded();
    expect(screen.getByText('WIZARD')).toBeInTheDocument();
  });

  it.each(['manager', 'analyst', 'viewer'])(
    'lets %s through even while onboarding is required',
    (role) => {
      mockState.role = role;
      renderGuarded();
      expect(screen.getByText('DASHBOARD')).toBeInTheDocument();
    }
  );

  it('lets everyone through once onboarding is done', () => {
    mockState.required = false;
    mockState.role = 'viewer';
    renderGuarded();
    expect(screen.getByText('DASHBOARD')).toBeInTheDocument();
  });
});
