import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ForgotPassword from './ForgotPassword';
import toast from 'react-hot-toast';
import { authAPI } from '../utils/api';

jest.mock('react-hot-toast');
jest.mock('../utils/api', () => ({
  authAPI: {
    post: jest.fn(),
  },
}));

const renderWithRouter = (ui) => render(<BrowserRouter>{ui}</BrowserRouter>);

describe('ForgotPassword Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders forgot password form', () => {
    renderWithRouter(<ForgotPassword />);

    expect(screen.getByRole('heading', { name: /forgot password\?/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/you@example.com/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument();
  });

  it('submits email successfully and shows confirmation state', async () => {
    authAPI.post.mockResolvedValueOnce({ data: { success: true } });

    renderWithRouter(<ForgotPassword />);

    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'user@example.com' },
    });

    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => {
      expect(authAPI.post).toHaveBeenCalledWith('/auth/forgot-password', {
        email: 'user@example.com',
      });
      expect(toast.success).toHaveBeenCalledWith('Check your email for reset instructions');
    });

    expect(screen.getByRole('heading', { name: /check your email/i })).toBeInTheDocument();
    expect(screen.getByText(/user@example.com/i)).toBeInTheDocument();
  });

  it('returns to form when user clicks try again in submitted state', async () => {
    authAPI.post.mockResolvedValueOnce({ data: { success: true } });

    renderWithRouter(<ForgotPassword />);

    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'user@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /check your email/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /try again/i }));

    expect(screen.getByRole('heading', { name: /forgot password\?/i })).toBeInTheDocument();
  });

  it('shows API error message on failure', async () => {
    authAPI.post.mockRejectedValueOnce({
      response: { data: { message: 'Email not found' } },
    });

    renderWithRouter(<ForgotPassword />);

    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'missing@example.com' },
    });

    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Email not found');
    });
  });
});
