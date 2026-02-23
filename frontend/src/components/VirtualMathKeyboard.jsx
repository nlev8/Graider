import { useState } from 'react';
import './VirtualMathKeyboard.css';

/**
 * VirtualMathKeyboard - Full-featured math expression builder.
 * Supports arbitrary fractions, exponents, roots, trig, logs, Greek letters, etc.
 * Works in both LaTeX and Unicode modes.
 */

const TABS = [
  { id: 'num', label: '123' },
  { id: 'algebra', label: 'x=' },
  { id: 'trig', label: 'sin' },
  { id: 'adv', label: 'log' },
  { id: 'greek', label: String.fromCharCode(945) + String.fromCharCode(946) },
  { id: 'sets', label: String.fromCharCode(8746) },
];

// Each key: { label, unicode, latex, wide?, type? }
// type: 'struct' means it inserts a template with cursor positioning
const PANELS = {
  num: [
    [
      { label: '7', u: '7', l: '7' },
      { label: '8', u: '8', l: '8' },
      { label: '9', u: '9', l: '9' },
      { label: String.fromCharCode(247), u: String.fromCharCode(247), l: '\\div ' },
      { label: '(', u: '(', l: '(' },
      { label: ')', u: ')', l: ')' },
    ],
    [
      { label: '4', u: '4', l: '4' },
      { label: '5', u: '5', l: '5' },
      { label: '6', u: '6', l: '6' },
      { label: String.fromCharCode(215), u: String.fromCharCode(215), l: '\\times ' },
      { label: '[', u: '[', l: '[' },
      { label: ']', u: ']', l: ']' },
    ],
    [
      { label: '1', u: '1', l: '1' },
      { label: '2', u: '2', l: '2' },
      { label: '3', u: '3', l: '3' },
      { label: String.fromCharCode(8722), u: '-', l: '-' },
      { label: '{', u: '{', l: '\\{' },
      { label: '}', u: '}', l: '\\}' },
    ],
    [
      { label: '0', u: '0', l: '0' },
      { label: '.', u: '.', l: '.' },
      { label: ',', u: ',', l: ',' },
      { label: '+', u: '+', l: '+' },
      { label: '=', u: '=', l: '=' },
      { label: String.fromCharCode(9003), u: '__BACKSPACE__', l: '__BACKSPACE__', cls: 'backspace' },
    ],
  ],
  algebra: [
    [
      { label: 'x', u: 'x', l: 'x' },
      { label: 'y', u: 'y', l: 'y' },
      { label: 'z', u: 'z', l: 'z' },
      { label: 'n', u: 'n', l: 'n' },
      { label: 'a', u: 'a', l: 'a' },
      { label: 'b', u: 'b', l: 'b' },
    ],
    [
      { label: 'x' + String.fromCharCode(8319), u: '^', l: '^{', struct: 'exp' },
      { label: 'x' + String.fromCharCode(178), u: String.fromCharCode(178), l: '^{2}' },
      { label: 'x' + String.fromCharCode(179), u: String.fromCharCode(179), l: '^{3}' },
      { label: String.fromCharCode(8730), u: String.fromCharCode(8730) + '(', l: '\\sqrt{', struct: 'sqrt' },
      { label: String.fromCharCode(8319) + String.fromCharCode(8730), u: '', l: '\\sqrt[]{', struct: 'nroot' },
      { label: 'x' + String.fromCharCode(8345), u: '_', l: '_{', struct: 'sub' },
    ],
    [
      { label: String.fromCharCode(9585) + '/' + String.fromCharCode(9586), u: '/', l: '\\frac{}{', struct: 'frac' },
      { label: '|x|', u: '|', l: '\\left|', struct: 'abs' },
      { label: String.fromCharCode(177), u: String.fromCharCode(177), l: '\\pm ' },
      { label: String.fromCharCode(8734), u: String.fromCharCode(8734), l: '\\infty ' },
      { label: String.fromCharCode(960), u: String.fromCharCode(960), l: '\\pi ' },
      { label: 'e', u: 'e', l: 'e' },
    ],
    [
      { label: '<', u: '<', l: '<' },
      { label: '>', u: '>', l: '>' },
      { label: String.fromCharCode(8804), u: String.fromCharCode(8804), l: '\\leq ' },
      { label: String.fromCharCode(8805), u: String.fromCharCode(8805), l: '\\geq ' },
      { label: String.fromCharCode(8800), u: String.fromCharCode(8800), l: '\\neq ' },
      { label: String.fromCharCode(8776), u: String.fromCharCode(8776), l: '\\approx ' },
    ],
  ],
  trig: [
    [
      { label: 'sin', u: 'sin(', l: '\\sin(', wide: true },
      { label: 'cos', u: 'cos(', l: '\\cos(', wide: true },
      { label: 'tan', u: 'tan(', l: '\\tan(', wide: true },
    ],
    [
      { label: 'csc', u: 'csc(', l: '\\csc(', wide: true },
      { label: 'sec', u: 'sec(', l: '\\sec(', wide: true },
      { label: 'cot', u: 'cot(', l: '\\cot(', wide: true },
    ],
    [
      { label: 'sin' + String.fromCharCode(8315) + String.fromCharCode(185), u: 'arcsin(', l: '\\sin^{-1}(', wide: true },
      { label: 'cos' + String.fromCharCode(8315) + String.fromCharCode(185), u: 'arccos(', l: '\\cos^{-1}(', wide: true },
      { label: 'tan' + String.fromCharCode(8315) + String.fromCharCode(185), u: 'arctan(', l: '\\tan^{-1}(', wide: true },
    ],
    [
      { label: String.fromCharCode(952), u: String.fromCharCode(952), l: '\\theta ' },
      { label: String.fromCharCode(176), u: String.fromCharCode(176), l: '^{\\circ}' },
      { label: 'rad', u: ' rad', l: '\\text{ rad}', wide: true },
    ],
  ],
  adv: [
    [
      { label: 'log', u: 'log(', l: '\\log(', wide: true },
      { label: 'ln', u: 'ln(', l: '\\ln(', wide: true },
      { label: 'log' + String.fromCharCode(8346), u: 'log_', l: '\\log_{', struct: 'logbase', wide: true },
    ],
    [
      { label: String.fromCharCode(8721), u: String.fromCharCode(8721), l: '\\sum_{', struct: 'sum', wide: true },
      { label: String.fromCharCode(8719), u: String.fromCharCode(8719), l: '\\prod_{', struct: 'prod', wide: true },
      { label: String.fromCharCode(8747), u: String.fromCharCode(8747), l: '\\int_{', struct: 'integral', wide: true },
    ],
    [
      { label: 'lim', u: 'lim ', l: '\\lim_{', struct: 'lim', wide: true },
      { label: String.fromCharCode(8594), u: String.fromCharCode(8594), l: '\\to ' },
      { label: 'f(x)', u: 'f(x)', l: 'f(x)' },
    ],
    [
      { label: "f'(x)", u: "f'(x)", l: "f'(x)" },
      { label: 'dy/dx', u: 'dy/dx', l: '\\frac{dy}{dx}', wide: true },
      { label: String.fromCharCode(8706), u: String.fromCharCode(8706), l: '\\partial ' },
    ],
  ],
  greek: [
    [
      { label: String.fromCharCode(945), u: String.fromCharCode(945), l: '\\alpha ' },
      { label: String.fromCharCode(946), u: String.fromCharCode(946), l: '\\beta ' },
      { label: String.fromCharCode(947), u: String.fromCharCode(947), l: '\\gamma ' },
      { label: String.fromCharCode(948), u: String.fromCharCode(948), l: '\\delta ' },
      { label: String.fromCharCode(949), u: String.fromCharCode(949), l: '\\epsilon ' },
      { label: String.fromCharCode(955), u: String.fromCharCode(955), l: '\\lambda ' },
    ],
    [
      { label: String.fromCharCode(956), u: String.fromCharCode(956), l: '\\mu ' },
      { label: String.fromCharCode(963), u: String.fromCharCode(963), l: '\\sigma ' },
      { label: String.fromCharCode(964), u: String.fromCharCode(964), l: '\\tau ' },
      { label: String.fromCharCode(966), u: String.fromCharCode(966), l: '\\phi ' },
      { label: String.fromCharCode(969), u: String.fromCharCode(969), l: '\\omega ' },
      { label: String.fromCharCode(961), u: String.fromCharCode(961), l: '\\rho ' },
    ],
    [
      { label: String.fromCharCode(916), u: String.fromCharCode(916), l: '\\Delta ' },
      { label: String.fromCharCode(931), u: String.fromCharCode(931), l: '\\Sigma ' },
      { label: String.fromCharCode(920), u: String.fromCharCode(920), l: '\\Theta ' },
      { label: String.fromCharCode(937), u: String.fromCharCode(937), l: '\\Omega ' },
      { label: String.fromCharCode(934), u: String.fromCharCode(934), l: '\\Phi ' },
      { label: String.fromCharCode(928), u: String.fromCharCode(928), l: '\\Pi ' },
    ],
  ],
  sets: [
    [
      { label: String.fromCharCode(8746), u: String.fromCharCode(8746), l: '\\cup ' },
      { label: String.fromCharCode(8745), u: String.fromCharCode(8745), l: '\\cap ' },
      { label: String.fromCharCode(8712), u: String.fromCharCode(8712), l: '\\in ' },
      { label: String.fromCharCode(8713), u: String.fromCharCode(8713), l: '\\notin ' },
      { label: String.fromCharCode(8834), u: String.fromCharCode(8834), l: '\\subset ' },
      { label: String.fromCharCode(8838), u: String.fromCharCode(8838), l: '\\subseteq ' },
    ],
    [
      { label: String.fromCharCode(8709), u: String.fromCharCode(8709), l: '\\emptyset ' },
      { label: String.fromCharCode(8477), u: String.fromCharCode(8477), l: '\\mathbb{R}' },
      { label: String.fromCharCode(8484), u: String.fromCharCode(8484), l: '\\mathbb{Z}' },
      { label: String.fromCharCode(8469), u: String.fromCharCode(8469), l: '\\mathbb{N}' },
      { label: String.fromCharCode(8474), u: String.fromCharCode(8474), l: '\\mathbb{Q}' },
      { label: String.fromCharCode(8450), u: String.fromCharCode(8450), l: '\\mathbb{C}' },
    ],
    [
      { label: String.fromCharCode(8704), u: String.fromCharCode(8704), l: '\\forall ' },
      { label: String.fromCharCode(8707), u: String.fromCharCode(8707), l: '\\exists ' },
      { label: String.fromCharCode(8594), u: String.fromCharCode(8594), l: '\\rightarrow ' },
      { label: String.fromCharCode(8596), u: String.fromCharCode(8596), l: '\\leftrightarrow ' },
      { label: String.fromCharCode(172), u: String.fromCharCode(172), l: '\\neg ' },
      { label: String.fromCharCode(8743), u: String.fromCharCode(8743), l: '\\wedge ' },
    ],
  ],
};

