import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';

const FALLBACK_AGENTS = [
  { id: 'crop_advisor', name: 'Crop Advisor', emoji: '🌾', description: 'Diseases, pests, remedies & cultivation' },
  { id: 'market_analyst', name: 'Market Analyst', emoji: '📊', description: 'MSP, mandi prices & demand trends' },
  { id: 'schemes_expert', name: 'Schemes Expert', emoji: '🏛️', description: 'Government schemes & subsidies' },
  { id: 'weather_analyst', name: 'Weather Analyst', emoji: '🌦️', description: 'Weather risks & seasonal planning' },
  { id: 'leaf_scanner', name: 'Leaf Scanner', emoji: '🔬', description: 'Plant disease identification' },
];

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
};

export default function AgentGrid({ t, language }) {
  const [agents, setAgents] = useState(FALLBACK_AGENTS);
  const navigate = useNavigate();

  useEffect(() => {
    fetch(`/api/agents?lang=${language || 'en'}`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setAgents(data);
        }
      })
      .catch(() => {
        // Use fallback
      });
  }, [language]);

  const getTranslatedName = (agentId, fallbackName) => {
    const key = 'agent' + agentId.split('_')[0].charAt(0).toUpperCase() + agentId.split('_')[0].slice(1);
    return t[key] || fallbackName;
  };

  const handleClick = (agentId) => {
    if (agentId === 'leaf_scanner') {
      navigate('/scanner');
    } else {
      navigate(`/chat/${agentId}`);
    }
  };

  return (
    <div className="page-container">
      <motion.div 
        className="hero-section"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <h1 className="page-title">{t.agentsAll || 'Select an AI Agent'}</h1>
        <p className="page-subtitle">Choose a specialized assistant to help you with your farming needs today.</p>
      </motion.div>

      <motion.div 
        className="agent-grid-full"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        {agents.map((agent) => (
          <motion.div
            key={agent.id}
            className="agent-card-large glass-panel"
            variants={itemVariants}
            whileHover={{ scale: 1.03, translateY: -5, boxShadow: "0 20px 40px rgba(0,0,0,0.4)" }}
            whileTap={{ scale: 0.98 }}
            onClick={() => handleClick(agent.id)}
            role="button"
            tabIndex={0}
          >
            <div className="agent-card-header">
              <div className="agent-emoji-large">{agent.emoji}</div>
              <div className="agent-status-indicator">
                <span className="status-dot pulsing"></span> Online
              </div>
            </div>
            <h3 className="agent-name-large">{getTranslatedName(agent.id, agent.name)}</h3>
            <p className="agent-desc-large">{agent.description}</p>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
