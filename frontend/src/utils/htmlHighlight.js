/*
 * htmlHighlight — pure HTML/text marker-highlight utilities, pushed down from the App.jsx
 * shell (App.jsx decomposition slice 13). These are PURE functions (string in, string out;
 * no React, no App state, no closure) that only call one another. The 8th sibling
 * applyAllHighlights stayed in App because it also depends on the marker accessors
 * (getMarkerText/getEndMarker) and the HIGHLIGHT_COLORS constant; it imports
 * highlightTextInHtml from here. Bodies moved VERBATIM (de-indented to module scope).
 */
const normalizeText = (str) => {
  if (!str) return str;
  return str
    .replace(/[\u2018\u2019\u201A\u201B]/g, "'")  // Smart single quotes to straight
    .replace(/[\u201C\u201D\u201E\u201F]/g, '"')  // Smart double quotes to straight
    .replace(/[\u2013\u2014]/g, '-')              // En-dash and em-dash to hyphen
    .replace(/\u2026/g, '...')                    // Ellipsis to dots
    .replace(/\u00A0/g, ' ');                     // Non-breaking space to regular space
};

// Build a mapping from plain text positions to HTML positions
// Entity-aware: &amp; maps to a single plain text character (&)
const buildTextToHtmlMap = (html) => {
  const map = []; // map[plainTextIndex] = htmlIndex
  let inTag = false;
  let plainIndex = 0;

  for (let i = 0; i < html.length; i++) {
    if (html[i] === '<') {
      inTag = true;
    } else if (html[i] === '>') {
      inTag = false;
    } else if (!inTag) {
      // HTML entity (e.g., &amp; &lt; &#123;) → one plain text char
      if (html[i] === '&') {
        const semiPos = html.indexOf(';', i);
        if (semiPos !== -1 && semiPos - i <= 8) {
          map[plainIndex] = i;
          plainIndex++;
          i = semiPos; // skip to ';' (loop will i++ past it)
          continue;
        }
      }
      map[plainIndex] = i;
      plainIndex++;
    }
  }
  map[plainIndex] = html.length; // End marker
  return map;
};

// Extract plain text from HTML (strips tags and decodes entities)
const htmlToPlainText = (html) => {
  let text = html.replace(/<[^>]*>/g, '');
  // Decode common HTML entities so search text matches
  text = text
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, code) => String.fromCharCode(parseInt(code, 16)));
  return text;
};

// Highlight text in HTML with a colored span (handles multi-line markers)
const highlightTextInHtml = (html, text, color, markerId, searchAfterPos = 0) => {
  if (!text || !html) return html;

  // Check if already highlighted
  if (html.includes(`data-marker-id="${markerId}"`)) {
    return html; // Already highlighted
  }

  // If text spans multiple lines, highlight each line separately
  // This handles cross-paragraph selections where a single span wrapper breaks
  // Split on newlines, carriage returns, or multiple spaces (browsers vary)
  const lines = text.split(/[\n\r]+/).map(l => l.trim()).filter(l => l.length > 0);
  if (lines.length > 1) {
    let result = html;
    let currentOffset = searchAfterPos;
    for (let li = 0; li < lines.length; li++) {
      // Find where this line matches BEFORE highlighting (to track position)
      const plainBefore = htmlToPlainText(result);
      const normalizedBefore = normalizeText(plainBefore).toLowerCase();
      const lineNorm = normalizeText(lines[li]).replace(/\s+/g, ' ').trim().toLowerCase();
      const linePos = normalizedBefore.indexOf(lineNorm, currentOffset);

      result = highlightTextInHtml(result, lines[li], color, `${markerId}-line${li}`, currentOffset);

      // Advance offset past this match so next line searches further in the document
      if (linePos !== -1) {
        currentOffset = linePos + lineNorm.length;
      }
    }
    return result;
  }

  // Normalize the search text
  const normalizedSearchText = normalizeText(text).replace(/\s+/g, ' ').trim();

  // Extract plain text from HTML and normalize it
  const plainText = htmlToPlainText(html);
  const normalizedPlainText = normalizeText(plainText);

  // Build mapping from plain text positions to HTML positions
  const textToHtmlMap = buildTextToHtmlMap(html);

  // Try to find the normalized search text in normalized plain text
  // Use case-insensitive search, starting from searchAfterPos
  const searchLower = normalizedSearchText.toLowerCase();
  const plainLower = normalizedPlainText.toLowerCase();

  let matchStart = plainLower.indexOf(searchLower, searchAfterPos);

  // If exact match fails, try matching with flexible whitespace
  if (matchStart === -1) {
    // Create regex that allows any whitespace between words
    const words = normalizedSearchText.split(/\s+/).filter(w => w.length > 0);
    if (words.length > 0) {
      const flexPattern = words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s+');
      const flexRegex = new RegExp(flexPattern, 'gi');
      let flexMatch;
      while ((flexMatch = flexRegex.exec(normalizedPlainText)) !== null) {
        if (flexMatch.index >= searchAfterPos) {
          matchStart = flexMatch.index;
          break;
        }
      }
    }
  }

  if (matchStart !== -1) {
    // Find match end in plain text
    const matchEnd = matchStart + normalizedSearchText.length;

    // Map to HTML positions
    const htmlStart = textToHtmlMap[matchStart];
    // Find the HTML end position - need to find where the last matched character ends
    let htmlEnd = textToHtmlMap[matchEnd] || html.length;

    // Adjust htmlEnd to include any trailing content before the next tag
    // This ensures we capture the full matched text even with length differences
    const remainingPlain = normalizedPlainText.substring(matchStart, matchEnd);
    let plainIdx = matchStart;
    let htmlIdx = htmlStart;

    // Walk through character by character to find exact HTML end
    while (plainIdx < matchEnd && htmlIdx < html.length) {
      if (html[htmlIdx] === '<') {
        // Skip HTML tag
        while (htmlIdx < html.length && html[htmlIdx] !== '>') htmlIdx++;
        htmlIdx++; // Skip '>'
      } else if (html[htmlIdx] === '&') {
        // HTML entity — skip to closing ';'
        const semiPos = html.indexOf(';', htmlIdx);
        if (semiPos !== -1 && semiPos - htmlIdx <= 8) {
          htmlIdx = semiPos + 1;
        } else {
          htmlIdx++;
        }
        plainIdx++;
      } else {
        plainIdx++;
        htmlIdx++;
      }
    }
    htmlEnd = htmlIdx;

    // Extract the HTML content to wrap
    const matchedHtml = html.substring(htmlStart, htmlEnd);

    // If matched range crosses block elements, extract the text content of each
    // block and highlight them individually (a span can't validly wrap across <p> tags)
    if (/<\/?(?:p|div|h[1-6]|li|br)\b/i.test(matchedHtml)) {
      // Extract individual text segments from the matched HTML
      const textSegments = matchedHtml
        .replace(/<[^>]*>/g, '\n')  // Replace tags with newlines
        .split('\n')
        .map(s => s.trim())
        .filter(s => s.length > 0);

      if (textSegments.length > 1) {
        // Re-highlight each text segment individually in the full HTML
        let result = html;
        for (let si = 0; si < textSegments.length; si++) {
          result = highlightTextInHtml(result, textSegments[si], color, `${markerId}-seg${si}`);
        }
        return result;
      }
    }

    // Single element — wrap normally
    const highlightSpan = `<span data-marker-id="${markerId}" style="background:${color.bg};border-bottom:2px solid ${color.border};padding:2px 0;">${matchedHtml}</span>`;

    return html.substring(0, htmlStart) + highlightSpan + html.substring(htmlEnd);
  }

  console.log('Highlight match failed for:', text.substring(0, 50) + '...');
  console.log('Searching for:', searchLower.substring(0, 80));
  console.log('Plain text excerpt:', plainLower.substring(0, 300));
  return html; // No match found
};

