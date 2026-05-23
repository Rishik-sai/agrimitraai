import React, { useEffect, useState } from 'react';

// Fallback agent data in case the API isn't running
const FALLBACK_AGENTS = [
  { id: 'crop_advisor', name: 'Crop Advisor', emoji: '🌾', description: 'Diseases, pests, remedies & cultivation' },
  { id: 'market_analyst', name: 'Market Analyst', emoji: '📊', description: 'MSP, mandi prices & demand trends' },
  { id: 'schemes_expert', name: 'Schemes Expert', emoji: '🏛️', description: 'Government schemes & subsidies' },
  { id: 'weather_analyst', name: 'Weather Analyst', emoji: '🌦️', description: 'Weather risks & seasonal planning' },
  { id: 'leaf_scanner', name: 'Leaf Scanner', emoji: '🔬', description: 'Plant disease identification' },
];

export default function AgentGrid({ activeAgent, onSelectAgent, t, language }) {
  const [agents, setAgents] = useState(FALLBACK_AGENTS);

  useEffect(() => {
    fetch(`/api/agents?lang=${language || 'en'}`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setAgents(data);
        }
      })
      .catch(() => {
        // Use fallback data
      });
  }, [language]);

  const handleClick = (agentId) => {
    if (activeAgent === agentId) {
      onSelectAgent(null); // Deselect
    } else {
      onSelectAgent(agentId);
    }
  };

  const getTranslatedName = (agentId, fallbackName) => {
    const key = 'agent' + agentId.split('_')[0].charAt(0).toUpperCase() + agentId.split('_')[0].slice(1);
    return t[key] || fallbackName;
  };

  return (
    <div className="agent-grid-section glass">
      <h2 className="agent-grid-title">🤖 {t.agentsAll}</h2>
      <div className="agent-grid">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className={`agent-card glass ${activeAgent === agent.id ? 'active' : ''}`}
            onClick={() => handleClick(agent.id)}
            role="button"
            tabIndex={0}
            id={`agent-${agent.id}`}
          >
            <div className="agent-emoji">{agent.emoji}</div>
            <div className="agent-name">{getTranslatedName(agent.id, agent.name)}</div>
            <div className="agent-desc">{agent.description}</div>
            <div className="agent-status">
              <span className="agent-status-dot"></span>
              Online
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
