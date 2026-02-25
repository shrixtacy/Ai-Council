import React, { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Send, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import OrchestrationVisualizer from '../components/OrchestrationVisualizer';
import { aiAPI, authAPI } from '../utils/api';

const MODES = [
  { value: 'fast', label: 'Fast' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'best_quality', label: 'Best Quality' },
];

const Chat = () => {
  const navigate = useNavigate();
  const latestRequestIdRef = useRef(0);
  const messagesEndRef = useRef(null);

  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('balanced');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [orchestrationData, setOrchestrationData] = useState(null);

  const buildSubtasks = (responseData) => {
    const steps = Array.isArray(responseData.execution_path)
      ? responseData.execution_path
      : [];

    return steps.map((step, idx) => ({
      id: `${Date.now()}-${idx}`,
      content: typeof step === 'string' ? step : JSON.stringify(step),
      taskType: 'orchestration_step',
      assignedModel: responseData.models_used?.[0] || 'AI Council',
      status: 'completed',
      confidence: responseData.confidence || 0,
      startTime: new Date(),
      endTime: new Date(),
    }));
  };

  const persistChatHistory = async (requestQuery, data) => {
    try {
      await authAPI.post('/chat/save', {
        query: requestQuery,
        response: data.content,
        executionMode: mode,
        modelsUsed: data.models_used || [],
        confidence: data.confidence || 0,
        cost: data.cost || 0,
        executionTime: data.execution_time || 0,
        orchestrationData: {
          executionPath: data.execution_path || [],
          arbitrationDecisions: data.arbitration_decisions || [],
          synthesisNotes: data.synthesis_notes || [],
        },
      });
    } catch (err) {
      // Non-blocking for UX; user still gets AI response even if history persistence fails.
      console.warn('Failed to persist chat history', {
        requestQuery,
        error: String(err?.message || err),
      });
    }
  };

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;

    const requestQuery = query;
    const userMessage = { role: 'user', content: requestQuery, mode };

    setMessages((prev) => [...prev, userMessage]);
    setQuery('');
    setLoading(true);

    try {
      const { data } = await aiAPI.post('/process', {
        query: requestQuery,
        mode,
      });

      // Race guard: ignore stale responses from earlier requests.
      if (requestId !== latestRequestIdRef.current) return;

      if (!data?.success) {
        throw new Error(data?.error_message || 'AI request failed');
      }

      setOrchestrationData({
        subtasks: buildSubtasks(data),
        arbitrationDecisions: data.arbitration_decisions || [],
        synthesisNotes: data.synthesis_notes || [],
      });

      const aiMessage = {
        role: 'assistant',
        content: data.content,
        metadata: {
          confidence: data.confidence,
          modelsUsed: data.models_used || [],
          executionTime: data.execution_time || 0,
          cost: data.cost || 0,
        },
      };

      setMessages((prev) => [...prev, aiMessage]);
      persistChatHistory(requestQuery, data);
    } catch (error) {
      if (requestId !== latestRequestIdRef.current) return;
      const message =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        'Failed to process request. Please try again.';

      toast.error(message);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, something went wrong while processing your request.',
          isError: true,
        },
      ]);
    } finally {
      if (requestId === latestRequestIdRef.current) {
        setLoading(false);
      }
    }
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-2xl shadow-lg p-4 mb-6 flex items-center gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          <h1 className="text-2xl font-bold font-display tracking-tight text-gray-800">AI Chat</h1>
        </div>

        <OrchestrationVisualizer orchestrationData={orchestrationData} isProcessing={loading} />

        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6 min-h-[400px] max-h-[500px] overflow-y-auto">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 mt-20">
              <p className="text-lg font-display tracking-tight">Start a conversation with AI Council</p>
              <p className="text-sm mt-2">Ask anything and watch the orchestration in action!</p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[75%] p-4 rounded-2xl ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-r from-primary-600 to-primary-700 text-white'
                        : msg.isError
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    <div>{msg.content}</div>
                    {msg.role === 'assistant' && msg.metadata && (
                      <div className="mt-2 text-xs opacity-70">
                        {msg.metadata.modelsUsed?.join(', ') || 'AI Council'} • {msg.metadata.executionTime?.toFixed?.(2) || msg.metadata.executionTime}s • ${Number(msg.metadata.cost || 0).toFixed(4)}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 p-4 rounded-2xl">
                    <div className="flex gap-2">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-4 space-y-3">
          <div className="flex gap-2 flex-wrap">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => setMode(m.value)}
                disabled={loading}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  mode === m.value
                    ? 'bg-primary-600 text-white border-primary-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                } disabled:opacity-50`}
              >
                {m.label}
              </button>
            ))}
          </div>

          <div className="flex gap-4">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask AI Council anything..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-6 py-3 font-display bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-lg font-semibold hover:from-primary-700 hover:to-primary-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Send className="w-5 h-5" />
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Chat;
