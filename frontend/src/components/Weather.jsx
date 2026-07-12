import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Cloud, MapPin, Droplets, Wind, AlertTriangle, Lightbulb } from 'lucide-react';

const FARMING_LOCATIONS = {
  "Andhra Pradesh": ["Guntur", "Kurnool", "Prakasam", "Nellore", "Anantapur", "West Godavari"],
  "Telangana": ["Warangal", "Karimnagar", "Nizamabad", "Khammam", "Nalgonda", "Mahabubnagar"],
  "Tamil Nadu": ["Thanjavur", "Madurai", "Coimbatore", "Salem", "Tiruchirappalli", "Erode"],
  "Karnataka": ["Dharwad", "Belagavi", "Tumakuru", "Hassan", "Mandya", "Raichur"],
  "Maharashtra": ["Nashik", "Pune", "Jalgaon", "Ahmednagar", "Solapur", "Kolhapur", "Latur"],
  "Punjab": ["Ludhiana", "Patiala", "Amritsar", "Jalandhar", "Bathinda", "Sangrur"],
  "Haryana": ["Karnal", "Hisar", "Rohtak", "Sirsa", "Panipat", "Kurukshetra"],
  "Uttar Pradesh": ["Gorakhpur", "Bareilly", "Meerut", "Aligarh", "Saharanpur", "Moradabad"],
  "Madhya Pradesh": ["Ujjain", "Indore", "Sehore", "Vidisha", "Hoshangabad", "Dewas"],
  "Gujarat": ["Rajkot", "Junagadh", "Amreli", "Banaskantha", "Mehsana", "Sabarkantha"],
  "Rajasthan": ["Sri Ganganagar", "Hanumangarh", "Bikaner", "Kota", "Alwar", "Bharatpur"],
  "Bihar": ["Muzaffarpur", "Purnia", "Gaya", "Begusarai", "Samastipur", "East Champaran"],
  "West Bengal": ["Bardhaman", "Hooghly", "Nadia", "Birbhum", "Murshidabad", "Cooch Behar"]
};

