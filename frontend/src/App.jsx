import React, { useState } from 'react';
import './index.css';
import Chat from './components/Chat';
import Scanner from './components/Scanner';
import Market from './components/Market';
import Schemes from './components/Schemes';
import AgentGrid from './components/AgentGrid';
import Weather from './components/Weather';
import { translations, locales } from './translations';

function App() {
  const [activeAgent, setActiveAgent] = useState(null);
  const [language, setLanguage] = useState('en');

  const t = translations[language];
  const locale = locales[language];

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-brand">
          <div className="header-logo">🌾</div>
          <div>
            <div className="header-title">{t.appTitle}</div>
            <div className="header-subtitle">{t.appSubtitle}</div>
          </div>
        </div>
        <div className="header-status" style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <div>
            <span className="status-dot"></span>
            <span>{t.systemOnline}</span>
          </div>
          <select 
            value={language} 
            onChange={(e) => setLanguage(e.target.value)}
            style={{ padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.1)', color: 'white', border: '1px solid rgba(255,255,255,0.3)', cursor: 'pointer' }}
          >
            <option value="en" style={{color: 'black'}}>{t.langEn}</option>
            <option value="hi" style={{color: 'black'}}>{t.langHi}</option>
            <option value="te" style={{color: 'black'}}>{t.langTe}</option>
            <option value="mr" style={{color: 'black'}}>{t.langMr}</option>
            <option value="bn" style={{color: 'black'}}>{t.langBn}</option>
            <option value="gu" style={{color: 'black'}}>{t.langGu}</option>
            <option value="kn" style={{color: 'black'}}>{t.langKn}</option>
            <option value="ml" style={{color: 'black'}}>{t.langMl}</option>
            <option value="or" style={{color: 'black'}}>{t.langOr}</option>
            <option value="pa" style={{color: 'black'}}>{t.langPa}</option>
            <option value="ta" style={{color: 'black'}}>{t.langTa}</option>
          </select>
        </div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {/* Agent Grid — full width top row */}
        <section className="agents-section">
          <AgentGrid activeAgent={activeAgent} onSelectAgent={setActiveAgent} t={t} language={language} />
        </section>

        {/* Chat — left column */}
        <section className="chat-section glass">
          <Chat activeAgent={activeAgent} t={t} language={language} locale={locale} />
        </section>

        {/* Right column panels */}
        <div className="sidebar-panels">
          <section className="glass">
            <Weather t={t} language={language} />
          </section>
          <section className="glass">
            <Market t={t} language={language} />
          </section>
          <section className="glass">
            <Schemes t={t} language={language} />
          </section>
          <section className="glass">
            <Scanner t={t} language={language} />
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <p>{t.footerText}</p>
      </footer>
    </div>
  );
}

export default App;
