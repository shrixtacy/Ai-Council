import { create } from 'zustand';
import { jwtDecode } from "jwt-decode";
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
          const decoded = jwtDecode(state.token);

          if (decoded.exp * 1000 > Date.now()) {
            set({ user: state.user, token: state.token, isAuthenticated: true });
          } else {
            localStorage.removeItem('ai-council-auth');
          }
        }
      } catch (e) {
        console.error('Failed to parse auth state');
         localStorage.removeItem('ai-council-auth'); 
      }
    }
  }
}));

// Initialize on load
useAuthStore.getState().init();

export default useAuthStore;
