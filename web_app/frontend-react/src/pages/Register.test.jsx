import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Register from './Register';
import { authAPI } from '../utils/api';
import toast from 'react-hot-toast';

// Mock dependencies
jest.mock('react-hot-toast');
jest.mock('../utils/api', () => ({
  authAPI: {
    post: jest.fn()
  }
}));

const renderWithRouter = (ui) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
};

describe('Register Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders registration form properly', () => {
    renderWithRouter(<Register />);
    
    expect(screen.getByPlaceholderText(/John Doe/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/you@example.com/i)).toBeInTheDocument();
    const passwordInputs = screen.getAllByPlaceholderText(/••••••••/i);
    expect(passwordInputs).toHaveLength(2);
    expect(screen.getByRole('button', { name: /Create account/i })).toBeInTheDocument();
  });

  it('shows error if passwords do not match', async () => {
    renderWithRouter(<Register />);
    
    const passwordInputs = screen.getAllByPlaceholderText(/••••••••/i);
    fireEvent.change(screen.getByPlaceholderText(/John Doe/i), {
      target: { value: 'Test User' },
    });
    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(passwordInputs[0], {
      target: { value: 'password123' },
    });
    fireEvent.change(passwordInputs[1], {
      target: { value: 'password456' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /Create account/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Passwords do not match');
      expect(authAPI.post).not.toHaveBeenCalled();
    });
  });

  it('submits successfully when fields are valid', async () => {
    authAPI.post.mockResolvedValueOnce({ 
      data: { success: true, userId: 1 } 
    });
    
    renderWithRouter(<Register />);
    
    const passwordInputs = screen.getAllByPlaceholderText(/••••••••/i);
    fireEvent.change(screen.getByPlaceholderText(/John Doe/i), {
      target: { value: 'Test User' },
    });
    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(passwordInputs[0], {
      target: { value: 'password123' },
    });
    fireEvent.change(passwordInputs[1], {
      target: { value: 'password123' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /Create account/i }));

    await waitFor(() => {
      expect(authAPI.post).toHaveBeenCalledWith('/auth/register', {
        name: 'Test User',
        email: 'test@example.com',
        password: 'password123',
      });
      expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('Registration successful'));
    });
  });

  it('shows error when API call fails', async () => {
    authAPI.post.mockRejectedValueOnce({
      response: {
        data: {
          message: 'Email already registered'
        }
      }
    });
    
    renderWithRouter(<Register />);
    
    const passwordInputs = screen.getAllByPlaceholderText(/••••••••/i);
    fireEvent.change(screen.getByPlaceholderText(/John Doe/i), {
      target: { value: 'Test User' },
    });
    fireEvent.change(screen.getByPlaceholderText(/you@example.com/i), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(passwordInputs[0], {
      target: { value: 'password123' },
    });
    fireEvent.change(passwordInputs[1], {
      target: { value: 'password123' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /Create account/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Email already registered');
    });
  });
});