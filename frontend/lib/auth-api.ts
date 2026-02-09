import { apiClient } from './api-client'

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterCredentials {
  email: string
  password: string
  name: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: {
    id: string
    email: string
    name: string
    role: string
    is_active: boolean
    created_at: string
  }
}

export interface UpdateProfileData {
  name?: string
  email?: string
  current_password?: string
  new_password?: string
}

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const formData = new URLSearchParams()
    formData.append('username', credentials.email)
    formData.append('password', credentials.password)
    
    const response = await apiClient.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
    return response.data
  },

  register: async (credentials: RegisterCredentials): Promise<AuthResponse> => {
    const response = await apiClient.post('/auth/register', credentials)
    return response.data
  },

  getMe: async () => {
    const response = await apiClient.get('/auth/me')
    return response.data
  },

  updateProfile: async (data: UpdateProfileData) => {
    const response = await apiClient.patch('/users/me', data)
    return response.data
  },

  logout: async () => {
    // Optional: Call backend logout endpoint if exists
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // Ignore logout errors
    }
  },
}

export default authApi
