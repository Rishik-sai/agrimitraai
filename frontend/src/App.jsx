import React, { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';

import Layout from './components/Layout';
import AgentGrid from './components/AgentGrid';
import Chat from './components/Chat';
import Scanner from './components/Scanner';
import Market from './components/Market';
import Schemes from './components/Schemes';
import Weather from './components/Weather';

import { translations, locales } from './translations';
import './index.css';

function App() {
  const [language, setLanguage] = useState('en');

  const t = translations[language];
  const locale = locales[language];

  return (
    <Routes>
      <Route path="/" element={<Layout t={t} language={language} setLanguage={setLanguage} />}>
        <Route index element={<AgentGrid t={t} language={language} />} />
        <Route path="chat/:agentId" element={<Chat t={t} language={language} locale={locale} />} />
        <Route path="chat" element={<Chat t={t} language={language} locale={locale} />} />
        <Route path="scanner" element={<Scanner t={t} language={language} />} />
        <Route path="market" element={<Market t={t} language={language} />} />
        <Route path="weather" element={<Weather t={t} language={language} />} />
        <Route path="schemes" element={<Schemes t={t} language={language} />} />
      </Route>
    </Routes>
  );
}

export default App;
