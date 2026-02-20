import useAuthStore from './authStore';

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset Zustand store state before each test
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
    localStorage.clear();
    jest.clearAllMocks();
  });

  it('initially has no authenticated user', () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });

  it('updates state successfully via setAuth', () => {
    const user = { id: '1', name: 'Test User' };
    const token = 'test-token';
    
    useAuthStore.getState().setAuth(user, token);

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.token).toBe('test-token');
    expect(state.user.name).toBe('Test User');
    
    // Check localStorage
    const stored = JSON.parse(localStorage.getItem('ai-council-auth'));
    expect(stored.state.isAuthenticated).toBe(true);
    expect(stored.state.token).toBe('test-token');
  });

  it('clears state on logout', () => {
    // Set authenticated state manually
    useAuthStore.getState().setAuth({ id: '1', name: 'Test User' }, 'test-token');
    
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    
    // Call logout
    useAuthStore.getState().logout();
    
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
    expect(localStorage.getItem('ai-council-auth')).toBeNull();
  });
});
