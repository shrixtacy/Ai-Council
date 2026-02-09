'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { apiClient } from './api-client'

export interface User {
  id: string
  email: string
  name: string
  role: string
  is_active: boolean
  created_at: string
}

interface AuthState {
  token: string | null
  user: User | null
  isLoading: boolean
  setAuth: (token: string, user: User) => void
  setUser: (user: User) => void
  logout: () => void
  refreshUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoading: false,

      setAuth: (token: string, user: User) => {
        set({ token, user })
        // Update API client auth header
        if (apiClient.defaults) {
          apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
        }
      },

      setUser: (user: User) => {
        set({ user })
      },

      logout: () => {
        set({ token: null, user: null })
        // Clear API client auth header
        if (apiClient.defaults) {
          delete apiClient.defaults.headers.common['Authorization']
        }
        // Clear session storage for privacy
        if (typeof window !== 'undefined') {
          localStorage.removeItem('ai_council_session')
        }
      },

      refreshUser: async () => {
        const { token } = get()
        if (!token) return

        set({ isLoading: true })
        try {
          const response = await apiClient.get('/auth/me')
          set({ user: response.data, isLoading: false })
        } catch (error) {
          // If token is invalid, logout
          set({ token: null, user: null, isLoading: false })
          if (apiClient.defaults) {
            delete apiClient.defaults.headers.common['Authorization']
          }
        }
      },
    }),
    {
      name: 'ai-council-auth',
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
)
