import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { BarChart2, TrendingUp, TrendingDown, Minus } from 'lucide-react';

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

  const containerVariants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
  };

  if (error) {
    return (
      <motion.div className="page-container" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <div className="page-header">
          <h1 className="page-title"><BarChart2 className="inline-icon" /> {t.marketPanel || 'Market Prices'}</h1>
        </div>
        <div className="error-state glass-panel" style={{ padding: '40px', textAlign: 'center' }}>
          <div className="error-emoji" style={{ fontSize: '3rem' }}>📡</div>
          <p>Unable to load market data. Start the backend server.</p>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div 
      className="page-container"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
    >
      <div className="page-header">
        <h1 className="page-title"><BarChart2 className="inline-icon" /> {t.marketPanel || 'Market Prices'}</h1>
        <p className="page-subtitle">Real-time mandi prices, MSP, and demand trends for your crops.</p>
      </div>

      {!data ? (
        <div className="agent-grid-full">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass-panel" style={{ padding: '30px', height: '200px' }}>
              <div className="skeleton-line" style={{ width: '60%', height: '24px', marginBottom: '20px' }}></div>
              <div className="skeleton-line" style={{ width: '80%' }}></div>
              <div className="skeleton-line" style={{ width: '40%' }}></div>
            </div>
          ))}
        </div>
      ) : (
        <motion.div 
          className="agent-grid-full"
          variants={containerVariants}
          initial="hidden"
          animate="show"
        >
          {(Array.isArray(data) ? data : Object.entries(data).map(([crop, info]) => ({ crop, ...info }))).map((info, idx) => (
            <motion.div key={idx} variants={itemVariants} className="glass-panel" style={{ padding: '30px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                <h3 style={{ fontSize: '1.5rem', margin: 0 }}>{info.crop}</h3>
                <span className={`demand-badge demand-${info.demand?.toLowerCase() || 'medium'}`} style={{ padding: '6px 12px', borderRadius: '20px', fontSize: '0.85rem', fontWeight: 'bold' }}>
                  {info.demand} Demand
                </span>
              </div>
              
              <div style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '10px', color: 'var(--accent-primary)' }}>
                {info.currentRange}
              </div>
              
              {info.msp && (
                <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '20px' }}>
                  MSP: ₹{info.msp.toLocaleString()} / quintal
                </div>
              )}
              
              {info.change && (
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  padding: '10px',
                  background: 'rgba(255,255,255,0.05)',
                  borderRadius: '8px',
                  color: info.trend === 'up' ? '#10b981' : info.trend === 'down' ? '#ef4444' : '#f59e0b'
                }}>
                  {info.trend === 'up' ? <TrendingUp size={20} /> : info.trend === 'down' ? <TrendingDown size={20} /> : <Minus size={20} />}
                  <span style={{ fontWeight: '600' }}>{info.change}</span>
                </div>
              )}
            </motion.div>
          ))}
        </motion.div>
      )}
    </motion.div>
  );
}
