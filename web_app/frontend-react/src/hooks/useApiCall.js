// hooks/useApiCall.js
import { useState, useCallback, useRef, useEffect } from 'react'; 
import toast from 'react-hot-toast';

/**
 * Custom hook for managing API calls with loading, error, and retry states.
 *
 * @param {Function} apiFunction - The async API function to call
 * @param {Object} options - Configuration options
 * @param {boolean} options.showSuccessToast - Show a success toast on success
 * @param {string} options.successMessage - Custom success message
 * @param {boolean} options.showErrorToast - Show an error toast on failure (default: true)
 * @param {number} options.minLoadingMs - Minimum loading duration to prevent flicker (default: 300)
 */
export const useApiCall = (apiFunction, options = {}) => {
  const {
    showSuccessToast = false,
    successMessage = 'Done!',
    showErrorToast = true,
    minLoadingMs = 300,
  } = options;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const startTimeRef = useRef(null);
  const mountedRef = useRef(true);

  // Track mounted state to avoid memory leaks
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(
    async (...args) => {
      try {
        if (mountedRef.current) {
          setLoading(true);
          setError(null);
        }
        startTimeRef.current = Date.now();

        const result = await apiFunction(...args);

        // Prevent loading flicker for very fast responses
        const elapsed = Date.now() - startTimeRef.current;
        if (elapsed < minLoadingMs) {
          await new Promise((r) => setTimeout(r, minLoadingMs - elapsed));
        }

        // Only update state if still mounted
        if (mountedRef.current) {
          setData(result);
        }

        if (showSuccessToast) {
          toast.success(successMessage);
        }

        return result;
      } catch (err) {
        // err.status works for our custom fetch errors (thrown with Object.assign)
        // err.response?.status works for axios-style errors
        const status = err.status || err.response?.status;

        if (status === 401) {
          toast.error('Session expired. Please log in again.');
          window.location.href = '/login';
          return;
        }

        const errorMessage =
          err.response?.data?.message ||
          err.response?.data?.error ||
          err.message ||
          'An error occurred';

        if (mountedRef.current) {
          setError(errorMessage);
        }

        if (showErrorToast) {
          if (!navigator.onLine) {
            toast.error('No internet connection. Please check your network.');
          } else if (status >= 500) {
            toast.error('Server error. Please try again later.');
          } else {
            toast.error(errorMessage);
          }
        }

        throw err;
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    // apiFunction removed from deps — it's recreated on every render in Analytics.jsx
    // which would cause an infinite loop. Use a stable ref instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [showSuccessToast, successMessage, showErrorToast, minLoadingMs]
  );

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, execute, reset };
};

/**
 * Hook for fetching data on mount with refetch support.
 */
export const useFetch = (apiFunction, deps = [], options = {}) => {
  const { data, loading, error, execute, reset } = useApiCall(apiFunction, {
    showErrorToast: true,
    ...options,
  });

  useEffect(() => {
    execute();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps); // deps passed in from the caller (e.g. [] in Analytics)

  return { data, loading, error, refetch: execute, reset };
};

export default useApiCall;
