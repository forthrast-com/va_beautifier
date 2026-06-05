// ─────────────────────────────────────────────────────────────────────────
// Vatican-document reader scripts.
//
// Loaded + inlined by make_html.py with two substitutions:
//   __INDICATOR_JSON__   the JSON array of chapter descriptors for the indicator
//   __DOC_NAME__         the JSON-encoded display name (e.g. "Laudato Si'")
// ─────────────────────────────────────────────────────────────────────────

// Honour the OS-level "reduce motion" preference. Sampled once at boot —
// the rare reader who toggles mid-session can reload. Used by scrollToEl
// to flip smooth scrolls to instant; CSS transitions are caught by the
// matching @media block in styles.css.
const prefersReducedMotion =
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── sticky heading bar ──
const stickyNum   = document.getElementById('sticky-num');
const stickyLabel = document.getElementById('sticky-label');
const stickySub   = document.getElementById('sticky-sub');
const stickyEls   = Array.from(document.querySelectorAll('[data-sticky]'));
let currentParaNum = '';
function updateSticky() {
  let current = null;
  for (const el of stickyEls) {
    if (el.getBoundingClientRect().top < 40) current = el;
    else break;
  }
  if (current) {
    stickyLabel.textContent = current.textContent;
    stickyNum.textContent   = current.dataset.chNum || '';
    const para = currentParaNum ? document.getElementById('para-' + currentParaNum) : null;
    stickySub.textContent = para?.dataset?.subText || '';
  } else {
    // Top of doc / no chapter context — leave the bar blank.
    // The permanent doc-title-corner element handles "where am I".
    stickyLabel.textContent = '';
    stickyNum.textContent   = '';
    stickySub.textContent   = '';
  }
}

function scrollToEl(el, smooth) {
  const barH = document.getElementById('sticky-bar').offsetHeight;
  const top = el.getBoundingClientRect().top + window.scrollY - barH - 8;
  const behavior = (smooth && !prefersReducedMotion) ? 'smooth' : 'instant';
  window.scrollTo({ top, behavior });
  if (el.id) history.replaceState(null, '', '#' + el.id);
}

// ── chapter indicator ──
const chapters = __INDICATOR_JSON__;
const nav = document.getElementById('ch-indicator');

// build bars (skip spacer entries for bar array, but insert gap divs).
// Each segment identifies either a numbered paragraph range (`first`/`last`)
// or an appended reading region (`key`), such as a closing prayer.
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
  // no-op when bar height is summed from fixed-height segs (GeS). Use
  // total para count (not seg count) so a 60-para chapter with 3 sections
  // still gets a taller bar than a 16-para preface with 1 seg.
  bar.style.flexGrow = ch.paras.length || 1;
  ch.segs.forEach(s => {
    const seg = document.createElement('div');
    seg.className = 'ch-seg';
    if (s.key) {
      seg.dataset.key = s.key;
    } else {
      seg.dataset.first = s.first;
      seg.dataset.last  = s.last;
    }
    seg.title = s.label;
    seg.addEventListener('click', e => {
      e.stopPropagation();
      scrollToEl(document.getElementById(s.target), true);
    });
    bar.appendChild(seg);
  });
  bar.addEventListener('click', () =>
    scrollToEl(document.getElementById(ch.id), true)
  );
  nav.appendChild(bar);
  bars.push(bar);
});

// reading-region key → indicator bar index lookup
const paraToChIdx = {};
chapters.forEach((ch, i) => ch.paras.forEach(pn => paraToChIdx[pn] = i));

// Collect numbered paragraphs and non-paragraph appendices in reading order.
const paraEls = Array.from(document.querySelectorAll('.paragraph, .appendix'));
function readingKey(el) {
  return el.classList.contains('appendix') ? el.id : el.id.replace('para-', '');
}

