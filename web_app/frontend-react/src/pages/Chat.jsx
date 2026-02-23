import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Send, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import OrchestrationVisualizer from '../components/OrchestrationVisualizer';

const Chat = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [orchestrationData, setOrchestrationData] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userMessage = { role: 'user', content: query };
    setMessages([...messages, userMessage]);
    setQuery('');
    setLoading(true);

    // Simulate orchestration data (replace with actual API call)
    setTimeout(() => {
      const mockOrchestration = {
        subtasks: [
          {
            id: '1',
            content: 'Analyze user intent',
            taskType: 'reasoning',
            assignedModel: 'gpt-4',
            status: 'completed',
            confidence: 0.95,
            startTime: new Date(),
            endTime: new Date(Date.now() + 1000)
          },
          {
            id: '2',
            content: 'Generate response',
            taskType: 'creative_output',
            assignedModel: 'claude-3',
            status: 'completed',
            confidence: 0.92,
            startTime: new Date(),
            endTime: new Date(Date.now() + 2000)
          }
        ],
        arbitrationDecisions: ['Selected GPT-4 for reasoning based on confidence score'],
        synthesisNotes: ['Combined outputs from multiple models for comprehensive response']
      };

      setOrchestrationData(mockOrchestration);
      
      const aiMessage = {
        role: 'assistant',
        content: 'This is a demo response. Connect to the AI backend to get real responses with live orchestration!'
      };
      
      setMessages(prev => [...prev, aiMessage]);
      setLoading(false);
    }, 2000);
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
          <h1 className="text-2xl font-bold font-display tracking-tight text-gray-800">AI Chat</h1>
        </div>

        {/* Orchestration Visualizer */}
        <OrchestrationVisualizer 
          orchestrationData={orchestrationData}
          isProcessing={loading}
        />

        {/* Chat Messages */}
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
                    className={`max-w-[70%] p-4 rounded-2xl ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-r from-primary-600 to-primary-700 text-white'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {msg.content}
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
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-lg p-4">
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