export default function Weather({ t, language }) {
  const [selectedState, setSelectedState] = useState('');
  const [city, setCity] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchWeather = async (stateName, cityName, lang) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/weather/${stateName}/${cityName}?lang=${lang || 'en'}`);
      const json = await res.json();
      setData(json);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    if (selectedState && city) {
      fetchWeather(selectedState, city, language);
    }
  }, [language]);

  const handleStateChange = (e) => {
    setSelectedState(e.target.value);
    setCity('');
    setData(null);
  };

  const handleCityChange = (e) => {
    const newCity = e.target.value;
    setCity(newCity);
    if (newCity && selectedState) {
      fetchWeather(selectedState, newCity, language);
    }
  };

  return (
    <motion.div 
      className="page-container"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
    >
      <div className="page-header">
        <h1 className="page-title"><Cloud className="inline-icon" /> {t.weatherPanel || 'Weather Advisory'}</h1>
        <p className="page-subtitle">{t?.weatherSubtitle || 'Get hyper-local weather risk assessments and crop suggestions.'}</p>
      </div>

      <div className="glass-panel" style={{ padding: '30px', marginBottom: '40px' }}>
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '250px' }}>
            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-muted)' }}><MapPin size={16} style={{ display: 'inline', verticalAlign: 'text-bottom' }}/> {t?.weatherSelectState || 'Select State'}</label>
            <select
              className="lang-select"
              value={selectedState}
              onChange={handleStateChange}
              style={{ width: '100%', padding: '12px', fontSize: '1rem' }}
            >
              <option value="" disabled>{t?.weatherSelectStatePlaceholder || 'Select State...'}</option>
              {Object.keys(FARMING_LOCATIONS).map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div style={{ flex: 1, minWidth: '250px' }}>
            <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-muted)' }}><MapPin size={16} style={{ display: 'inline', verticalAlign: 'text-bottom' }}/> {t?.weatherSelectDistrict || 'Select District/City'}</label>
            <select
              className="lang-select"
              value={city}
              onChange={handleCityChange}
              disabled={!selectedState}
              style={{ width: '100%', padding: '12px', fontSize: '1rem', opacity: !selectedState ? 0.5 : 1 }}
            >
              <option value="" disabled>{t?.weatherSelectDistrictPlaceholder || 'Select District/City...'}</option>
              {selectedState && FARMING_LOCATIONS[selectedState].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {loading ? (
          <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="glass-panel" style={{ padding: '40px' }}>
            <div className="skeleton-line" style={{ height: '60px', width: '30%', marginBottom: '20px' }}></div>
            <div className="skeleton-line" style={{ height: '20px', width: '70%', marginBottom: '10px' }}></div>
            <div className="skeleton-line" style={{ height: '20px', width: '60%' }}></div>
          </motion.div>
        ) : data ? (
          <motion.div 
            key="data" 
            initial={{ opacity: 0, scale: 0.95 }} 
            animate={{ opacity: 1, scale: 1 }} 
            exit={{ opacity: 0 }}
            className="glass-panel" 
            style={{ padding: '40px', display: 'flex', flexDirection: 'column', gap: '30px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
              <div>
                <div style={{ fontSize: '4rem', fontWeight: 'bold', lineHeight: '1', color: 'var(--text-main)', marginBottom: '10px' }}>
                  {data.temp}
                </div>
                <div style={{ fontSize: '1.5rem', color: 'var(--text-secondary)' }}>{data.condition}</div>
                <div style={{ color: 'var(--text-muted)' }}>{data.district}</div>
              </div>
              
              <div style={{ display: 'flex', gap: '20px' }}>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '20px', borderRadius: '16px', minWidth: '120px', textAlign: 'center' }}>
                  <Droplets size={32} color="#3b82f6" style={{ margin: '0 auto 10px' }} />
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{t?.weatherHumidity || 'Humidity'}</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: '600' }}>{data.humidity}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '20px', borderRadius: '16px', minWidth: '120px', textAlign: 'center' }}>
                  <Wind size={32} color="#10b981" style={{ margin: '0 auto 10px' }} />
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{t?.weatherWind || 'Wind'}</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: '600' }}>{data.wind}</div>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '20px', borderRadius: '16px' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#ef4444', marginBottom: '10px' }}>
                  <AlertTriangle size={20} /> {t?.weatherRisk || 'Weather Risk'}
                </h3>
                <p style={{ color: 'var(--text-main)' }}>{data.risk}</p>
              </div>
              
              {data.advisory && (
                <div style={{ flex: 2, background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)', padding: '20px', borderRadius: '16px' }}>
                  <h3 style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#3b82f6', marginBottom: '10px' }}>
                    <Lightbulb size={20} /> {t?.weatherAdvisory || 'Advisory'}
                  </h3>
                  <p style={{ color: 'var(--text-main)', lineHeight: '1.6' }}>{data.advisory}</p>
                </div>
              )}
            </div>

            {data.suggested_crops && data.suggested_crops.length > 0 && (
              <div>
                <h3 style={{ marginBottom: '15px' }}>{t?.weatherSuggestedCrops || '🌱 Suggested Crops for Current Conditions'}</h3>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  {data.suggested_crops.map((crop, i) => (
                    <span key={i} style={{
                      background: 'linear-gradient(135deg, #10b981, #059669)',
                      color: 'white',
                      padding: '8px 16px',
                      borderRadius: '20px',
                      fontWeight: '500'
                    }}>
                      {crop}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        ) : (
          <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-panel" style={{ padding: '60px', textAlign: 'center' }}>
            <Cloud size={64} style={{ color: 'var(--text-muted)', marginBottom: '20px', opacity: 0.5 }} />
            <h2 style={{ color: 'var(--text-secondary)' }}>{t?.weatherSelectLocation || 'Select a location'}</h2>
            <p style={{ color: 'var(--text-muted)' }}>{t?.weatherSelectLocationDesc || 'Choose your state and district to view hyper-local weather data.'}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
