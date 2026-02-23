// components/ErrorMessage.jsx
import { AlertCircle, RefreshCw, WifiOff, Lock, ServerCrash, FileQuestion } from 'lucide-react';

const ERROR_CONFIGS = {
  401: {
    icon: Lock,
    title: 'Authentication Required',
    message: 'You need to be logged in to access this resource.',
    actionLabel: 'Log In',
    action: () => (window.location.href = '/login'),
  },
  403: {
    icon: Lock,
    title: 'Access Denied',
    message: "You don't have permission to view this content.",
  },
  404: {
    icon: FileQuestion,
    title: 'Not Found',
    message: 'The resource you requested could not be found.',
  },
  500: {
    icon: ServerCrash,
    title: 'Server Error',
    message: 'Something went wrong on our end. Please try again later.',
  },
  network: {
    icon: WifiOff,
    title: 'Connection Error',
    message: 'Unable to connect. Please check your internet connection.',
  },
};

export const ErrorMessage = ({ error, statusCode, onRetry, className = '' }) => {
  const config = ERROR_CONFIGS[statusCode] ||
    ERROR_CONFIGS[error?.status] || {
      icon: AlertCircle,
      title: 'Error',
      message: typeof error === 'string' ? error : error?.message || 'An unexpected error occurred.',
    };

  const Icon = config.icon;

  return (
    <div className={`bg-red-50 border border-red-200 rounded-lg p-5 ${className}`}>
      <div className="flex items-start gap-4">
        <div className="flex-shrink-0 mt-0.5">
          <Icon className="w-6 h-6 text-red-500" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-red-800 text-sm mb-0.5">{config.title}</h3>
          <p className="text-red-700 text-sm">
            {typeof error === 'string' ? error : error?.message || config.message}
          </p>
          <div className="flex flex-wrap gap-3 mt-3">
            {onRetry && (
              <button
                onClick={onRetry}
                className="flex items-center gap-1.5 text-sm font-medium text-red-600 hover:text-red-800 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>
            )}
            {config.action && (
              <button
                onClick={config.action}
                className="flex items-center gap-1.5 text-sm font-medium text-red-600 hover:text-red-800 transition-colors"
              >
                {config.actionLabel}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export const InlineError = ({ message }) =>
  message ? (
    <p className="flex items-center gap-1.5 text-red-600 text-sm mt-1">
      <AlertCircle className="w-4 h-4 flex-shrink-0" />
      {message}
    </p>
  ) : null;

export default ErrorMessage;
