import React from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import useAuthStore from '../store/authStore';

// Mock the Zustand store
jest.mock('../store/authStore', () => ({
  __esModule: true,
  default: jest.fn()
}));

describe('ProtectedRoute', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  const TestComponent = () => <div>Protected Content</div>;
  const LoginComponent = () => <div>Login Page</div>;

  const renderWithRouter = (isAuthenticated) => {
    useAuthStore.mockImplementation((selector) => {
      const state = {
        isAuthenticated,
        user: isAuthenticated ? {} : null,
      };
      return selector ? selector(state) : state;
    });

    return render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<LoginComponent />} />
          <Route 
            path="/protected" 
            element={
              <ProtectedRoute>
                <TestComponent />
              </ProtectedRoute>
            } 
          />
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders children if user is authenticated', () => {
    const { getByText } = renderWithRouter(true);
    expect(getByText('Protected Content')).toBeTruthy();
  });

  it('redirects to /login if user is not authenticated', () => {
    const { getByText } = renderWithRouter(false);
    expect(getByText('Login Page')).toBeTruthy();
  });
});
