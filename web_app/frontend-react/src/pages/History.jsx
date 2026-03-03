import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  MessageSquare,
  Search,
  Trash2,
  Download,
  Clock,
  Zap,
  DollarSign,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  X,
  Filter,
} from 'lucide-react';
import { SkeletonCard } from '../components/SkeletonCard';
import { ErrorMessage } from '../components/Errormessage';
import { useChatHistory } from '../hooks/useChatHistory';

// ─── Helpers ────────────────────────────────────────────────────────────────

const MODE_OPTIONS = [
  { value: '', label: 'All Modes' },
  { value: 'fast', label: 'Fast' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'best_quality', label: 'Best Quality' },
];

const MODE_COLORS = {
  fast: 'bg-yellow-100 text-yellow-800',
  balanced: 'bg-blue-100 text-blue-800',
  best_quality: 'bg-green-100 text-green-800',
};

function formatRelativeTime(dateString) {
  const now = new Date();
  const date = new Date(dateString);
  const seconds = Math.floor((now - date) / 1000);

  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

function truncate(text, maxLen = 120) {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
}

function exportAsJson(conversation) {
  const blob = new Blob([JSON.stringify(conversation, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `conversation-${conversation._id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Sub-components ─────────────────────────────────────────────────────────

const SearchBar = ({ value, onChange }) => (
  <div className="relative">
    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Search conversations…"
      className="w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all text-sm"
    />
    {value && (
      <button
        onClick={() => onChange('')}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
      >
        <X className="w-4 h-4" />
      </button>
    )}
  </div>
);

const ModeFilter = ({ activeMode, onSelect }) => (
  <div className="flex gap-2 flex-wrap">
    <Filter className="w-5 h-5 text-gray-400 self-center" />
    {MODE_OPTIONS.map((opt) => (
      <button
        key={opt.value}
        onClick={() => onSelect(opt.value)}
        className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
          activeMode === opt.value
            ? 'bg-primary-600 text-white border-primary-600'
            : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
        }`}
      >
        {opt.label}
      </button>
    ))}
  </div>
);

const ConversationCard = ({ conversation, onDelete, onExport }) => {
  const navigate = useNavigate();
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      layout
      className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow border border-gray-100 overflow-hidden"
    >
      <div className="flex items-start gap-4 p-5">
        {/* Main content — clickable */}
        <div
          className="flex-1 min-w-0 cursor-pointer"
          onClick={() => navigate(`/history/${conversation._id}`)}
        >
          <h3 className="font-semibold text-gray-800 mb-1 truncate">
            {conversation.query}
          </h3>
          <p className="text-gray-500 text-sm leading-relaxed mb-3">
            {truncate(conversation.response)}
          </p>

          {/* Metadata chips */}
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {formatRelativeTime(conversation.timestamp)}
            </span>
            {conversation.executionMode && (
              <span
                className={`px-2 py-0.5 rounded-full font-medium ${
                  MODE_COLORS[conversation.executionMode] || 'bg-gray-100 text-gray-700'
                }`}
              >
                <Zap className="w-3 h-3 inline mr-0.5 -mt-0.5" />
                {conversation.executionMode}
              </span>
            )}
            {conversation.cost != null && (
              <span className="flex items-center gap-1">
                <DollarSign className="w-3.5 h-3.5" />
                ${Number(conversation.cost).toFixed(4)}
              </span>
            )}
            {conversation.confidence != null && (
              <span className="flex items-center gap-1">
                <BarChart3 className="w-3.5 h-3.5" />
                {(conversation.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-2 flex-shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onExport(conversation);
            }}
            title="Export as JSON"
            className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
          >
            <Download className="w-4 h-4" />
          </button>

          {confirmDelete ? (
            <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => {
                  onDelete(conversation._id);
                  setConfirmDelete(false);
                }}
                className="px-2 py-1 text-xs bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
              >
                Yes
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-2 py-1 text-xs bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
              >
                No
              </button>
            </div>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setConfirmDelete(true);
              }}
              title="Delete conversation"
              className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
};

const Pagination = ({ currentPage, totalPages, total, onPageChange }) => {
  if (totalPages <= 1) return null;

  const pages = [];
  const maxVisible = 5;
  let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
  let end = Math.min(totalPages, start + maxVisible - 1);
  if (end - start + 1 < maxVisible) {
    start = Math.max(1, end - maxVisible + 1);
  }
  for (let i = start; i <= end; i++) pages.push(i);

  return (
    <div className="flex items-center justify-between mt-6">
      <p className="text-sm text-gray-500">
        {total} conversation{total !== 1 ? 's' : ''}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className="p-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        {pages.map((p) => (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${
              p === currentPage
                ? 'bg-primary-600 text-white'
                : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
            }`}
          >
            {p}
          </button>
        ))}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="p-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

// ─── Main Page ──────────────────────────────────────────────────────────────

const History = () => {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [modeFilter, setModeFilter] = useState('');

  const { history, loading, error, pagination, deleteConversation, refetch } =
    useChatHistory(page);

  // Client-side filtering (search + mode)
  const filteredHistory = useMemo(() => {
    let result = history;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.query?.toLowerCase().includes(q) ||
          c.response?.toLowerCase().includes(q)
      );
    }
    if (modeFilter) {
      result = result.filter((c) => c.executionMode === modeFilter);
    }
    return result;
  }, [history, searchQuery, modeFilter]);

  const handlePageChange = (newPage) => {
    setPage(newPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-lg p-4 mb-6 flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-2xl font-bold font-display tracking-tight text-gray-800">
            Chat History
          </h1>
          {!loading && pagination.total > 0 && (
            <span className="ml-auto text-sm text-gray-500">
              {pagination.total} total
            </span>
          )}
        </div>

        {/* Toolbar: Search + Filters */}
        <div className="bg-white rounded-2xl shadow-lg p-4 mb-6 space-y-3">
          <SearchBar value={searchQuery} onChange={setSearchQuery} />
          <ModeFilter activeMode={modeFilter} onSelect={setModeFilter} />
        </div>

        {/* Error state */}
        {error && (
          <div className="mb-6">
            <ErrorMessage error={error} onRetry={refetch} />
          </div>
        )}

        {/* Loading skeleton */}
        {loading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : filteredHistory.length > 0 ? (
          <>
            {/* Conversation list */}
            <div className="space-y-4">
              <AnimatePresence mode="popLayout">
                {filteredHistory.map((conv) => (
                  <ConversationCard
                    key={conv._id}
                    conversation={conv}
                    onDelete={deleteConversation}
                    onExport={exportAsJson}
                  />
                ))}
              </AnimatePresence>
            </div>

            {/* Pagination */}
            <Pagination
              currentPage={pagination.currentPage}
              totalPages={pagination.totalPages}
              total={pagination.total}
              onPageChange={handlePageChange}
            />
          </>
        ) : (
          /* Empty state */
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-2xl shadow-lg p-12 text-center"
          >
            <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-gray-800 mb-2">
              {searchQuery || modeFilter
                ? 'No Matching Conversations'
                : 'No Conversations Yet'}
            </h3>
            <p className="text-gray-600 mb-6">
              {searchQuery || modeFilter
                ? 'Try adjusting your search or filters.'
                : 'Your chat history will appear here once you start conversations.'}
            </p>
            {!searchQuery && !modeFilter && (
              <button
                onClick={() => navigate('/chat')}
                className="px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-lg font-semibold hover:from-primary-700 hover:to-primary-800 transition-all"
              >
                Start Chatting
              </button>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default History;
