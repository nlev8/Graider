"""Shared 16:9 slide geometry + structural layout classes. Every vivid value is
a CSS variable a TemplateSpec supplies; this file fixes structure, not look.
See spec §3."""

BASE_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
@page { size: 1280px 720px; margin: 0; }
html, body { background: #555; }
.deck { display:flex; flex-direction:column; align-items:center; gap:16px; }
.slide {
  width:1280px; height:720px; overflow:hidden; position:relative;
  background: var(--bg); color: var(--ink);
  font-family: var(--font-body);
  padding: var(--pad);
  display:flex; flex-direction:column;
  break-after: page;
}
/* Display font targets the heading/display divs the builder actually emits
   (.s-title, .s-head, .key-concept .big) — NOT <h1>/<h2>, which it never emits.
   Without these, headings inherit --font-body from .slide and templates whose
   head font != body font (editorial-bold, vibrant-gradient, cinematic) lose
   their headline typography. h1/h2 kept as a forward-compatible safety net. */
.slide h1, .slide h2, .s-title, .s-head, .key-concept .big, .kicker { font-family: var(--font-head); }
.kicker { text-transform:uppercase; letter-spacing:var(--kicker-spacing,3px); font-size:var(--kicker-size,18px); color:var(--accent); margin-bottom:18px; }
.s-title { font-size:var(--title-size); font-weight:var(--title-weight,800); line-height:var(--title-leading,1.05); color:var(--title-color,var(--ink)); }
.s-head  { font-size:var(--head-size); font-weight:var(--head-weight,800); color:var(--head-color,var(--accent)); margin-bottom:28px; }
.s-sub   { font-size:var(--sub-size,30px); color:var(--muted); margin-top:18px; }
.bullets { list-style:none; display:flex; flex-direction:column; gap:var(--bullet-gap,18px); font-size:var(--bullet-size,28px); line-height:1.4; }
.bullets li { display:flex; gap:16px; align-items:flex-start; color:var(--ink); }
.bullets li::before { content:var(--bullet-mark,"\\25CF"); color:var(--accent); font-size:18px; line-height:1.9; }
.body-2col { display:flex; gap:48px; flex:1; }
.col { flex:1; }
.col h3 { font-size:30px; color:var(--accent); margin-bottom:16px; font-family:var(--font-head); }
.content-row { display:flex; gap:48px; flex:1; align-items:center; }
.content-row .text { flex:1.1; }
.content-row .art { flex:.9; display:flex; align-items:center; justify-content:center; }
.content-row .art img { max-width:100%; max-height:520px; border-radius:var(--img-radius); }
.image-focus { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:24px; }
.image-focus img { max-width:90%; max-height:540px; border-radius:var(--img-radius); }
.caption { font-size:24px; color:var(--muted); }
.key-concept { flex:1; display:flex; align-items:center; justify-content:center; text-align:center; }
.key-concept .big { font-size:var(--concept-size,52px); font-weight:800; color:var(--ink); max-width:1000px; line-height:1.2; }
.divider { flex:1; display:flex; align-items:center; }
.divider .s-title { font-size:var(--divider-size,72px); }
.accent-bar { position:absolute; top:0; left:0; right:0; height:var(--bar-height,10px); background:var(--accent); }
"""
