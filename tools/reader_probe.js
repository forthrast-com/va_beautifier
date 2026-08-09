// Structural QA probe for a built reader page. Returns JSON.
//
// The unit tests read the generated HTML as text; this reads it as a laid-out
// document, which is where the bugs that shipped green in Aug 2026 lived —
// a sticky bar disagreeing with a body heading, an eyebrow numbered in the
// wrong system. Anything here that needs eyes gets flagged for a screenshot
// rather than described.
(() => {
  const out = { flags: [] };
  const flag = (kind, detail) => out.flags.push({ kind, detail });

  // ── ids and internal links ───────────────────────────────────────────────
  const ids = new Map();
  for (const el of document.querySelectorAll('[id]')) {
    ids.set(el.id, (ids.get(el.id) || 0) + 1);
  }
  for (const [id, n] of ids) if (n > 1) flag('duplicate-id', `${id} ×${n}`);

  const anchors = [...document.querySelectorAll('a[href^="#"]')];
  out.internalLinks = anchors.length;
  for (const a of anchors) {
    const target = decodeURIComponent(a.getAttribute('href').slice(1));
    if (target && !document.getElementById(target)) {
      flag('dangling-link', `${a.getAttribute('href')} (${a.textContent.trim().slice(0, 30)})`);
    }
  }

  // ── heading outline ──────────────────────────────────────────────────────
  // The doc title is the only h1 and each heading nests one level below its
  // nearest rendered ancestor; a jump of more than one is an a11y regression.
  const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
    .filter(h => h.offsetParent !== null || h.closest('#fn-drawer'))
    .map(h => ({ level: +h.tagName[1], text: h.textContent.trim().slice(0, 40) }));
  const bodyHeadings = [...document.querySelectorAll('main h1, main h2, main h3, main h4, main h5, main h6')]
    .map(h => ({ level: +h.tagName[1], text: h.textContent.trim().slice(0, 40) }));
  out.h1Count = document.querySelectorAll('h1').length;
  if (out.h1Count !== 1) flag('h1-count', `${out.h1Count} h1 elements`);
  for (let i = 1; i < bodyHeadings.length; i++) {
    const jump = bodyHeadings[i].level - bodyHeadings[i - 1].level;
    if (jump > 1) {
      flag('heading-skip',
        `h${bodyHeadings[i - 1].level} "${bodyHeadings[i - 1].text}" → ` +
        `h${bodyHeadings[i].level} "${bodyHeadings[i].text}"`);
    }
  }
  out.headings = bodyHeadings.length;

  // ── sticky bar vs body heading ───────────────────────────────────────────
  // data-ch-num is what the bar renders beside the title. A chapter whose
  // body heading shows no number must not hand the bar one.
  for (const h of document.querySelectorAll('[data-sticky]')) {
    const num = h.getAttribute('data-ch-num');
    const text = h.textContent.trim();
    if (num && (/^(conclusion|epilogue)$/i).test(text)) {
      flag('bare-chapter-numbered-in-bar', `"${text}" carries data-ch-num="${num}"`);
    }
  }

  // ── layout overflow ──────────────────────────────────────────────────────
  const de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 1) {
    const wide = [...document.querySelectorAll('main *')]
      .filter(el => el.getBoundingClientRect().right > de.clientWidth + 1)
      .slice(0, 3)
      .map(el => `${el.tagName.toLowerCase()}.${(el.className || '').toString().split(' ')[0]}`);
    flag('horizontal-overflow',
      `scrollWidth ${de.scrollWidth} > client ${de.clientWidth}; ${wide.join(', ')}`);
  }

  // ── contrast of the main reading surfaces ────────────────────────────────
  const lum = (c) => {
    const [r, g, b] = c.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number)
      .map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (fg, bg) => {
    const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
    return (a + 0.05) / (b + 0.05);
  };
  const bgOf = (el) => {
    for (let n = el; n && n !== document; n = n.parentElement) {
      const c = getComputedStyle(n).backgroundColor;
      if (c && c !== 'rgba(0, 0, 0, 0)' && !c.startsWith('rgba(0, 0, 0, 0)')) return c;
    }
    return getComputedStyle(document.body).backgroundColor;
  };
  const samples = ['.paragraph p', '.para-num', '.chapter-title', '.section-title',
                   '.doc-name', '.sticky-label', '.fn-item', '.heading-la'];
  out.contrast = {};
  for (const sel of samples) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const cs = getComputedStyle(el);
    const r = ratio(cs.color, bgOf(el));
    out.contrast[sel] = Math.round(r * 100) / 100;
    const large = parseFloat(cs.fontSize) >= 24
      || (parseFloat(cs.fontSize) >= 18.66 && +cs.fontWeight >= 700);
    if (r < (large ? 3 : 4.5)) {
      flag('contrast', `${sel} ${r.toFixed(2)}:1 (${cs.color} on ${bgOf(el)})`);
    }
  }

  // ── indicator ────────────────────────────────────────────────────────────
  out.bars = document.querySelectorAll('#ch-indicator .ch-bar').length;
  out.segs = document.querySelectorAll('#ch-indicator .ch-seg').length;
  if (!out.bars) flag('indicator-empty', 'no bars rendered');
  const zero = [...document.querySelectorAll('#ch-indicator .ch-bar')]
    .filter(b => b.getBoundingClientRect().height < 1).length;
  if (zero) flag('indicator-zero-height', `${zero} bar(s) render at <1px`);

  out.paragraphs = document.querySelectorAll('.paragraph').length;
  out.footnotes = document.querySelectorAll('.fn-item').length;
  return JSON.stringify(out);
})()
