import React, { useState } from 'react';

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

  // Refetch when language changes (if a location is already selected)
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
    <div className="weather-container">
      <div className="section-header">
        <h2 className="section-title">🌦️ {t.weatherPanel}</h2>
      </div>

      <div style={{ display: 'flex', gap: '10px', marginBottom: '1rem' }}>
        <select
          className="weather-select"
          value={selectedState}
          onChange={handleStateChange}
          style={{ flex: 1 }}
        >
          <option value="" disabled>Select State...</option>
          {Object.keys(FARMING_LOCATIONS).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          className="weather-select"
          value={city}
          onChange={handleCityChange}
          disabled={!selectedState}
          style={{ flex: 1 }}
        >
          <option value="" disabled>Select District/City...</option>
          {selectedState && FARMING_LOCATIONS[selectedState].map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {loading && (
        <div>
          <div className="loading-skeleton" style={{ height: '40px', width: '50%' }}></div>
          <div className="loading-skeleton" style={{ height: '16px', width: '70%', marginTop: '0.5rem' }}></div>
          <div className="loading-skeleton" style={{ height: '16px', width: '60%', marginTop: '0.3rem' }}></div>
        </div>
      )}

      {data && !loading && (
        <div className="weather-display">
          <div className="weather-main">
            <div className="weather-temp">{data.temp}</div>
            <div>
              <div className="weather-condition">{data.condition}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{data.district}</div>
            </div>
          </div>

          <div className="weather-details">
            <div className="weather-detail">💧 Humidity: <span>{data.humidity}</span></div>
            <div className="weather-detail">💨 Wind: <span>{data.wind}</span></div>
          </div>

          <div className="weather-risk">
            <strong>⚠️ Risk:</strong> {data.risk}
          </div>

          {data.advisory && (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.6rem' }}>
              💡 {data.advisory}
            </div>
          )}

          {data.forecast && (
            <div className="weather-forecast">
              {data.forecast.map((day, i) => (
                <div key={i} className="forecast-day">
                  <strong>{day.split('/')[0]?.trim()}</strong>
                  {day.split('/')[1]?.trim()}
                </div>
              ))}
            </div>
          )}

          {data.suggested_crops && data.suggested_crops.length > 0 && (
            <div style={{ marginTop: '1rem', borderTop: '1px solid rgba(0,0,0,0.1)', paddingTop: '0.8rem' }}>
              <strong>🌱 Suggested Crops:</strong>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                {data.suggested_crops.map((crop, i) => (
                  <span key={i} style={{
                    background: 'rgba(34, 197, 94, 0.1)',
                    color: 'var(--accent-color, #15803d)',
                    padding: '4px 8px',
                    borderRadius: '12px',
                    fontSize: '0.85rem',
                    fontWeight: '500'
                  }}>
                    {crop}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!data && !loading && (
        <div className="error-state">
          <div className="error-emoji">🌍</div>
          <p>Select a location to view weather advisory</p>
        </div>
      )}
    </div>
  );
}
