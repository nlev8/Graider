import React, { useState, useEffect } from 'react';
import './CoordinateInput.css';

const COORDINATE_FORMATS = [
  { id: 'dd', label: 'Decimal Degrees', example: '40.7128, -74.0060' },
  { id: 'dms', label: 'Degrees Minutes Seconds', example: '40°42\'46"N, 74°0\'22"W' },
  { id: 'dm', label: 'Degrees Decimal Minutes', example: '40°42.767\'N, 74°0.360\'W' },
];

export default function CoordinateInput({ value, onChange, showMap = false, label }) {
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [inputFormat, setInputFormat] = useState('dd');

  // For DMS format
  const [latDeg, setLatDeg] = useState('');
  const [latMin, setLatMin] = useState('');
  const [latSec, setLatSec] = useState('');
  const [latDir, setLatDir] = useState('N');
  const [lonDeg, setLonDeg] = useState('');
  const [lonMin, setLonMin] = useState('');
  const [lonSec, setLonSec] = useState('');
  const [lonDir, setLonDir] = useState('W');

  useEffect(() => {
    if (value) {
      parseValue(value);
    }
  }, [value]);

  const parseValue = (val) => {
    if (typeof val === 'object' && val.latitude !== undefined && val.longitude !== undefined) {
      setLatitude(String(val.latitude));
      setLongitude(String(val.longitude));
    } else if (typeof val === 'string') {
      const parts = val.split(',').map(s => s.trim());
      if (parts.length === 2) {
        setLatitude(parts[0]);
        setLongitude(parts[1]);
      }
    }
  };

  const dmsToDecimal = (deg, min, sec, dir) => {
    const d = parseFloat(deg) || 0;
    const m = parseFloat(min) || 0;
    const s = parseFloat(sec) || 0;
    let decimal = d + m / 60 + s / 3600;
    if (dir === 'S' || dir === 'W') {
      decimal = -decimal;
    }
    return decimal;
  };

  const handleDecimalChange = (lat, lon) => {
    const coord = {
      latitude: parseFloat(lat) || 0,
      longitude: parseFloat(lon) || 0,
      format: 'dd',
      raw: `${lat}, ${lon}`
    };
    onChange(coord);
  };

  const handleLatChange = (e) => {
    const val = e.target.value;
    setLatitude(val);
    handleDecimalChange(val, longitude);
  };

  const handleLonChange = (e) => {
    const val = e.target.value;
    setLongitude(val);
    handleDecimalChange(latitude, val);
  };

  const handleDMSUpdate = () => {
    const latDecimal = dmsToDecimal(latDeg, latMin, latSec, latDir);
    const lonDecimal = dmsToDecimal(lonDeg, lonMin, lonSec, lonDir);

    setLatitude(latDecimal.toFixed(6));
    setLongitude(lonDecimal.toFixed(6));

    const coord = {
      latitude: latDecimal,
      longitude: lonDecimal,
      format: 'dms',
      raw: `${latDeg}°${latMin}'${latSec}"${latDir}, ${lonDeg}°${lonMin}'${lonSec}"${lonDir}`
    };
    onChange(coord);
  };

  const lat = parseFloat(latitude) || 0;
  const lon = parseFloat(longitude) || 0;
  const hasValidCoords = lat !== 0 || lon !== 0;

  return (
    <div className="coordinate-input-container">
      {label && <label className="coordinate-label">{label}</label>}

      <div className="format-selector">
        <label>Format:</label>
        <select value={inputFormat} onChange={(e) => setInputFormat(e.target.value)}>
          {COORDINATE_FORMATS.map(f => (
            <option key={f.id} value={f.id}>{f.label}</option>
          ))}
        </select>
        <span className="format-example">
          e.g., {COORDINATE_FORMATS.find(f => f.id === inputFormat)?.example}
        </span>
      </div>

      {inputFormat === 'dd' && (
        <div className="decimal-input">
          <div className="coord-field">
            <label>Latitude:</label>
            <input
              type="number"
              step="0.0001"
              value={latitude}
              onChange={handleLatChange}
              placeholder="-90 to 90"
              min="-90"
              max="90"
            />
          </div>
          <div className="coord-field">
            <label>Longitude:</label>
            <input
              type="number"
              step="0.0001"
              value={longitude}
              onChange={handleLonChange}
              placeholder="-180 to 180"
              min="-180"
              max="180"
            />
          </div>
        </div>
      )}

      {inputFormat === 'dms' && (
        <div className="dms-input">
          <div className="dms-row">
            <label>Latitude:</label>
            <input
              type="number"
              value={latDeg}
              onChange={(e) => setLatDeg(e.target.value)}
              placeholder="°"
              className="deg"
              min="0"
              max="90"
            />
            <span>°</span>
            <input
              type="number"
              value={latMin}
              onChange={(e) => setLatMin(e.target.value)}
              placeholder="'"
              className="min"
              min="0"
              max="59"
            />
            <span>'</span>
            <input
              type="number"
              step="0.01"
              value={latSec}
              onChange={(e) => setLatSec(e.target.value)}
              placeholder='"'
              className="sec"
              min="0"
              max="59.99"
            />
            <span>"</span>
            <select value={latDir} onChange={(e) => setLatDir(e.target.value)}>
              <option value="N">N</option>
              <option value="S">S</option>
            </select>
          </div>
          <div className="dms-row">
            <label>Longitude:</label>
            <input
              type="number"
              value={lonDeg}
              onChange={(e) => setLonDeg(e.target.value)}
              placeholder="°"
              className="deg"
              min="0"
              max="180"
            />
            <span>°</span>
            <input
              type="number"
              value={lonMin}
              onChange={(e) => setLonMin(e.target.value)}
              placeholder="'"
              className="min"
              min="0"
              max="59"
            />
            <span>'</span>
            <input
              type="number"
              step="0.01"
              value={lonSec}
              onChange={(e) => setLonSec(e.target.value)}
              placeholder='"'
              className="sec"
              min="0"
              max="59.99"
            />
            <span>"</span>
            <select value={lonDir} onChange={(e) => setLonDir(e.target.value)}>
              <option value="E">E</option>
              <option value="W">W</option>
            </select>
          </div>
          <button type="button" onClick={handleDMSUpdate} className="convert-btn">
            Convert to Decimal
          </button>
        </div>
      )}

      {showMap && hasValidCoords && (
        <div className="map-preview">
          <iframe
            title="Location Preview"
            width="100%"
            height="200"
            frameBorder="0"
            src={`https://www.openstreetmap.org/export/embed.html?bbox=${lon-0.01},${lat-0.01},${lon+0.01},${lat+0.01}&layer=mapnik&marker=${lat},${lon}`}
          />
          <p className="map-coords">
            Coordinates: {lat.toFixed(4)}, {lon.toFixed(4)}
          </p>
        </div>
      )}
    </div>
  );
}
