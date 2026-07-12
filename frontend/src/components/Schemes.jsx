import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, ExternalLink, IndianRupee } from 'lucide-react';

export default function Schemes({ t, language }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setData(null);
    setError(false);
    fetch(`/api/schemes?lang=${language || 'en'}`)
      .then((res) => res.json())
      .then(setData)
      .catch(() => setError(true));
  }, [language]);

  const containerVariants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };

  const itemVariants = {
    hidden: { opacity: 0, scale: 0.95 },
    show: { opacity: 1, scale: 1 }
  };

  if (error) {
    return (
      <motion.div className="page-container" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <div className="page-header">
          <h1 className="page-title"><BookOpen className="inline-icon" /> {t.schemesPanel || 'Govt Schemes'}</h1>
        </div>
        <div className="error-state glass-panel" style={{ padding: '40px', textAlign: 'center' }}>
          <div className="error-emoji" style={{ fontSize: '3rem' }}>🏛️</div>
          <p>{t?.schemesError || 'Unable to load schemes. Start the backend server.'}</p>
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
        <h1 className="page-title"><BookOpen className="inline-icon" /> {t.schemesPanel || 'Govt Schemes'}</h1>
        <p className="page-subtitle">{t?.schemesSubtitle || 'Discover subsidies, financial support, and welfare programs for farmers.'}</p>
      </div>

      {!data ? (
        <div className="agent-grid-full">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-panel" style={{ padding: '30px', height: '250px' }}>
              <div className="skeleton-line" style={{ width: '80%', height: '24px', marginBottom: '20px' }}></div>
              <div className="skeleton-line" style={{ width: '100%', marginBottom: '10px' }}></div>
              <div className="skeleton-line" style={{ width: '100%', marginBottom: '10px' }}></div>
              <div className="skeleton-line" style={{ width: '60%' }}></div>
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
          {data.map((scheme, i) => (
            <motion.div key={i} variants={itemVariants} className="glass-panel" style={{ padding: '30px', display: 'flex', flexDirection: 'column' }}>
              <h3 style={{ fontSize: '1.4rem', marginBottom: '15px', color: 'var(--accent-primary)', display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                <IndianRupee size={24} style={{ marginTop: '3px', flexShrink: 0 }} />
                {scheme.title}
              </h3>
              
              <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '20px', flex: 1 }}>
                {scheme.description}
              </p>
              
              <div style={{ background: 'rgba(255,255,255,0.05)', padding: '15px', borderRadius: '12px', marginBottom: '20px' }}>
                <strong style={{ display: 'block', marginBottom: '8px', color: 'var(--text-muted)' }}>{t?.schemesEligibility || 'Eligibility:'}</strong>
                <span style={{ color: 'var(--text-main)' }}>{scheme.eligibility}</span>
              </div>
              
              <a 
                href={scheme.link} 
                target="_blank" 
                rel="noreferrer" 
                style={{ 
                  display: 'inline-flex', 
                  alignItems: 'center', 
                  gap: '8px', 
                  color: 'var(--accent-secondary)', 
                  textDecoration: 'none',
                  fontWeight: '600',
                  padding: '10px 0'
                }}
              >
                {t?.schemesApply || 'Apply / Learn More'} <ExternalLink size={16} />
              </a>
            </motion.div>
          ))}
        </motion.div>
      )}
    </motion.div>
  );
}
