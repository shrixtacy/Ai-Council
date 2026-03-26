import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VerifyOTP from './VerifyOTP';
import toast from 'react-hot-toast';
import useAuthStore from '../store/authStore';
import { authAPI } from '../utils/api';

const mockNavigate = jest.fn();
const mockSetAuth = jest.fn();

jest.mock('react-hot-toast');
jest.mock('../store/authStore');
jest.mock('../utils/api', () => ({
  authAPI: {
    post: jest.fn(),
  },
}));

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: jest.fn(),
  };
});

const { useLocation } = require('react-router-dom');

describe('VerifyOTP Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    useAuthStore.mockImplementation((selector) => {
      const state = { setAuth: mockSetAuth };
      return selector(state);
    });

    useLocation.mockReturnValue({
      state: {
        userId: 'user-123',
        email: 'test@example.com',
      },
    });
  });

  it('renders OTP screen with six input boxes', () => {
    render(<VerifyOTP />);

    expect(screen.getByText(/verify your email/i)).toBeInTheDocument();
    expect(screen.getByText(/test@example.com/i)).toBeInTheDocument();
    expect(screen.getAllByRole('textbox')).toHaveLength(6);
  });

  it('shows error for incomplete OTP and does not call API', async () => {
    render(<VerifyOTP />);

    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[0], { target: { value: '1' } });
    fireEvent.change(inputs[1], { target: { value: '2' } });

    fireEvent.click(screen.getByRole('button', { name: /verify email/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Please enter complete OTP');
      expect(authAPI.post).not.toHaveBeenCalled();
    });
  });

  it('verifies OTP successfully and navigates to dashboard', async () => {
    authAPI.post.mockResolvedValueOnce({
      data: {
        success: true,
        user: { id: 'user-123', email: 'test@example.com' },
        token: 'token-123',
      },
    });

    render(<VerifyOTP />);

    const inputs = screen.getAllByRole('textbox');
    ['1', '2', '3', '4', '5', '6'].forEach((digit, idx) => {
      fireEvent.change(inputs[idx], { target: { value: digit } });
    });

    fireEvent.click(screen.getByRole('button', { name: /verify email/i }));

    await waitFor(() => {
      expect(authAPI.post).toHaveBeenCalledWith('/auth/verify-otp', {
        userId: 'user-123',
        otp: '123456',
      });
      expect(mockSetAuth).toHaveBeenCalledWith(
        { id: 'user-123', email: 'test@example.com' },
        'token-123',
      );
      expect(toast.success).toHaveBeenCalledWith('Email verified successfully!');
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('handles verification failure and resets OTP', async () => {
    authAPI.post.mockRejectedValueOnce({
      response: { data: { message: 'Invalid OTP' } },
    });

    render(<VerifyOTP />);

    const inputs = screen.getAllByRole('textbox');
    ['1', '2', '3', '4', '5', '6'].forEach((digit, idx) => {
      fireEvent.change(inputs[idx], { target: { value: digit } });
    });

    fireEvent.click(screen.getByRole('button', { name: /verify email/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Invalid OTP');
      expect(inputs[0]).toHaveValue('');
      expect(inputs[5]).toHaveValue('');
    });
  });

  it('resends OTP successfully', async () => {
    authAPI.post.mockResolvedValueOnce({ data: { success: true } });

    render(<VerifyOTP />);

    fireEvent.click(screen.getByRole('button', { name: /resend otp/i }));

    await waitFor(() => {
      expect(authAPI.post).toHaveBeenCalledWith('/auth/resend-otp', { userId: 'user-123' });
      expect(toast.success).toHaveBeenCalledWith('OTP resent successfully!');
    });
  });

  it('redirects to register when userId is missing', async () => {
    useLocation.mockReturnValueOnce({ state: {} });

    render(<VerifyOTP />);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/register');
    });
  });
});
