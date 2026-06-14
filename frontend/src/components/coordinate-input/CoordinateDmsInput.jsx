import React from 'react';

/**
 * DMS (Degrees Minutes Seconds) input panel for CoordinateInput.
 * Pure-prop child: reads only what is passed in; no local state, no fetches.
 */
export default function CoordinateDmsInput({
  latDeg, latMin, latSec, latDir,
  lonDeg, lonMin, lonSec, lonDir,
  setLatDeg, setLatMin, setLatSec, setLatDir,
  setLonDeg, setLonMin, setLonSec, setLonDir,
  onConvert,
}) {
  return (
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
      <button type="button" onClick={onConvert} className="convert-btn">
        Convert to Decimal
      </button>
    </div>
  );
}
