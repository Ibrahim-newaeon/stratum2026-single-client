import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// vi.mock factories are hoisted above imports and const declarations —
// everything they reference must come from vi.hoisted().
const { DETAIL, forbidden, inertMutation } = vi.hoisted(() => {
  const DETAIL = 'Public signup is disabled. Ask your organization owner for an invite.';
  return {
    DETAIL,
    // Shaped like an AxiosError; axios.isAxiosError() keys on isAxiosError.
    forbidden: {
      isAxiosError: true,
      name: 'AxiosError',
      message: 'Request failed with status code 403',
      response: { status: 403, data: { detail: DETAIL } },
    },
    inertMutation: () => ({
      mutate: () => undefined,
      isPending: false,
      isSuccess: false,
      isError: false,
      error: null,
    }),
  };
});

vi.mock('@/api/auth', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useSignup: () => ({ ...inertMutation(), error: forbidden, isError: true }),
    useSendWhatsAppOTP: inertMutation,
    useVerifyWhatsAppOTP: inertMutation,
    useSendEmailOTP: inertMutation,
    useVerifyEmailOTP: inertMutation,
  };
});

import Signup from './Signup';

describe('Signup when public signup is disabled (register 403)', () => {
  it('replaces the form with an invite-only notice and a login link', () => {
    render(
      <MemoryRouter>
        <Signup />
      </MemoryRouter>
    );
    expect(screen.getByText(DETAIL)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /log ?in/i })).toHaveAttribute('href', '/login');
    // The signup form fields must be gone — no dead-end retries.
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });
});
