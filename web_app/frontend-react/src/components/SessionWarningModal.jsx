import React from 'react';
import { Clock, RefreshCw } from 'lucide-react';
import { useTokenManager } from '../hooks/useTokenManager';

const formatTime = (ms) => {
  if (ms == null || ms <= 0) return '0:00';
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

export const SessionWarningModal = () => {
  const { showWarning, timeUntilExpiry, refreshToken } = useTokenManager();

  if (!showWarning) return null;

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 bg-black bg-opacity-50">
      <div className="bg-gray-800 text-gray-100 rounded-lg p-6 max-w-sm w-full mx-4 shadow-xl">
        <div className="flex items-center gap-3 mb-3">
          <Clock className="text-yellow-400 shrink-0" size={24} />
          <h2 className="text-lg font-semibold">Session Expiring Soon</h2>
        </div>
        <p className="text-sm text-gray-300 mb-1">
          Your session will expire in{' '}
          <span className="font-mono text-yellow-400">{formatTime(timeUntilExpiry)}</span>.
        </p>
        <p className="text-sm text-gray-400 mb-5">Would you like to extend your session?</p>
        <button
          onClick={refreshToken}
          className="flex items-center gap-2 w-full justify-center bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
        >
          <RefreshCw size={16} />
          Extend Session
        </button>
      </div>
    </div>
  );
};

export default SessionWarningModal;
