// ─────────────────────────────────────────────────────────────────────────
// Vatican-document reader scripts.
//
// Loaded + inlined by make_html.py with two substitutions:
//   __INDICATOR_JSON__   the JSON array of chapter descriptors for the indicator
//   __DOC_NAME__         the JSON-encoded display name (e.g. "Laudato Si'")
// ─────────────────────────────────────────────────────────────────────────

// ── sticky heading bar ──
const stickyNum   = document.getElementById('sticky-num');
const stickyLabel = document.getElementById('sticky-label');
const stickyEls   = Array.from(document.querySelectorAll('[data-sticky]'));
function updateSticky() {
  let current = null;
  for (const el of stickyEls) {
    if (el.getBoundingClientRect().top < 40) current = el;
    else break;
  }
  if (current) {
    stickyLabel.textContent = current.textContent;
    stickyNum.textContent   = current.dataset.chNum || '';
  } else {
    stickyLabel.textContent = __DOC_NAME__;
    stickyNum.textContent   = '';
  }
}
window.addEventListener('scroll', updateSticky, {passive: true});
updateSticky();

function scrollToEl(el, smooth) {
  const barH = document.getElementById('sticky-bar').offsetHeight;
  const top = el.getBoundingClientRect().top + window.scrollY - barH - 8;
  window.scrollTo({ top, behavior: smooth ? 'smooth' : 'instant' });
  if (el.id) history.replaceState(null, '', '#' + el.id);
}

// ── chapter indicator ──
const chapters = __INDICATOR_JSON__;
const nav = document.getElementById('ch-indicator');

// build bars (skip spacer entries for bar array, but insert gap divs)
const bars = [];
chapters.forEach(ch => {
  if (ch.spacer) {
    const gap = document.createElement('div');
    gap.className = 'ch-part-gap';
    nav.appendChild(gap);
  }
  const bar = document.createElement('div');
  bar.className = 'ch-bar';
  bar.title = ch.label;
  // proportional sizing when the parent indicator is height-capped (LS);
  // no-op when bar height is summed from fixed-height segs (GeS).
  bar.style.flexGrow = ch.paras.length || 1;
  ch.paras.forEach(pn => {
    const seg = document.createElement('div');
    seg.className = 'ch-seg';
    seg.dataset.para = pn;
    seg.addEventListener('click', e => {
      e.stopPropagation();
      scrollToEl(document.getElementById('para-' + pn), true);
    });
    bar.appendChild(seg);
  });
  bar.addEventListener('click', () =>
    scrollToEl(document.getElementById(ch.id), true)
  );
  nav.appendChild(bar);
  bars.push(bar);
});

// para → chapter index lookup
const paraToChIdx = {};
chapters.forEach((ch, i) => ch.paras.forEach(pn => paraToChIdx[pn] = i));

// collect all para elements in order
const paraEls = Array.from(document.querySelectorAll('.paragraph'));

function updateIndicator() {
  const threshold = window.innerHeight * 0.35;
  let curPara = paraEls[0]?.dataset?.para;
  for (const el of paraEls) {
    if (el.getBoundingClientRect().top <= threshold) curPara = el.id.replace('para-', '');
    else break;
  }
  const chIdx = paraToChIdx[curPara] ?? 0;
  const activePart = chapters[chIdx]?.part;
  bars.forEach((b, i) => {
    const isActive = i === chIdx;
    b.classList.toggle('active', isActive);
    b.classList.toggle('part-active', !isActive && chapters[i].part === activePart);
    if (isActive) {
      b.querySelectorAll('.ch-seg').forEach(s =>
        s.classList.toggle('cur-para', s.dataset.para == curPara)
      );
    }
  });
}
window.addEventListener('scroll', updateIndicator, {passive: true});
updateIndicator();

// ── publish sticky-bar height as a CSS var ──
// The indicator + (potential) other layout pieces read --bar-h so they
// can fit / centre inside the visible viewport instead of overlapping
// the sticky bar.
const stickyBar = document.getElementById('sticky-bar');
function publishBarH() {
  document.documentElement.style.setProperty('--bar-h', stickyBar.offsetHeight + 'px');
}
publishBarH();
window.addEventListener('resize', publishBarH);

