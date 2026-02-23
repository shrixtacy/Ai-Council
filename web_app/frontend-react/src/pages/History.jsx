import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, MessageSquare } from 'lucide-react';

const History = () => {
  const navigate = useNavigate();

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
          <h1 className="text-2xl font-bold text-gray-800">Chat History</h1>
        </div>

        {/* Empty State */}
        <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
          <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-gray-800 mb-2">No Conversations Yet</h3>
          <p className="text-gray-600 mb-6">
            Your chat history will appear here once you start conversations.
          </p>
          <button
            onClick={() => navigate('/chat')}
            className="px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-lg font-semibold hover:from-primary-700 hover:to-primary-800 transition-all"
          >
            Start Chatting
          </button>
        </div>
      </div>
    </div>
  );
};

export default History;
