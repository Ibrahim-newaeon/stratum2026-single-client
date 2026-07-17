import { describe, it, expect } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { getApiErrorMessage, getApiErrorCode } from './client';

function axiosErrorWith(data: unknown, status = 400): AxiosError {
  const config = { headers: new AxiosHeaders() };
  return new AxiosError(
    `Request failed with status code ${status}`,
    'ERR_BAD_REQUEST',
    config as never,
    undefined,
    {
      status,
      statusText: '',
      headers: {},
      config: config as never,
      data,
    }
  );
}

describe('getApiErrorMessage', () => {
  it('prefers FastAPI detail over the generic axios message', () => {
    const err = axiosErrorWith(
      { detail: 'Public signup is disabled. Ask your organization owner for an invite.' },
      403
    );
    expect(getApiErrorMessage(err)).toBe(
      'Public signup is disabled. Ask your organization owner for an invite.'
    );
  });

  it('falls back to the ApiResponse message field', () => {
    const err = axiosErrorWith({ success: false, message: 'Invalid or expired OTP code' });
    expect(getApiErrorMessage(err)).toBe('Invalid or expired OTP code');
  });

  it('uses the axios message when the body has no usable text', () => {
    const err = axiosErrorWith({ detail: [{ loc: ['body'], msg: 'x' }] }, 422);
    expect(getApiErrorMessage(err)).toBe('Request failed with status code 422');
  });

  it('handles plain Errors and unknowns with a fallback', () => {
    expect(getApiErrorMessage(new Error('boom'))).toBe('boom');
    expect(getApiErrorMessage(undefined, 'fallback text')).toBe('fallback text');
  });
});

describe('object-shaped detail (typed backend errors)', () => {
  it('reads detail.message and detail.code', () => {
    const err = axiosErrorWith(
      { detail: { code: 'credentials_not_configured', message: 'Meta app credentials are not configured.' } },
      400
    );
    expect(getApiErrorMessage(err)).toBe('Meta app credentials are not configured.');
    expect(getApiErrorCode(err)).toBe('credentials_not_configured');
  });

  it('getApiErrorCode returns null when absent', () => {
    expect(getApiErrorCode(axiosErrorWith({ detail: 'plain' }))).toBeNull();
    expect(getApiErrorCode(new Error('x'))).toBeNull();
  });
});
