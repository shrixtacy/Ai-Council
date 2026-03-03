import { useEffect, useState } from 'react';
import { jwtDecode } from 'jwt-decode';
import useAuthStore from '../store/authStore';
import { authAPI } from '../utils/api';

export const useTokenManager = () => {
  const { token, logout, setAuth, user } = useAuthStore();
  const [timeUntilExpiry, setTimeUntilExpiry] = useState(0);
  const [showWarning, setShowWarning] = useState(false);

  useEffect(() => {
    if (!token) return;

    let decoded;
    try {
      decoded = jwtDecode(token);
    } catch {
      logout();
      return;
    }

    const expiryTime = decoded.exp * 1000;

    const interval = setInterval(() => {
      const remaining = expiryTime - Date.now();
      setTimeUntilExpiry(remaining);

      if (remaining <= 5 * 60 * 1000 && remaining > 0) {
        setShowWarning(true);
      }
      if (remaining <= 0) {
        logout();
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [token, logout]);

  const refreshToken = async () => {
    try {
      const { data } = await authAPI.post('/auth/refresh-token');
      setAuth(user, data.token);
      setShowWarning(false);
    } catch (error) {
      console.error('Failed to refresh token:', error);
    }
  };

  return { timeUntilExpiry, showWarning, refreshToken };
};

export default useTokenManager;
