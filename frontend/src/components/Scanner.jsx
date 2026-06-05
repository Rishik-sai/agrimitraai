import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { ScanLine, UploadCloud, AlertCircle, CheckCircle, Leaf } from 'lucide-react';

function Scanner({ t, language }) {
  const [dragging, setDragging] = useState(false);
  const [result, setResult] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const fileInputRef = useRef(null);

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
    setResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const resp = await axios.post(`/api/scan?lang=${language || 'en'}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      // Simulate slight delay for dramatic effect
      setTimeout(() => {
        setResult(resp.data.analysis);
        setScanning(false);
      }, 1500);
    } catch (err) {
      console.error("Scan error:", err);
      setTimeout(() => {
        setResult({
          disease: 'Analysis Unavailable',
          severity: 'Unknown',
          confidence: 0,
          recommendations: ['Leaf scan analysis failed. Please verify the backend server or API key config.'],
        });
        setScanning(false);
      }, 1000);
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
    e.stopPropagation();
    setResult(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getSeverityColor = (severity) => {
    const s = (severity || '').toLowerCase();
    if (s === 'high') return '#ef4444'; // Red
    if (s === 'medium') return '#f59e0b'; // Amber
    return '#10b981'; // Emerald
  };

  return (
    <motion.div 
      className="page-container"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
    >
      <div className="page-header">
        <h1 className="page-title"><ScanLine size={32} className="inline-icon" /> {t.scannerPanel || 'Crop Disease Scanner'}</h1>
        <p className="page-subtitle">Upload an image of a leaf to instantly identify diseases and get remedies.</p>
      </div>

      <div className="scanner-layout">
        <div className="scanner-upload-section">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/*"
            style={{ display: 'none' }}
          />

          <motion.div
            className={`scanner-dropzone-large glass-panel ${dragging ? 'dragging' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={handleClick}
            whileHover={{ scale: previewUrl ? 1 : 1.02 }}
            whileTap={{ scale: previewUrl ? 1 : 0.98 }}
          >
            <AnimatePresence mode="wait">
              {previewUrl ? (
                <motion.div 
                  key="preview"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="scanner-preview-container"
                >
                  <img src={previewUrl} alt="Leaf Preview" className="scanner-preview-image" />
                  
                  {scanning && (
                    <motion.div 
                      className="scanner-laser-container"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                    >
                      <motion.div 
                        className="scanner-laser"
                        animate={{ top: ['0%', '100%', '0%'] }}
                        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      />
                      <div className="scanner-overlay-text pulsing">
                        <ScanLine className="spin-slow" /> Analyzing Crop Data...
                      </div>
                    </motion.div>
                  )}
                </motion.div>
              ) : (
                <motion.div 
                  key="upload"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="scanner-empty-state"
                >
                  <motion.div 
                    animate={{ y: [0, -10, 0] }} 
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <UploadCloud size={64} className="upload-icon" />
                  </motion.div>
                  <h3>Drag & Drop Leaf Image</h3>
                  <p>or click to browse from your device</p>
                  <span className="file-hint">Supports JPG, PNG (Max 10MB)</span>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {previewUrl && !scanning && (
            <motion.button 
              className="btn-danger mt-4" 
              onClick={handleReset}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              Scan Another Leaf
            </motion.button>
          )}
        </div>

        <div className="scanner-results-section">
          <AnimatePresence mode="wait">
            {scanning ? (
              <motion.div 
                key="loading"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="glass-panel results-placeholder loading"
              >
                <div className="skeleton-line title"></div>
                <div className="skeleton-line"></div>
                <div className="skeleton-line"></div>
                <div className="skeleton-line short"></div>
              </motion.div>
            ) : result ? (
              <motion.div 
                key="result"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="glass-panel results-card"
                style={{ borderTop: `4px solid ${getSeverityColor(result.severity)}` }}
              >
                <div className="results-header">
                  <h2>{result.disease}</h2>
                  <span 
                    className="severity-badge"
                    style={{ backgroundColor: `${getSeverityColor(result.severity)}20`, color: getSeverityColor(result.severity) }}
                  >
                    {result.severity === 'High' ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
                    {result.severity} Severity
                  </span>
                </div>
                
                <div className="results-metrics">
                  <div className="metric-box">
                    <span className="metric-label">Confidence</span>
                    <span className="metric-value">{result.confidence}%</span>
                  </div>
                  <div className="metric-box">
                    <span className="metric-label">Affected Area</span>
                    <span className="metric-value">{result.affected_area || 'Unknown'}</span>
                  </div>
                </div>

                <div className="results-recommendations">
                  <h3><Leaf size={18} /> Recommended Actions</h3>
                  <ul>
                    {(result.recommendations || []).map((rec, i) => (
                      <motion.li 
                        key={i}
                        initial={{ opacity: 0, x: 10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.1 }}
                      >
                        {rec}
                      </motion.li>
                    ))}
                  </ul>
                </div>
              </motion.div>
            ) : (
              <motion.div 
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass-panel results-placeholder empty"
              >
                <Leaf size={48} className="empty-icon" />
                <p>Upload a leaf image to see detailed AI analysis and targeted remedies.</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

export default Scanner;
