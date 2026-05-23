import React, { useEffect, useState } from 'react';

export default function Market({ t, language }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setData(null);
    setError(false);
    fetch(`/api/market?lang=${language || 'en'}`)
      .then((res) => res.json())
      .then(setData)
      .catch(() => setError(true));
  }, [language]);

  if (error) {
    return (
      <div className="market-container">
        <div className="section-header">
          <h2 className="section-title">📊 {t.marketPanel}</h2>
        </div>
        <div className="error-state">
          <div className="error-emoji">📡</div>
          <p>Unable to load market data. Start the backend server.</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="market-container">
        <div className="section-header">
          <h2 className="section-title">📊 {t.marketPanel}</h2>
        </div>
        <div className="market-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass" style={{ padding: '0.9rem' }}>
              <div className="loading-skeleton" style={{ width: '60%' }}></div>
              <div className="loading-skeleton" style={{ width: '80%' }}></div>
              <div className="loading-skeleton" style={{ width: '40%' }}></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="market-container">
      <div className="section-header">
        <h2 className="section-title">📊 {t.marketPanel}</h2>
      </div>
      <div className="market-grid">
        {Object.entries(data).map(([crop, info]) => (
          <div key={crop} className="market-card glass">
            <div className="market-crop">{crop}</div>
            <div className="market-price">{info.currentRange}</div>
            {info.msp && <div className="market-msp">MSP: ₹{info.msp.toLocaleString()}</div>}
            <span className={`demand-badge demand-${info.demand?.toLowerCase() || 'medium'}`}>
              {info.demand}
            </span>
            {info.change && (
              <div className={`trend-indicator trend-${info.trend || 'stable'}`}>
                {info.trend === 'up' ? '▲' : info.trend === 'down' ? '▼' : '●'} {info.change}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
