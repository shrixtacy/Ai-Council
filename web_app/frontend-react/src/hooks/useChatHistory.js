import { useState, useEffect, useCallback, useRef } from 'react';
import toast from 'react-hot-toast';
import { authAPI } from '../utils/api';

/**
 * Hook for fetching paginated chat history with delete support.
 *
 * @param {number} page  - Current page (1-indexed)
 * @param {number} limit - Items per page
 */
export const useChatHistory = (page = 1, limit = 20) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pagination, setPagination] = useState({
    totalPages: 0,
    currentPage: 1,
    total: 0,
  });

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const { data } = await authAPI.get(
        `/chat/history?page=${page}&limit=${limit}`
      );

      if (!mountedRef.current) return;

      setHistory(data.data || []);
      setPagination({
        totalPages: data.totalPages || 0,
        currentPage: Number(data.currentPage) || page,
        total: data.total || 0,
      });
    } catch (err) {
      if (!mountedRef.current) return;

      const message =
        err.response?.data?.message || err.message || 'Failed to fetch history';
      setError(message);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [page, limit]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const deleteConversation = useCallback(
    async (id) => {
      try {
        await authAPI.delete(`/chat/history/${id}`);
        toast.success('Conversation deleted');
        fetchHistory();
      } catch (err) {
        const message =
          err.response?.data?.message ||
          err.message ||
          'Failed to delete conversation';
        toast.error(message);
      }
    },
    [fetchHistory]
  );

  return { history, loading, error, pagination, deleteConversation, refetch: fetchHistory };
};

export default useChatHistory;
