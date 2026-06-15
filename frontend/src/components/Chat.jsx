import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';

const SUGGESTIONS = [
  "What is the MSP of paddy?",
  "How to treat rice blast disease?",
  "Tell me about PM-KISAN scheme",
  "Weather advisory for Guntur",
  "Best storage practices for cotton",
];

function getSessionId() {
  let id = localStorage.getItem('agrimitra_session_id');
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem('agrimitra_session_id', id);
  }
  return id;
}

function Chat({ activeAgent, t, language, locale }) {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
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

    // Pre-create assistant message to append to
    setMessages((prev) => [...prev, { role: 'assistant', content: '', sources: [], agents_used: [] }]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: messageText, language: language, session_id: getSessionId() })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          // Keep the last partial line in the buffer
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            const trimmedLine = line.trim();
            if (!trimmedLine) continue;
            
            if (trimmedLine.startsWith('data: ')) {
              const dataStr = trimmedLine.replace('data: ', '').trim();
              if (dataStr === '[DONE]') {
                continue;
              }
              
              try {
                const data = JSON.parse(dataStr);
                
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  // Create a shallow copy of the last message to avoid mutating state directly, 
                  // which causes double-appending in React StrictMode
                  const lastMsg = { ...newMsgs[newMsgs.length - 1] };
                  
                  if (data.chunk) {
                    lastMsg.content += data.chunk;
                  }
                  
                  if (data.metadata) {
                    lastMsg.sources = data.metadata.sources || [];
                    lastMsg.agents_used = data.metadata.agents_used || [];
                  }
                  
                  newMsgs[newMsgs.length - 1] = lastMsg;
                  return newMsgs;
                });
                
              } catch (e) {
                console.error("Failed to parse SSE JSON:", dataStr, e);
              }
            }
          }
        }
      }
    } catch (e) {
      console.error(e);
      setMessages((prev) => {
        const newMsgs = [...prev];
        const lastMsg = newMsgs[newMsgs.length - 1];
        lastMsg.content = '⚠️ Unable to reach the AI backend. Make sure the FastAPI server is running on port 8000.\n\nStart it with: `uvicorn main:app --reload --port 8000`';
        return newMsgs;
      });
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

  const handleVoiceToggle = async () => {
    if (isListening) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
        setIsListening(false);
      }
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        
        if (audioChunksRef.current.length === 0) return;
        
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append("file", audioBlob, "voice_note.webm");

        try {
          setQuery(prev => prev + (prev ? ' ' : '') + "⏳ Transcribing...");
          
          const response = await fetch('/api/transcribe', {
            method: 'POST',
            body: formData,
          });
          
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          
          const data = await response.json();
          if (data.text) {
            setQuery(prev => prev.replace("⏳ Transcribing...", "").trim() + (prev.replace("⏳ Transcribing...", "").trim() ? ' ' : '') + data.text);
          } else {
            setQuery(prev => prev.replace("⏳ Transcribing...", "").trim());
          }
        } catch (error) {
          console.error("Transcription error:", error);
          setQuery(prev => prev.replace("⏳ Transcribing...", "").trim());
          alert("Failed to transcribe audio.");
        }
      };

      mediaRecorder.start();
      setIsListening(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
      alert("Microphone access denied or not available.");
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2 className="chat-title">💬 {t?.agentsAll || "Chat Assistant"}</h2>
        <span className="chat-badge">Multi-RAG (Live Data)</span>
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="welcome-emoji">🌾</div>
            <h3 className="welcome-title">Welcome to AgriMitra AI</h3>
            <p className="welcome-text">
              {t?.chatSelectAgent || "Ask me anything about crops, market prices, government schemes, weather, or plant diseases. I'll route your question to the right expert agents and search the web for live data if needed."}
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
            {msg.agents_used && msg.agents_used.length > 0 && (
              <div className="msg-agents">
                {msg.agents_used.map((agent, j) => (
                  <span key={j} className="msg-agent-badge">
                    {agent.emoji} {t && t[`agent${agent.id.split('_')[0].charAt(0).toUpperCase() + agent.id.split('_')[0].slice(1)}`] ? t[`agent${agent.id.split('_')[0].charAt(0).toUpperCase() + agent.id.split('_')[0].slice(1)}`] : agent.name}
                  </span>
                ))}
              </div>
            )}

            <div className="msg-content-md">
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>

            {msg.sources && msg.sources.length > 0 && (
              <div className="msg-sources">
                {msg.sources.map((src, j) => (
                  <span key={j} className="msg-source-chip">
                    {src === 'web' || src.includes('.') ? '🌐' : '📄'} {src}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (!messages.length || messages[messages.length-1].role !== 'assistant' || !messages[messages.length-1].content) && (
          <div className="typing-indicator">
            <div className="typing-dots">
              <span></span><span></span><span></span>
            </div>
            <span className="typing-text">{t?.chatConnecting || "Consulting agents & searching the web..."}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

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
            onClick={handleVoiceToggle}
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
