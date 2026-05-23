import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

function Scanner({ t, language }) {
  const [dragging, setDragging] = useState(false);
  const [result, setResult] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const fileInputRef = useRef(null);

  // Clean up preview URL when component unmounts or before creating a new one
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleScan = async (file) => {
    if (!file) return;
    setScanning(true);
    setResult(null); // Clear previous result when scanning a new file
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const resp = await axios.post(`/api/scan?lang=${language || 'en'}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setResult(resp.data.analysis);
    } catch (err) {
      console.error("Scan error:", err);
      setResult({
        disease: 'Analysis Unavailable',
        severity: 'Unknown',
        confidence: 0,
        recommendations: ['Leaf scan analysis failed. Please verify the backend server or API key config.'],
      });
    } finally {
      setScanning(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      setPreviewUrl(URL.createObjectURL(file));
      handleScan(file);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (scanning) return;
    
    const file = e.dataTransfer.files[0];
    if (file) {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      setPreviewUrl(URL.createObjectURL(file));
      handleScan(file);
    }
  };

  const handleClick = () => {
    if (scanning) return;
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleReset = (e) => {
    e.stopPropagation(); // Avoid triggering file upload click
    setResult(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getSeverityClass = (severity) => {
    const s = (severity || '').toLowerCase();
    if (s === 'high') return 'severity-high';
    if (s === 'medium') return 'severity-medium';
    return 'severity-low';
  };

  return (
    <div className="scanner-container">
      <div className="section-header">
        <h2 className="section-title">🔬 {t.scannerPanel}</h2>
      </div>

      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        style={{ display: 'none' }}
      />

      {/* Drop zone / Preview */}
      <div
        className={`scanner-dropzone ${dragging ? 'dragging' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={handleClick}
        style={{ position: 'relative' }}
      >
        {previewUrl ? (
          <>
            <img src={previewUrl} alt="Leaf Preview" className="scanner-preview" />
            {scanning && (
              <div className="scanner-overlay">
                <div className="scanner-line"></div>
                <div>{t.scannerAnalyzing}</div>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="scanner-icon">🍃</div>
            <div className="scanner-label">{t.scannerUpload}</div>
            <div className="scanner-hint">Supports JPG, PNG up to 10MB</div>
          </>
        )}
      </div>

      {/* Reset button if we have a preview and are not currently scanning */}
      {previewUrl && !scanning && (
        <button className="reset-scan-btn" onClick={handleReset}>
          ❌ Clear Image
        </button>
      )}

      {/* Result */}
      {result && (
        <div className="scan-result">
          <div className="scan-disease">{result.disease}</div>
          <span className={`scan-severity ${getSeverityClass(result.severity)}`}>
            {result.severity} Severity
          </span>
          {result.confidence > 0 && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              Confidence: {result.confidence}%
            </div>
          )}
          {result.affected_area && result.affected_area !== 'None' && (
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
              Affected Area: {result.affected_area}
            </div>
          )}
          <ul className="scan-recs">
            {(result.recommendations || []).map((rec, i) => (
              <li key={i}>{rec}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default Scanner;