function updateIndicator() {
  const threshold = window.innerHeight * 0.35;
  let curPara = paraEls[0] ? readingKey(paraEls[0]) : '';
  for (const el of paraEls) {
    if (el.getBoundingClientRect().top <= threshold) curPara = readingKey(el);
    else break;
  }
  currentParaNum = curPara || '';
  const chIdx = paraToChIdx[curPara] ?? 0;
  const activePart = chapters[chIdx]?.part;
  bars.forEach((b, i) => {
    const isActive = i === chIdx;
    b.classList.toggle('active', isActive);
    b.classList.toggle('part-active', !isActive && chapters[i].part === activePart);
    const cp = parseInt(curPara);
    b.querySelectorAll('.ch-seg').forEach(s => {
      const selected = s.dataset.key
        ? s.dataset.key === curPara
        : cp >= parseInt(s.dataset.first) && cp <= parseInt(s.dataset.last);
      s.classList.toggle('cur-para', isActive && selected);
    });
  });
  updateSticky();
}
window.addEventListener('scroll', updateIndicator, {passive: true});
updateIndicator();

// ── publish sticky-bar height as a CSS var ──
// The indicator + (potential) other layout pieces read --bar-h so they
// can fit / centre inside the visible viewport instead of overlapping
// the sticky bar.
const stickyBar = document.getElementById('sticky-bar');
const docTitleCorner = document.getElementById('doc-title-corner');
function publishBarH() {
  document.documentElement.style.setProperty('--bar-h', stickyBar.offsetHeight + 'px');
}
function publishTitleClearance() {
  const titleRight = docTitleCorner.getBoundingClientRect().right;
  document.documentElement.style.setProperty('--title-clearance', titleRight + 16 + 'px');
}
publishBarH();
publishTitleClearance();
if ('ResizeObserver' in window) {
  new ResizeObserver(publishTitleClearance).observe(docTitleCorner);
}
window.addEventListener('resize', () => {
  publishBarH();
  publishTitleClearance();
});

// ── Long modern documents: soft-anchor paragraph numbers ──
// Three-phase trajectory as paragraph scrolls up through viewport:
//   A. paragraph below viewport centre -> number sits at top of paragraph
//   B. paragraph approaching top -> anchor lerps from viewport centre
//                                   down to (bar bottom + small offset)
//   C. paragraph past top -> number sticks just under the bar, clamped
//                            to paragraph bottom so it exits with the para
// Number is `position: absolute` within `.paragraph`; we set its top in
// px relative to the paragraph. CSS default (top:50%) is the JS-off
// fallback — the first frame of scroll handler replaces it.
if (document.body.classList.contains('doc-laudato_si') ||
    document.body.classList.contains('doc-magnifica_humanitas') ||
    document.body.classList.contains('doc-antiqua_et_nova') ||
    document.body.classList.contains('doc-quo_vadis_humanitas') ||
    document.body.classList.contains('doc-sacrosanctum_concilium')) {
  const paragraphs = Array.from(document.querySelectorAll('.paragraph'));
  let raf = 0;
  let cachedNumH = 0;   // every digit renders the same height for a given font/size

  function placeNums() {
    raf = 0;
    // Narrow layout: CSS reverts to inline bold prefix; clear any inline
    // styles we may have set from a previous (wider) layout and bail.
    if (window.innerWidth <= 900) {
      for (const para of paragraphs) {
        const num = para.querySelector('.para-num');
        if (num && num.style.top) { num.style.top = ''; num.style.transform = ''; }
      }
      return;
    }
    const barH = stickyBar.offsetHeight;
    const vh   = window.innerHeight;
    const topAnchor = barH + 6;
    const centerY   = barH + (vh - barH) / 2;

    // Two-pass: read all rects, then write all styles — interleaving forces
    // a layout flush per paragraph (~246 of them in LS).
    const updates = [];
    for (const para of paragraphs) {
      const rect = para.getBoundingClientRect();
      updates.push((rect.bottom < -50 || rect.top > vh + 50) ? null : rect);
    }
    if (!cachedNumH) {
      const visiblePara = paragraphs.find((para, i) =>
        updates[i] && para.querySelector('.para-num')
      );
      cachedNumH = visiblePara ? visiblePara.querySelector('.para-num').offsetHeight : 16;
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
      const paraTop = rect.top, paraBottom = rect.bottom;
      let anchor;
      if (paraTop >= centerY) {
        anchor = paraTop + halfNum;                          // phase A
      } else if (paraTop >= topAnchor) {
        const t = (centerY - paraTop) / (centerY - topAnchor);
        anchor = centerY * (1 - t) + (topAnchor + halfNum) * t;  // phase B
      } else {
        anchor = topAnchor + halfNum;                        // phase C
      }
      anchor = Math.max(paraTop + halfNum, Math.min(anchor, paraBottom - halfNum));
      num.style.top = (anchor - paraTop) + 'px';
      num.style.transform = 'translateY(-50%)';
    }
  }

  function schedule() { if (!raf) raf = requestAnimationFrame(placeNums); }
  window.addEventListener('scroll', schedule, {passive: true});
  window.addEventListener('resize', schedule);
  placeNums();
}

