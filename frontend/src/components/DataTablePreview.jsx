/**
 * DataTablePreview — renders a CSV at a URL as a sortable HTML table.
 *
 * Extracted from App.jsx + PlannerTab.jsx (2026-05-02) where it was
 * defined twice, byte-for-byte identical. Shared module is the single
 * source of truth.
 *
 * Props:
 *   url: string — the URL to fetch CSV from
 */
import React from "react";

export default function DataTablePreview({ url }) {
  var [rows, setRows] = React.useState(null);
  React.useEffect(function() {
    fetch(url).then(function(r) { return r.text(); }).then(function(text) {
      var lines = text.trim().split(String.fromCharCode(10));
      var parsed = lines.map(function(line) {
        // Simple CSV parse (handles quoted fields)
        var result = [];
        var current = "";
        var inQuotes = false;
        for (var i = 0; i < line.length; i++) {
          var ch = line[i];
          if (ch === '"') { inQuotes = !inQuotes; }
          else if (ch === ',' && !inQuotes) { result.push(current.trim()); current = ""; }
          else { current += ch; }
        }
        result.push(current.trim());
        return result;
      });
      setRows(parsed);
    }).catch(function() { setRows([]); });
  }, [url]);
  if (!rows) return React.createElement("div", { style: { padding: "20px", textAlign: "center", color: "var(--text-secondary)" } }, "Loading table...");
  if (rows.length === 0) return React.createElement("div", { style: { padding: "20px", color: "var(--text-secondary)" } }, "Empty table");
  var header = rows[0];
  var body = rows.slice(1);
  return (
    React.createElement("div", { style: { maxHeight: "400px", overflow: "auto", borderRadius: "12px", border: "1px solid var(--border)" } },
      React.createElement("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" } },
        React.createElement("thead", null,
          React.createElement("tr", null,
            header.map(function(h, i) {
              return React.createElement("th", { key: i, style: { padding: "10px 12px", background: "rgba(139, 92, 246, 0.1)", fontWeight: 600, textAlign: "left", borderBottom: "2px solid var(--border)", position: "sticky", top: 0 } }, h);
            })
          )
        ),
        React.createElement("tbody", null,
          body.map(function(row, ri) {
            return React.createElement("tr", { key: ri, style: { background: ri % 2 === 0 ? "transparent" : "rgba(0,0,0,0.02)" } },
              row.map(function(cell, ci) {
                return React.createElement("td", { key: ci, style: { padding: "8px 12px", borderBottom: "1px solid var(--border)" } }, cell);
              })
            );
          })
        )
      )
    )
  );
}
