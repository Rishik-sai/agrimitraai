import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const SUGGESTIONS = [
  "What is the MSP of paddy?",
  "How to treat rice blast disease?",
  "Tell me about PM-KISAN scheme",
  "Weather advisory for Guntur",
  "Best storage practices for cotton",
];

function Chat({ activeAgent, t, language, locale }) {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const sendMessage = async (text) => {
    const messageText = text || query;
    if (!messageText.trim()) return;

    const userMsg = { role: 'user', content: messageText };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setQuery('');

    try {
      // Pass the language parameter to the backend
      const resp = await axios.post('/api/chat', { query: messageText, language: language });
      const botMsg = {
        role: 'assistant',
        content: resp.data.answer,
        sources: resp.data.sources || [],
        agents_used: resp.data.agents_used || [],
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (e) {
      const errMsg = {
        role: 'assistant',
        content: '⚠️ Unable to reach the AI backend. Make sure the FastAPI server is running on port 8000.\n\nStart it with: `uvicorn main:app --reload --port 8000`',
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const startListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Your browser does not support Speech Recognition.');
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = locale || 'en-IN';
    recognition.interimResults = false;
    
    recognition.onstart = () => setIsListening(true);
    
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setQuery(prev => (prev ? prev + ' ' : '') + transcript);
      setIsListening(false);
    };
    
    recognition.onerror = (event) => {
      console.error(event.error);
      setIsListening(false);
    };
    
    recognition.onend = () => setIsListening(false);
    
    recognition.start();
  };

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <h2 className="chat-title">💬 {t?.agentsAll || "Chat Assistant"}</h2>
        <span className="chat-badge">Multi-RAG</span>
      </div>

      {/* Messages */}
      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-emoji">🌾</div>
            <h3 className="welcome-title">Welcome to AgriMitra AI</h3>
            <p className="welcome-text">
              {t?.chatSelectAgent || "Ask me anything about crops, market prices, government schemes, weather, or plant diseases. I'll route your question to the right expert agents."}
            </p>
            <div className="welcome-suggestions">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  className="suggestion-chip"
                  onClick={() => sendMessage(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {/* Agent badges */}
            {msg.agents_used && msg.agents_used.length > 0 && (
              <div className="msg-agents">
                {msg.agents_used.map((agent, j) => (
                  <span key={j} className="msg-agent-badge">
                    {agent.emoji} {t && t[`agent${agent.id.split('_')[0].charAt(0).toUpperCase() + agent.id.split('_')[0].slice(1)}`] ? t[`agent${agent.id.split('_')[0].charAt(0).toUpperCase() + agent.id.split('_')[0].slice(1)}`] : agent.name}
                  </span>
                ))}
              </div>
            )}

            {/* Content */}
            <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

            {/* Sources */}
            {msg.sources && msg.sources.length > 0 && (
              <div className="msg-sources">
                {msg.sources.map((src, j) => (
                  <span key={j} className="msg-source-chip">📄 {src}</span>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Typing indicator */}
        {loading && (
          <div className="typing-indicator">
            <div className="typing-dots">
              <span></span><span></span><span></span>
            </div>
            <span className="typing-text">{t?.chatConnecting || "Consulting agents..."}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area" style={{ position: 'relative' }}>
        <textarea
          className="chat-input"
          rows={2}
          placeholder={isListening ? (t?.listening || "Listening...") : (t?.chatPlaceholder || "Ask about crops, prices, schemes, weather...")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKey}
          disabled={loading}
          style={{ paddingRight: '90px' }}
        />
        <div style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: '8px' }}>
          <button
            className="send-btn"
            onClick={startListening}
            disabled={loading}
            title={t?.speakBtn || "Speak"}
            style={{ background: isListening ? '#ef4444' : 'var(--glass-border)' }}
          >
            🎤
          </button>
          <button
            className="send-btn"
            onClick={() => sendMessage()}
            disabled={loading || !query.trim()}
            title={t?.sendBtn || "Send message"}
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  );
}

export default Chat;
