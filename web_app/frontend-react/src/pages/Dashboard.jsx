import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Brain, MessageSquare, BarChart3, History, LogOut } from 'lucide-react';
import useAuthStore from '../store/authStore';
import toast from 'react-hot-toast';

const Dashboard = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    toast.success('Logged out successfully');
    navigate('/login');
  };

  const cards = [
    {
      title: 'AI Chat',
      description: 'Start a conversation with AI Council',
      icon: MessageSquare,
      color: 'from-blue-500 to-blue-600',
      path: '/chat'
    },
    {
      title: 'Analytics',
      description: 'View your usage statistics',
      icon: BarChart3,
      color: 'from-green-500 to-green-600',
      path: '/analytics'
    },
    {
      title: 'History',
      description: 'Browse past conversations',
      icon: History,
      color: 'from-purple-500 to-purple-600',
      path: '/history'
    }
  ];

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-r from-primary-600 to-primary-700 rounded-full flex items-center justify-center">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold font-display tracking-tight text-gray-800">Welcome back, {user?.name}!</h1>
                <p className="text-gray-600">{user?.email}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="flex font-display items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <LogOut className="w-5 h-5" />
              Logout
            </button>
          </div>
        </div>

        {/* Cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {cards.map((card, index) => (
            <motion.div
              key={card.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              onClick={() => navigate(card.path)}
              className="bg-white rounded-2xl shadow-lg p-6 cursor-pointer hover:shadow-xl transition-shadow"
            >
              <div className={`w-12 h-12 bg-gradient-to-r ${card.color} rounded-lg flex items-center justify-center mb-4`}>
                <card.icon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-xl font-bold font-display tracking-tight text-gray-800 mb-2">{card.title}</h3>
              <p className="text-gray-600">{card.description}</p>
            </motion.div>
          ))}
        </div>

        {/* Info */}
        <div className="mt-6 bg-gradient-to-r from-primary-50 to-purple-50 rounded-2xl p-6">
          <h3 className="text-lg font-bold font-display tracking-tight text-gray-800 mb-2">🚀 AI Council Orchestrator</h3>
          <p className="text-gray-700">
            Experience intelligent multi-agent AI orchestration with real-time task decomposition,
            cost optimization, and live visualization of how AI models work together to solve complex problems.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
