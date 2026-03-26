import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VerifyEmailReminder from './VerifyEmailReminder';
import { authAPI } from '../utils/api';
import toast from 'react-hot-toast';

jest.mock('react-hot-toast');
jest.mock('../utils/api', () => ({
  authAPI: {
    post: jest.fn(),
  },
}));

describe('VerifyEmailReminder Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders reminder content and resend button', () => {
    render(<VerifyEmailReminder />);

    expect(screen.getByRole('heading', { name: /verify your email/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /resend verification email/i })).toBeInTheDocument();
  });

  it('resends verification email successfully', async () => {
    authAPI.post.mockResolvedValueOnce({ data: { success: true } });

    render(<VerifyEmailReminder />);

    fireEvent.click(screen.getByRole('button', { name: /resend verification email/i }));

    await waitFor(() => {
      expect(authAPI.post).toHaveBeenCalledWith('/auth/resend-verification');
      expect(toast.success).toHaveBeenCalledWith('Verification email sent! Check your inbox.');
    });
  });

  it('shows API error message on resend failure', async () => {
    authAPI.post.mockRejectedValueOnce({
      response: { data: { message: 'Too many requests' } },
    });

    render(<VerifyEmailReminder />);

    fireEvent.click(screen.getByRole('button', { name: /resend verification email/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Too many requests');
    });
  });

  it('shows fallback error message on resend failure without API message', async () => {
    authAPI.post.mockRejectedValueOnce(new Error('Network down'));

    render(<VerifyEmailReminder />);

    fireEvent.click(screen.getByRole('button', { name: /resend verification email/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to resend email');
    });
  });
});
