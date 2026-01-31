import React, { useState, useEffect } from 'react';
import './DataTable.css';

export default function DataTable({
  initialColumns = 3,
  initialRows = 4,
  headers = [],
  data = [],
  units = [],
  editable = true,
  onChange,
  label
}) {
  const [tableData, setTableData] = useState(() => {
    if (data.length > 0) return data;
    return Array(initialRows).fill(null).map(() => Array(initialColumns).fill(''));
  });

  const [tableHeaders, setTableHeaders] = useState(() => {
    if (headers.length > 0) return headers;
    return Array(initialColumns).fill('').map((_, i) => `Column ${i + 1}`);
  });

  const [columnUnits, setColumnUnits] = useState(() => {
    if (units.length > 0) return units;
    return Array(initialColumns).fill('');
  });

  useEffect(() => {
    if (onChange) {
      onChange({
        headers: tableHeaders,
        units: columnUnits,
        data: tableData
      });
    }
  }, [tableHeaders, columnUnits, tableData]);

  const updateCell = (rowIdx, colIdx, value) => {
    const newData = tableData.map((row, ri) =>
      ri === rowIdx
        ? row.map((cell, ci) => (ci === colIdx ? value : cell))
        : row
    );
    setTableData(newData);
  };

  const updateHeader = (colIdx, value) => {
    const newHeaders = [...tableHeaders];
    newHeaders[colIdx] = value;
    setTableHeaders(newHeaders);
  };

  const updateUnit = (colIdx, value) => {
    const newUnits = [...columnUnits];
    newUnits[colIdx] = value;
    setColumnUnits(newUnits);
  };

  const addRow = () => {
    setTableData([...tableData, Array(tableHeaders.length).fill('')]);
  };

  const removeRow = (idx) => {
    if (tableData.length > 1) {
      setTableData(tableData.filter((_, i) => i !== idx));
    }
  };

  const addColumn = () => {
    setTableHeaders([...tableHeaders, `Column ${tableHeaders.length + 1}`]);
    setColumnUnits([...columnUnits, '']);
    setTableData(tableData.map(row => [...row, '']));
  };

  const removeColumn = (idx) => {
    if (tableHeaders.length > 1) {
      setTableHeaders(tableHeaders.filter((_, i) => i !== idx));
      setColumnUnits(columnUnits.filter((_, i) => i !== idx));
      setTableData(tableData.map(row => row.filter((_, i) => i !== idx)));
    }
  };

  return (
    <div className="data-table-container">
      {label && <label className="data-table-label">{label}</label>}

      {editable && (
        <div className="table-controls">
          <button type="button" onClick={addRow}>+ Add Row</button>
          <button type="button" onClick={addColumn}>+ Add Column</button>
        </div>
      )}

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr className="header-row">
              {tableHeaders.map((header, colIdx) => (
                <th key={colIdx}>
                  {editable ? (
                    <input
                      type="text"
                      value={header}
                      onChange={(e) => updateHeader(colIdx, e.target.value)}
                      placeholder="Header"
                      className="header-input"
                    />
                  ) : (
                    header
                  )}
                  {editable && tableHeaders.length > 1 && (
                    <button
                      type="button"
                      className="remove-col-btn"
                      onClick={() => removeColumn(colIdx)}
                      title="Remove column"
                    >
                      ×
                    </button>
                  )}
                </th>
              ))}
              {editable && <th className="action-col"></th>}
            </tr>
            <tr className="units-row">
              {columnUnits.map((unit, colIdx) => (
                <th key={colIdx}>
                  {editable ? (
                    <input
                      type="text"
                      value={unit}
                      onChange={(e) => updateUnit(colIdx, e.target.value)}
                      placeholder="units (e.g., mL, °C)"
                      className="unit-input"
                    />
                  ) : (
                    unit && `(${unit})`
                  )}
                </th>
              ))}
              {editable && <th></th>}
            </tr>
          </thead>
          <tbody>
            {tableData.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {row.map((cell, colIdx) => (
                  <td key={colIdx}>
                    {editable ? (
                      <input
                        type="text"
                        value={cell}
                        onChange={(e) => updateCell(rowIdx, colIdx, e.target.value)}
                        placeholder="—"
                        className="cell-input"
                      />
                    ) : (
                      cell || '—'
                    )}
                  </td>
                ))}
                {editable && (
                  <td className="action-col">
                    {tableData.length > 1 && (
                      <button
                        type="button"
                        className="remove-row-btn"
                        onClick={() => removeRow(rowIdx)}
                        title="Remove row"
                      >
                        ×
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
