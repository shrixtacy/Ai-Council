import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import ResetPassword from './ResetPassword';
import toast from 'react-hot-toast';
import { authAPI } from '../utils/api';

const mockNavigate = jest.fn();

jest.mock('react-hot-toast');
jest.mock('../utils/api', () => ({
  authAPI: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useParams: jest.fn(),
    useNavigate: () => mockNavigate,
  };
});

const { MemoryRouter, useParams } = require('react-router-dom');

const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('ResetPassword Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.scrollTo = jest.fn();
    useParams.mockReturnValue({ token: 'reset-token-123' });
  });

  it('shows invalid link state when token verification fails', async () => {
    authAPI.get.mockRejectedValueOnce({
      response: { data: { message: 'Invalid token' } },
    });

    renderWithRouter(<ResetPassword />);

    await waitFor(() => {
      expect(authAPI.get).toHaveBeenCalledWith('/auth/verify-reset-token/reset-token-123');
      expect(screen.getByRole('heading', { name: /invalid link/i })).toBeInTheDocument();
      expect(toast.error).toHaveBeenCalledWith('This password reset link is invalid or has expired');
    });
  });

  it('blocks submit when passwords do not match', async () => {
    authAPI.get.mockResolvedValueOnce({
      data: { success: true, expiresAt: new Date(Date.now() + 60_000).toISOString() },
    });

    const { container } = renderWithRouter(<ResetPassword />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /set new password/i })).toBeInTheDocument();
    });

    const passwordInputs = screen.getAllByPlaceholderText(/••••••••/i);
    fireEvent.change(passwordInputs[0], { target: { name: 'password', value: 'StrongPass1!' } });
    fireEvent.change(passwordInputs[1], { target: { name: 'confirmPassword', value: 'Mismatch1!' } });

    const form = container.querySelector('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Passwords do not match');
      expect(authAPI.post).not.toHaveBeenCalled();
    });
  });

  it('resets password successfully and redirects to login', async () => {
    jest.useFakeTimers();

    authAPI.get.mockResolvedValueOnce({
      data: { success: true, expiresAt: new Date(Date.now() + 60_000).toISOString() },
    });

    authAPI.post.mockResolvedValueOnce({ data: { success: true } });

    renderWithRouter(<ResetPassword />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /set new password/i })).toBeInTheDocument();
    });

    const passwordInputs = screen.getAllByPlaceholderText(/••••••••/i);
    fireEvent.change(passwordInputs[0], { target: { name: 'password', value: 'StrongPass1!' } });
    fireEvent.change(passwordInputs[1], { target: { name: 'confirmPassword', value: 'StrongPass1!' } });

    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));

    await waitFor(() => {
      expect(authAPI.post).toHaveBeenCalledWith('/auth/reset-password', {
        token: 'reset-token-123',
        password: 'StrongPass1!',
      });
      expect(toast.success).toHaveBeenCalledWith('Password reset successful!');
    });

    act(() => {
      jest.advanceTimersByTime(3000);
    });

    expect(mockNavigate).toHaveBeenCalledWith('/login');
    jest.useRealTimers();
  });
});
