import katex from 'katex'
import 'katex/dist/katex.min.css'
import DOMPurify from 'dompurify'

/*
 * renderMarkdown — relocated verbatim from AssistantChat.jsx (CQ wave-3
 * split). Output is sanitized with DOMPurify before being returned; the
 * app-boundary XSS contract for the production call site lives in
 * __tests__/AssistantChat.xss.test.jsx.
 */
export function renderMarkdown(text) {
  if (!text) return ''
  let html = text

  // Placeholder system: protect complex HTML (KaTeX, images) from later regex passes
  var placeholders = []
  function ph(content) {
    var id = '\x00PH' + placeholders.length + '\x00'
    placeholders.push(content)
    return id
  }

  // Block math: $$...$$
  html = html.replace(/\$\$([\s\S]+?)\$\$/g, function(m, latex) {
    try {
      return ph('<div style="margin:8px 0;text-align:center">' +
        katex.renderToString(latex.trim(), { displayMode: true, throwOnError: false }) + '</div>')
    } catch (e) {
      return ph('<code style="color:#f87171">' + latex + '</code>')
    }
  })

  // Inline math: $...$  (skip currency like $5.00)
  html = html.replace(/\$([^\$\n]+?)\$/g, function(m, latex) {
    if (/^\d/.test(latex.trim())) return m
    try {
      return ph(katex.renderToString(latex.trim(), { displayMode: false, throwOnError: false }))
    } catch (e) {
      return ph('<code style="color:#f87171">' + latex + '</code>')
    }
  })

  // Markdown images: ![alt](url) — supports base64 data URIs and regular URLs
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function(m, alt, url) {
    return ph('<img src="' + url + '" alt="' + alt +
      '" style="max-width:100%;border-radius:8px;margin:8px 0;display:block" />')
  })

  // Markdown links [text](url) -> clickable links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(match, linkText, url) {
    // Download worksheet links get a special style
    if (url.indexOf('/api/download-worksheet/') !== -1 || url.indexOf('/api/download-document/') !== -1) {
      return '<a href="' + url + '" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border-radius:12px;text-decoration:none;font-weight:600;font-size:0.85em;margin:4px 0" download>' + linkText + '</a>'
    }
    return '<a href="' + url + '" style="color:var(--accent-light);text-decoration:underline" target="_blank" rel="noopener">' + linkText + '</a>'
  })
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  // Italic
  html = html.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(99,102,241,0.15);padding:2px 6px;border-radius:4px;font-size:0.85em">$1</code>')
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h4 style="margin:8px 0 4px;font-size:0.95em">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 style="margin:10px 0 4px;font-size:1.05em">$1</h3>')
  // Unordered lists
  html = html.replace(/^[-*] (.+)$/gm, '<li style="margin-left:16px;list-style:disc">$1</li>')
  // Paragraphs (double newlines)
  html = html.replace(/\n\n/g, '<br/><br/>')
  // Single newlines
  html = html.replace(/\n/g, '<br/>')

  // Restore placeholders
  for (var i = 0; i < placeholders.length; i++) {
    html = html.split('\x00PH' + i + '\x00').join(placeholders[i])
  }
  return DOMPurify.sanitize(html)
}
