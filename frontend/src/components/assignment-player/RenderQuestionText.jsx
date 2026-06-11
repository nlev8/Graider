/**
 * parseMarkdownTable - Detects markdown pipe tables in text and splits into
 * { before, table: { headers, rows }, after } or null if no table found.
 */
function parseMarkdownTable(text) {
  if (!text || typeof text !== 'string' || !text.includes('|')) return null;

  // Match pipe-delimited table patterns (may be on one line or multi-line)
  // Normalize: if all on one line, split on separator row pattern
  const lines = text.includes('\n')
    ? text.split('\n')
    : text.split(/(?=\|[\s-]+\|)/);

  // Find table boundaries
  let tableLines = [];
  let beforeText = '';
  let afterText = '';
  let inTable = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    const isSep = /^\|[\s-|:]+\|$/.test(line) || /^[\s-|:]+$/.test(line.replace(/\|/g, '|'));
    const isPipeRow = (line.match(/\|/g) || []).length >= 2;

    if (isPipeRow && !inTable) {
      inTable = true;
      // Everything before this is beforeText
      beforeText = lines.slice(0, i).join(' ').trim();
    }

    if (inTable) {
      if (isPipeRow) {
        tableLines.push(line);
      } else {
        afterText = lines.slice(i).join(' ').trim();
        break;
      }
    }
  }

  if (tableLines.length < 2) return null;

  // Parse rows - filter out separator rows
  const parseRow = (line) =>
    line.split('|').map(c => c.trim()).filter((c, i, arr) => i > 0 && i < arr.length);

  const dataRows = tableLines.filter(l => !/^\|[\s-:|]+\|?$/.test(l) && !/^[\s-:|]+$/.test(l));
  if (dataRows.length < 2) return null;

  const headers = parseRow(dataRows[0]);
  const rows = dataRows.slice(1).map(parseRow);

  return { before: beforeText, table: { headers, rows }, after: afterText };
}

/**
 * RenderQuestionText - renders question text with inline markdown tables parsed into HTML tables
 */
export default function RenderQuestionText({ text, style }) {
  const parsed = parseMarkdownTable(text);
  if (!parsed) return <p style={style}>{text}</p>;

  const tableStyle = {
    borderCollapse: 'collapse',
    margin: '10px 0',
    fontSize: '0.95rem',
    width: 'auto',
    minWidth: '200px',
  };
  const thStyle = {
    padding: '8px 16px',
    background: 'rgba(99, 102, 241, 0.15)',
    border: '1px solid rgba(255,255,255,0.15)',
    fontWeight: 600,
    textAlign: 'center',
    color: 'var(--text-primary)',
  };
  const tdStyle = {
    padding: '8px 16px',
    border: '1px solid rgba(255,255,255,0.1)',
    textAlign: 'center',
    color: 'var(--text-primary)',
  };

  return (
    <div>
      {parsed.before && <p style={style}>{parsed.before}</p>}
      <table style={tableStyle}>
        <thead>
          <tr>
            {parsed.table.headers.map((h, i) => <th key={i} style={thStyle}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {parsed.table.rows.map((row, rIdx) => (
            <tr key={rIdx}>
              {row.map((cell, cIdx) => <td key={cIdx} style={tdStyle}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {parsed.after && <p style={style}>{parsed.after}</p>}
    </div>
  );
}