export default function VirtualMathKeyboard({ mode = 'unicode', onInsert, onBackspace, onClose, inline = false }) {
  const [tab, setTab] = useState('num');

  const handleKey = (key, e) => {
    e.preventDefault();
    e.stopPropagation();

    const value = mode === 'latex' ? key.l : key.u;

    if (value === '__BACKSPACE__') {
      onBackspace?.();
      return;
    }

    // For structural keys in LaTeX mode, insert the template
    if (mode === 'latex' && key.struct) {
      switch (key.struct) {
        case 'frac':
          onInsert?.('\\frac{}{}');
          return;
        case 'sqrt':
          onInsert?.('\\sqrt{}');
          return;
        case 'nroot':
          onInsert?.('\\sqrt[]{}');
          return;
        case 'exp':
          onInsert?.('^{}');
          return;
        case 'sub':
          onInsert?.('_{}');
          return;
        case 'abs':
          onInsert?.('\\left|\\right|');
          return;
        case 'logbase':
          onInsert?.('\\log_{}(');
          return;
        case 'sum':
          onInsert?.('\\sum_{}^{}');
          return;
        case 'prod':
          onInsert?.('\\prod_{}^{}');
          return;
        case 'integral':
          onInsert?.('\\int_{}^{}');
          return;
        case 'lim':
          onInsert?.('\\lim_{\\to }');
          return;
        default:
          break;
      }
    }

    // For structural keys in unicode mode, insert meaningful text
    if (mode === 'unicode' && key.struct) {
      switch (key.struct) {
        case 'frac':
          onInsert?.('/');
          return;
        case 'sqrt':
          onInsert?.(String.fromCharCode(8730) + '(');
          return;
        case 'nroot':
          onInsert?.(String.fromCharCode(8319) + String.fromCharCode(8730) + '(');
          return;
        case 'exp':
          onInsert?.('^');
          return;
        case 'sub':
          onInsert?.('_');
          return;
        case 'abs':
          onInsert?.('|');
          return;
        case 'logbase':
          onInsert?.('log_');
          return;
        case 'sum':
          onInsert?.(String.fromCharCode(8721));
          return;
        case 'prod':
          onInsert?.(String.fromCharCode(8719));
          return;
        case 'integral':
          onInsert?.(String.fromCharCode(8747));
          return;
        case 'lim':
          onInsert?.('lim ');
          return;
        default:
          break;
      }
    }

    onInsert?.(value);
  };

  const rows = PANELS[tab] || [];

  return (
    <div className={'vk-container' + (inline ? ' vk-inline' : '')}>
      <div className="vk-header">
        <div className="vk-tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={'vk-tab' + (tab === t.id ? ' vk-tab-active' : '')}
              onMouseDown={(e) => { e.preventDefault(); setTab(t.id); }}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button
          className="vk-close"
          onMouseDown={(e) => { e.preventDefault(); onClose?.(); }}
        >
          {String.fromCharCode(10005)}
        </button>
      </div>
      <div className="vk-grid">
        {rows.map((row, rIdx) => (
          <div key={rIdx} className="vk-row">
            {row.map((key, kIdx) => (
              <button
                key={kIdx}
                className={
                  'vk-key'
                  + (key.cls === 'backspace' ? ' vk-key-backspace' : '')
                  + (key.wide ? ' vk-key-wide' : '')
                  + (key.struct ? ' vk-key-struct' : '')
                }
                onMouseDown={(e) => handleKey(key, e)}
                title={key.struct ? (mode === 'latex' ? key.l : key.u) : undefined}
              >
                {key.label}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