// ── footnote drawer ──
const drawer  = document.getElementById('fn-drawer');
const tab     = document.getElementById('fn-tab');
const drawerTabs = Array.from(document.querySelectorAll('.drawer-view-tab'));
const drawerViews = Array.from(document.querySelectorAll('.drawer-view'));
const notesPanel = document.getElementById('drawer-footnotes');
const bookmarkList = document.getElementById('bookmark-list');
const bookmarksEmpty = document.querySelector('.bookmarks-empty');
const tocItems = Array.from(document.querySelectorAll('#drawer-toc .toc-item'));
const tocByTarget = new Map(tocItems.map(item => [item.dataset.target, item]));
const BOOKMARK_KEY = 'va_reader_bookmarks:' + document.body.className;
let bookmarks = [];
try {
  const stored = JSON.parse(localStorage.getItem(BOOKMARK_KEY) || '[]');
  if (Array.isArray(stored)) bookmarks = stored.filter(id => tocByTarget.has(id));
} catch (e) {}

tab.addEventListener('click', () => drawer.classList.toggle('open'));

function showDrawerView(view) {
  drawerTabs.forEach(button => {
    const active = button.dataset.drawerView === view;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  drawerViews.forEach(panel => {
    const active = panel.id === 'drawer-' + view;
    panel.hidden = !active;
    panel.classList.toggle('active', active);
  });
}

drawerTabs.forEach(button => {
  button.addEventListener('click', () => showDrawerView(button.dataset.drawerView));
});

function followDrawerLink(a) {
  const target = document.getElementById(a.getAttribute('href').slice(1));
  if (target) scrollToEl(target, true);
}

function saveBookmarks() {
  localStorage.setItem(BOOKMARK_KEY, JSON.stringify(bookmarks));
}

function toggleBookmark(target) {
  if (bookmarks.includes(target)) {
    bookmarks = bookmarks.filter(id => id !== target);
  } else {
    bookmarks.push(target);
  }
  saveBookmarks();
  renderBookmarks();
}

function wireBookmarkButton(button) {
  button.addEventListener('click', e => {
    e.preventDefault();
    e.stopPropagation();
    toggleBookmark(button.dataset.bookmarkTarget);
  });
}

function renderBookmarks() {
  bookmarkList.replaceChildren();
  for (const target of bookmarks) {
    const source = tocByTarget.get(target);
    if (!source) continue;
    const item = source.cloneNode(true);
    const link = item.querySelector('a');
    const button = item.querySelector('.bookmark-toggle');
    button.classList.add('saved');
    button.setAttribute('aria-pressed', 'true');
    wireBookmarkButton(button);
    link.addEventListener('click', e => {
      e.preventDefault();
      followDrawerLink(link);
    });
    bookmarkList.appendChild(item);
  }
  bookmarksEmpty.hidden = bookmarks.length > 0;
  document.querySelectorAll('#drawer-toc .bookmark-toggle').forEach(button => {
    const saved = bookmarks.includes(button.dataset.bookmarkTarget);
    button.classList.toggle('saved', saved);
    button.setAttribute('aria-pressed', saved ? 'true' : 'false');
  });
}

tocItems.forEach(item => wireBookmarkButton(item.querySelector('.bookmark-toggle')));
renderBookmarks();

function selectFn(id) {
  document.querySelectorAll('.fn-item.fn-active')
    .forEach(el => el.classList.remove('fn-active'));
  const target = document.getElementById(id);
  if (!target) return;
  target.classList.add('fn-active');
  const rect = target.getBoundingClientRect();
  const cRect = notesPanel.getBoundingClientRect();
  if (rect.top < cRect.top || rect.bottom > cRect.bottom) {
    notesPanel.scrollTop += rect.top - cRect.top - notesPanel.clientHeight / 3;
  }
}

document.querySelectorAll('.fn-ch-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    followDrawerLink(a);
  });
});