// ── LS-only: soft-anchor paragraph numbers ──
// Three-phase trajectory as paragraph scrolls up through viewport:
//   A. paragraph below viewport centre -> number sits at top of paragraph
//   B. paragraph approaching top -> anchor lerps from viewport centre
//                                   down to (bar bottom + small offset)
//   C. paragraph past top -> number sticks just under the bar, clamped
//                            to paragraph bottom so it exits with the para
// Number is `position: absolute` within `.paragraph`; we set its top in
// px relative to the paragraph. CSS default (top:50%) is the JS-off
// fallback — the first frame of scroll handler replaces it.
if (document.body.classList.contains('doc-laudato_si')) {
  const paragraphs = Array.from(document.querySelectorAll('.paragraph'));
  let raf = 0;

  // Cache the num height once — every digit renders the same height for
  // a given font/size, so we only need to measure one.
  let cachedNumH = 0;

  function placeNums() {
    raf = 0;
    // Mobile: CSS reverts to inline bold prefix; clear any inline styles
    // we may have set from a previous (wider) layout and bail.
    if (window.innerWidth <= 700) {
      for (const para of paragraphs) {
        const num = para.querySelector('.para-num');
        if (num && num.style.top) {
          num.style.top = '';
          num.style.transform = '';
        }
      }
      return;
    }
    const barH = stickyBar.offsetHeight;
    const vh   = window.innerHeight;
    const topAnchor = barH + 6;
    const centerY   = barH + (vh - barH) / 2;

    // Two-pass: read all rects first, then write all styles. Interleaving
    // reads and writes forces a layout flush per paragraph (~246 times).
    const updates = [];
    for (const para of paragraphs) {
      const rect = para.getBoundingClientRect();
      if (rect.bottom < -50 || rect.top > vh + 50) {
        updates.push(null);   // off-screen marker
      } else {
        updates.push(rect);
      }
    }
    if (!cachedNumH) {
      const visible = paragraphs.find((_, i) => updates[i]);
      cachedNumH = visible ? visible.querySelector('.para-num').offsetHeight : 16;
    }
    const halfNum = cachedNumH / 2;

    for (let i = 0; i < paragraphs.length; i++) {
      const num = paragraphs[i].querySelector('.para-num');
      if (!num) continue;
      const rect = updates[i];
      if (!rect) {
        if (num.style.top) { num.style.top = ''; num.style.transform = ''; }
        continue;
      }
      const paraTop = rect.top;
      const paraBottom = rect.bottom;

      // Where the number's CENTRE wants to be in viewport coords
      let anchor;
      if (paraTop >= centerY) {
        anchor = paraTop + halfNum;                          // phase A
      } else if (paraTop >= topAnchor) {
        const t = (centerY - paraTop) / (centerY - topAnchor); // 0 → 1
        anchor = centerY * (1 - t) + (topAnchor + halfNum) * t;  // phase B
      } else {
        anchor = topAnchor + halfNum;                        // phase C
      }
      anchor = Math.max(paraTop + halfNum, Math.min(anchor, paraBottom - halfNum));

      num.style.top = (anchor - paraTop) + 'px';
      num.style.transform = 'translateY(-50%)';
    }
  }

  function schedule() {
    if (!raf) raf = requestAnimationFrame(placeNums);
  }
  window.addEventListener('scroll', schedule, {passive: true});
  window.addEventListener('resize', schedule);
  placeNums();
}

// ── footnote drawer ──
const drawer  = document.getElementById('fn-drawer');
const tab     = document.getElementById('fn-tab');
const content = document.getElementById('fn-content');

tab.addEventListener('click', () => drawer.classList.toggle('open'));

function selectFn(id) {
  document.querySelectorAll('.fn-item.fn-active')
    .forEach(el => el.classList.remove('fn-active'));
  const target = document.getElementById(id);
  if (!target) return;
  target.classList.add('fn-active');
  const rect = target.getBoundingClientRect();
  const cRect = content.getBoundingClientRect();
  if (rect.top < cRect.top || rect.bottom > cRect.bottom) {
    content.scrollTop += rect.top - cRect.top - content.clientHeight / 3;
  }
}

document.querySelectorAll('.fn-ch-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const target = document.getElementById(a.getAttribute('href').slice(1));
    if (target) scrollToEl(target, true);
  });
});

document.querySelectorAll('.fn-num-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const target = document.getElementById(a.getAttribute('href').slice(1));
    if (target) scrollToEl(target, true);
  });
});

document.querySelectorAll('.sec-nav-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const target = document.getElementById(a.getAttribute('href').slice(1));
    if (target) scrollToEl(target, true);
  });
});

document.querySelectorAll('sup a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    drawer.classList.add('open');
    selectFn(a.getAttribute('href').slice(1));
  });
});

// ── reader prefs ──
// Theme + paragraph size, written as data-attributes on <html> so the CSS
// variants under :root pick them up. Persisted in localStorage under one key.
// The aA button in the sticky bar toggles the panel.
(function () {
  const root  = document.documentElement;
  const KEY   = 'va_reader_prefs';
  const trig  = document.getElementById('action-prefs');
  const panel = document.getElementById('prefs-panel');
  if (!trig || !panel) return;   // safety net if the markup ever disappears

  let prefs = {};
  try { prefs = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}

  function apply() {
    if (prefs.theme) root.dataset.theme = prefs.theme;
    if (prefs.size)  root.dataset.size  = prefs.size;
    panel.querySelectorAll('button[data-pref]').forEach(b => {
      b.classList.toggle('active', prefs[b.dataset.pref] === b.dataset.value);
    });
  }

  panel.querySelectorAll('button[data-pref]').forEach(b => {
    b.addEventListener('click', () => {
      prefs[b.dataset.pref] = b.dataset.value;
      localStorage.setItem(KEY, JSON.stringify(prefs));
      apply();
    });
  });

  trig.addEventListener('click', e => {
    e.stopPropagation();
    panel.hidden = !panel.hidden;
  });
  document.addEventListener('click', e => {
    if (!panel.hidden && !panel.contains(e.target) && !trig.contains(e.target)) {
      panel.hidden = true;
    }
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !panel.hidden) panel.hidden = true;
  });

  apply();
})();
