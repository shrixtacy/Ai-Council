import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Login from './Login';
import useAuthStore from '../store/authStore';
import toast from 'react-hot-toast';

import { authAPI } from '../utils/api';

// Mock dependencies
jest.mock('../store/authStore');
jest.mock('react-hot-toast');
jest.mock('../utils/api', () => ({
  authAPI: {
    post: jest.fn()
  }
}));

const renderWithRouter = (ui) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
};

describe('Login Component', () => {
  const mockSetAuth = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.mockImplementation((selector) => {
      const state = {
        setAuth: mockSetAuth,
        loading: false,
        error: null,
      };
      return selector(state);
    });
  });

  it('renders login form correctly', () => {
    renderWithRouter(<Login />);
    
    expect(screen.getByPlaceholderText(/you@example.com/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/••••••••/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /Login/i })).toBeTruthy();
  });

  it('handles successful login submission', async () => {
    authAPI.post.mockResolvedValueOnce({
      data: { success: true, user: { id: 1 }, token: 'mock-token' }
    });
    
    renderWithRouter(<Login />);
    
    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/••••••••/i), {
      target: { value: 'password123' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /Login/i }));

    await waitFor(() => {
      expect(authAPI.post).toHaveBeenCalledWith('/auth/login', {
        email: 'test@example.com',
        password: 'password123',
      });
      expect(mockSetAuth).toHaveBeenCalledWith({ id: 1 }, 'mock-token');
      expect(toast.success).toHaveBeenCalledWith('Login successful!');
    });
  });

  it('handles login failure', async () => {
    authAPI.post.mockRejectedValueOnce({
      response: { data: { message: 'Invalid credentials' } }
    });
    
    renderWithRouter(<Login />);
    
    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'wrong@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/••••••••/i), {
      target: { value: 'wrongpass' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /Login/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Invalid credentials');
    });
  });

  it('redirects to verify-otp if needsVerification is true', async () => {
    authAPI.post.mockRejectedValueOnce({
      response: { data: { message: 'Please verify your email first', needsVerification: true, userId: '12345' } }
    });
    
    // We spy on the global window location or just assert the toast since we are rendering with BrowserRouter
    renderWithRouter(<Login />);
    
    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'unverified@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/••••••••/i), {
      target: { value: 'password123' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /Login/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Please verify your email first');
    });
  });
});
