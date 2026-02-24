import axios from 'axios';

const AUTH_API_URL = process.env.REACT_APP_AUTH_API_URL || 'http://localhost:5000/api';
const AI_API_URL = process.env.REACT_APP_AI_API_URL || 'http://localhost:8000/api';

// Auth API instance
export const authAPI = axios.create({
  baseURL: AUTH_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// AI Council API instance
export const aiAPI = axios.create({
  baseURL: AI_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
authAPI.interceptors.request.use((config) => {
  const token = localStorage.getItem('ai-council-auth');
  if (token) {
    const parsed = JSON.parse(token);
    if (parsed.state?.token) {
      config.headers.Authorization = `Bearer ${parsed.state.token}`;
    }
  }
  return config;
});

aiAPI.interceptors.request.use((config) => {
  const token = localStorage.getItem('ai-council-auth');
  if (token) {
    const parsed = JSON.parse(token);
    if (parsed.state?.token) {
      config.headers.Authorization = `Bearer ${parsed.state.token}`;
    }
  }
  return config;
});

// Handle 401 and 403 errors
const handleAuthErrors = (error) => {
  if (error.response?.status === 403 && error.response?.data?.code === 'EMAIL_NOT_VERIFIED') {
    window.location.href = '/verify-email';
    return Promise.reject(error);
  }
  if (error.response?.status === 401) {
    localStorage.removeItem('ai-council-auth');
    window.location.href = '/login';
  }
  return Promise.reject(error);
};

authAPI.interceptors.response.use((response) => response, handleAuthErrors);
aiAPI.interceptors.response.use((response) => response, handleAuthErrors);

const api = { authAPI, aiAPI };
export default api;