document.querySelectorAll('.fn-num-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const target = document.getElementById(a.getAttribute('href').slice(1));
    if (target) scrollToEl(target, true);
  });
});

document.querySelectorAll('.sec-nav-link, .sub-nav-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    followDrawerLink(a);
  });
});

document.querySelectorAll('sup a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    drawer.classList.add('open');
    showDrawerView('footnotes');
    selectFn(a.getAttribute('href').slice(1));
  });
});

const home = document.getElementById('action-home');
if (home) home.addEventListener('click', () => window.location.assign('index.html'));

// ── reader prefs ──
// Theme + paragraph size, written as data-attributes on <html> so the CSS
// variants under :root pick them up. Persisted in localStorage under one key.
// The aA button in the sticky bar toggles the panel.
(function () {
  const root  = document.documentElement;
  const KEY   = 'va_reader_prefs';
  const trig  = document.getElementById('action-prefs');
  const panel = document.getElementById('prefs-panel');
  const info  = document.getElementById('info-panel');
  if (!trig || !panel) return;   // safety net if the markup ever disappears

  let prefs = {};
  try { prefs = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}

  function apply() {
    // Theme 'auto' (or unset) clears the attr so @media (prefers-color-scheme)
    // takes over. An explicit 'light'/'dark' overrides system.
    if (prefs.theme === 'light' || prefs.theme === 'dark') {
      root.dataset.theme = prefs.theme;
    } else {
      delete root.dataset.theme;
    }
    if (prefs.size) root.dataset.size = prefs.size;
    if (prefs.font) root.dataset.font = prefs.font;
    panel.querySelectorAll('button[data-pref]').forEach(b => {
      const expected = b.dataset.value;
      let actual = prefs[b.dataset.pref];
      if (b.dataset.pref === 'theme' && !actual) actual = 'auto';
      if (b.dataset.pref === 'font'  && !actual) actual = 'serif';
      if (b.dataset.pref === 'size'  && !actual) actual = 'medium';
      b.classList.toggle('active', expected === actual);
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
    if (!panel.hidden && info) info.hidden = true;
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

// ── edition information ──
(function () {
  const trig  = document.getElementById('action-info');
  const panel = document.getElementById('info-panel');
  const prefs = document.getElementById('prefs-panel');
  if (!trig || !panel) return;

  trig.addEventListener('click', e => {
    e.stopPropagation();
    panel.hidden = !panel.hidden;
    if (!panel.hidden && prefs) prefs.hidden = true;
  });
  document.addEventListener('click', e => {
    if (!panel.hidden && !panel.contains(e.target) && !trig.contains(e.target)) {
      panel.hidden = true;
    }
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !panel.hidden) panel.hidden = true;
  });
})();
