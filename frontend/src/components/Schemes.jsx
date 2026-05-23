import React, { useEffect, useState } from 'react';
import axios from 'axios';

const Schemes = ({ t, language }) => {
  const [schemes, setSchemes] = useState([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    setSchemes([]);
    setError(false);
    const fetchSchemes = async () => {
      try {
        const response = await axios.get(`/api/schemes?lang=${language || 'en'}`);
        setSchemes(response.data);
      } catch {
        setError(true);
      }
    };
    fetchSchemes();
  }, [language]);

  if (error) {
    return (
      <div className="schemes-container">
        <div className="section-header">
          <h2 className="section-title">🏛️ {t.schemesPanel}</h2>
        </div>
        <div className="error-state">
          <div className="error-emoji">📡</div>
          <p>Unable to load schemes. Start the backend server.</p>
        </div>
      </div>
    );
  }

  if (schemes.length === 0) {
    return (
      <div className="schemes-container">
        <div className="section-header">
          <h2 className="section-title">🏛️ {t.schemesPanel}</h2>
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="glass" style={{ padding: '0.85rem', marginBottom: '0.6rem' }}>
            <div className="loading-skeleton" style={{ width: '50%' }}></div>
            <div className="loading-skeleton" style={{ width: '90%' }}></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="schemes-container">
      <div className="section-header">
        <h2 className="section-title">🏛️ {t.schemesPanel}</h2>
      </div>
      <ul className="schemes-list">
        {schemes.map((scheme, idx) => (
          <li key={idx} className="scheme-card glass" id={`scheme-${idx}`}>
            <div className="scheme-top">
              <h3 className="scheme-name">{scheme.name}</h3>
              {scheme.category && (
                <span className="scheme-category">{scheme.category}</span>
              )}
            </div>
            <p className="scheme-desc">{scheme.description}</p>
            {scheme.eligibility && (
              <p className="scheme-eligibility">Eligibility: {scheme.eligibility}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default Schemes;
