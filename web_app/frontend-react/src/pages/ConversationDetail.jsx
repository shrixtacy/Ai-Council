import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import {
  ArrowLeft,
  Clock,
  Zap,
  DollarSign,
  BarChart3,
  Download,
  Trash2,
  Brain,
  Timer,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { authAPI } from '../utils/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/Errormessage';
import OrchestrationVisualizer from '../components/OrchestrationVisualizer';

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
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

const MODE_LABELS = {
  fast: { label: 'Fast', color: 'bg-yellow-100 text-yellow-800' },
  balanced: { label: 'Balanced', color: 'bg-blue-100 text-blue-800' },
  best_quality: { label: 'Best Quality', color: 'bg-green-100 text-green-800' },
};

// ─── Page ───────────────────────────────────────────────────────────────────

const ConversationDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [conversation, setConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchConversation = async () => {
      try {
        setLoading(true);
        setError(null);
        const { data } = await authAPI.get(`/chat/history/${id}`);
        if (!cancelled) setConversation(data.data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err.response?.data?.message ||
              err.message ||
              'Failed to load conversation'
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchConversation();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const handleDelete = async () => {
    try {
      await authAPI.delete(`/chat/history/${id}`);
      toast.success('Conversation deleted');
      navigate('/history');
    } catch (err) {
      toast.error(
        err.response?.data?.message || 'Failed to delete conversation'
      );
    }
  };

  const modeInfo = conversation?.executionMode
    ? MODE_LABELS[conversation.executionMode] || {
        label: conversation.executionMode,
        color: 'bg-gray-100 text-gray-700',
      }
    : null;

  // Build orchestrationData shape expected by OrchestrationVisualizer
  const orchestrationData =
    conversation?.orchestrationData &&
    (conversation.orchestrationData.executionPath?.length > 0 ||
      conversation.orchestrationData.arbitrationDecisions?.length > 0 ||
      conversation.orchestrationData.synthesisNotes?.length > 0)
      ? {
          subtasks: (conversation.orchestrationData.executionPath || []).map(
            (step, idx) => ({
              id: `${id}-${idx}`,
              content: typeof step === 'string' ? step : JSON.stringify(step),
              taskType: 'orchestration_step',
              assignedModel:
                conversation.modelsUsed?.[0] || 'AI Council',
              status: 'completed',
              confidence: conversation.confidence || 0,
              startTime: conversation.timestamp,
              endTime: conversation.timestamp,
            })
          ),
          arbitrationDecisions:
            conversation.orchestrationData.arbitrationDecisions || [],
          synthesisNotes:
            conversation.orchestrationData.synthesisNotes || [],
        }
      : null;

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-lg p-4 mb-6 flex items-center gap-4">
          <button
            onClick={() => navigate('/history')}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-2xl font-bold font-display tracking-tight text-gray-800">
            Conversation Detail
          </h1>
        </div>

        {/* Loading */}
        {loading && (
          <div className="bg-white rounded-2xl shadow-lg p-12">
            <LoadingSpinner size="lg" text="Loading conversation…" />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6">
            <ErrorMessage
              error={error}
              onRetry={() => window.location.reload()}
            />
          </div>
        )}

        {/* Content */}
        {!loading && !error && conversation && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            {/* Query card */}
            <div className="bg-white rounded-2xl shadow-lg p-6">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div className="flex-1">
                  <p className="text-xs uppercase font-semibold text-gray-400 mb-1">
                    Your Query
                  </p>
                  <h2 className="text-xl font-bold text-gray-800">
                    {conversation.query}
                  </h2>
                </div>

                {/* Actions */}
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => exportAsJson(conversation)}
                    title="Export as JSON"
                    className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                  >
                    <Download className="w-5 h-5" />
                  </button>

                  {confirmDelete ? (
                    <div className="flex gap-1 items-center">
                      <button
                        onClick={handleDelete}
                        className="px-3 py-1.5 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setConfirmDelete(false)}
                        className="px-3 py-1.5 text-xs bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmDelete(true)}
                      title="Delete conversation"
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Metadata grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-100">
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Clock className="w-4 h-4 text-gray-400" />
                  <span>{formatDate(conversation.timestamp)}</span>
                </div>
                {modeInfo && (
                  <div className="flex items-center gap-2 text-sm">
                    <Zap className="w-4 h-4 text-gray-400" />
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${modeInfo.color}`}
                    >
                      {modeInfo.label}
                    </span>
                  </div>
                )}
                {conversation.confidence != null && (
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <BarChart3 className="w-4 h-4 text-gray-400" />
                    <span>
                      {(conversation.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                )}
                {conversation.cost != null && (
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <DollarSign className="w-4 h-4 text-gray-400" />
                    <span>${Number(conversation.cost).toFixed(4)}</span>
                  </div>
                )}
                {conversation.executionTime != null && (
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Timer className="w-4 h-4 text-gray-400" />
                    <span>{Number(conversation.executionTime).toFixed(2)}s</span>
                  </div>
                )}
                {conversation.modelsUsed?.length > 0 && (
                  <div className="flex items-center gap-2 text-sm text-gray-600 col-span-2 sm:col-span-3">
                    <Brain className="w-4 h-4 text-gray-400" />
                    <span>{conversation.modelsUsed.join(', ')}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Response card */}
            <div className="bg-white rounded-2xl shadow-lg p-6">
              <p className="text-xs uppercase font-semibold text-gray-400 mb-3">
                AI Response
              </p>
              <div className="prose prose-gray max-w-none text-gray-700">
                <ReactMarkdown>{conversation.response || ''}</ReactMarkdown>
              </div>
            </div>

            {/* Orchestration Visualizer */}
            {orchestrationData && (
              <OrchestrationVisualizer
                orchestrationData={orchestrationData}
                isProcessing={false}
              />
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default ConversationDetail;