// Remove highlight from HTML by marker ID
const removeHighlightFromHtml = (html, markerId) => {
  if (!html) return html;
  // Remove the span but keep the inner content (handles nested tags)
  // Match opening span with marker ID, then capture everything until closing span
  const regex = new RegExp(`<span[^>]*data-marker-id="${markerId}"[^>]*>(.*?)</span>`, 'gis');
  return html.replace(regex, '$1');
};

// Convert plain text (from AI-generated assignments) to rich HTML matching docx-parsed format
const textToRichHtml = (text) => {
  const style = '<style>body{font-family:Georgia,serif;line-height:1.6}table{border-collapse:collapse;width:100%;margin:15px 0}td,th{border:1px solid #ccc;padding:8px 12px;text-align:left}th{background:#f5f5f5;font-weight:bold}p{margin:10px 0}h1,h2,h3{margin:20px 0 10px 0}</style>';
  const lines = text.split('\n');
  const parts = [style];
  let qNum = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const escaped = line.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const trimmed = escaped.trim();
    if (!trimmed) continue;
    // First line = title
    if (i === 0) { parts.push('<h1><strong>' + escaped + '</strong></h1>'); continue; }
    // Name/Date/Period
    if (/^(Name|Date|Period):/.test(trimmed)) {
      const [label, ...rest] = escaped.split(':');
      parts.push('<p><strong>' + label + ': </strong>' + rest.join(':') + '</p>');
      continue;
    }
    // ALL-CAPS = section heading
    if (trimmed === trimmed.toUpperCase() && /[A-Z]/.test(trimmed) && !/^_+$/.test(trimmed)) {
      parts.push('<h2><strong>' + escaped + '</strong></h2>');
      continue;
    }
    // Numbered question (N) ...)
    const qMatch = trimmed.match(/^(\d+)\)\s+(.+)/);
    if (qMatch) {
      qNum++;
      parts.push(
        '<table><tr><td><p>[GRAIDER:QUESTION:' + qNum + ']<strong>  ' + escaped + '</strong></p></td></tr>' +
        '<tr><td><p><strong>Your Answer:</strong></p><p><em>Type your answer here...</em></p></td></tr></table>'
      );
      // Skip following Response/Answer/underscore lines (they're replaced by the table)
      while (i + 1 < lines.length && /^(Response|Answer|_{5,})/.test(lines[i + 1].trim())) i++;
      continue;
    }
    // Vocab term (word: ___)
    if (/^.+:\s*_{5,}/.test(trimmed)) {
      const term = escaped.split(':')[0];
      parts.push('<table><tr><td><p><strong>' + term + ':</strong> ' + '_'.repeat(60) + '</p></td></tr></table>');
      continue;
    }
    // Skip standalone underscore lines
    if (/^_+$/.test(trimmed)) continue;
    // Default
    parts.push('<p>' + escaped + '</p>');
  }
  return parts.join('\n');
};

// Remove ALL marker highlights from HTML (for clean reset)
const removeAllHighlightsFromHtml = (html) => {
  if (!html) return html;
  // Remove all spans with data-marker-id attribute
  return html.replace(/<span[^>]*data-marker-id="[^"]*"[^>]*>(.*?)<\/span>/gis, '$1');
};

export {
  normalizeText,
  buildTextToHtmlMap,
  htmlToPlainText,
  highlightTextInHtml,
  removeHighlightFromHtml,
  textToRichHtml,
  removeAllHighlightsFromHtml,
};
