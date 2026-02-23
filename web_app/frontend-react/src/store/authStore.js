import { create } from 'zustand';

const useAuthStore = create((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  
  setAuth: (user, token) => {
    localStorage.setItem('ai-council-auth', JSON.stringify({ state: { user, token, isAuthenticated: true } }));
    set({ user, token, isAuthenticated: true });
  },
  
  logout: () => {
    localStorage.removeItem('ai-council-auth');
    set({ user: null, token: null, isAuthenticated: false });
  },
  
  updateUser: (userData) => set((state) => ({
    user: { ...state.user, ...userData }
  })),
  
  // Initialize from localStorage
  init: () => {
    const stored = localStorage.getItem('ai-council-auth');
    if (stored) {
      try {
        const { state } = JSON.parse(stored);
        if (state.token) {
          set({ user: state.user, token: state.token, isAuthenticated: true });
        }
      } catch (e) {
        console.error('Failed to parse auth state');
      }
    }
  }
}));

// Initialize on load
useAuthStore.getState().init();

export default useAuthStore;
