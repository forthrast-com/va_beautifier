// ─────────────────────────────────────────────────────────────────────────
// Vatican-document reader scripts.
//
// Loaded + inlined by make_html.py with two substitutions:
//   __INDICATOR_JSON__   the JSON array of chapter descriptors for the indicator
//   __DOC_SLUG__         the JSON-encoded document slug (e.g. "laudato_si")
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
const stickyContextEls = Array.from(
  document.querySelectorAll('[data-sticky], .section-title')
);
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
    if (document.body.classList.contains('layout-long')) {
      // The indicator anticipates the next paragraph at 35% of the viewport,
      // but the bar should not: change its context only when the authored
      // section heading reaches the top of the readable area. A new chapter,
      // part, or appendix clears the previous section context.
      const barEdge = document.getElementById('sticky-bar').offsetHeight + 8;
      let currentSub = '';
      for (const el of stickyContextEls) {
        if (el.getBoundingClientRect().top > barEdge) break;
        currentSub = el.matches('.section-title') ? el.textContent : '';
      }
      stickySub.textContent = currentSub;
    } else {
      const para = currentParaNum
        ? document.getElementById('para-' + currentParaNum)
        : null;
      stickySub.textContent = para?.dataset?.subText || '';
    }
  } else {
    // Top of doc / no chapter context — leave the bar blank.
    // The permanent doc-title-corner element handles "where am I".
    stickyLabel.textContent = '';
    stickyNum.textContent   = '';
    stickySub.textContent   = '';
  }
}

// ── screen-reader announcements ──
// One polite live region for state changes that otherwise happen silently
// (bookmarks, reader prefs). Clear-then-set so repeating the same message
// still fires an announcement.
const srStatus = document.getElementById('sr-status');
let srTimer = 0;
function announce(msg) {
  srStatus.textContent = '';
  clearTimeout(srTimer);
  srTimer = setTimeout(() => { srStatus.textContent = msg; }, 50);
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
    // Sub-heading notches: tick marks at each sub start (visible only on
    // the active bar) plus the split-lane current marker — a full-height
    // stripe on the left two-thirds for "this section", a band sliding
    // notch-to-notch on the right third for "this sub". Each notch carries
    // its sub anchor so clicks on the active bar land interval-precise.
    if (s.notches && s.notches.length) {
      s.notches.forEach(n => {
        const notch = document.createElement('i');
        notch.className = 'ch-notch';
        notch.style.top = (n.f * 100) + '%';
        seg.appendChild(notch);
      });
      seg._bounds = [0, ...s.notches.map(n => n.f), 1];
      seg._targets = [s.target, ...s.notches.map(n => n.target)];
      seg._edge = document.createElement('i');
      seg._edge.className = 'ch-curedge';
      seg._band = document.createElement('i');
      seg._band.className = 'ch-curband';
      seg.append(seg._edge, seg._band);
    }
    seg.addEventListener('click', e => {
      e.stopPropagation();
      let target = s.target;
      // On the active (widened) bar the notch grid is visible, so honour
      // it: route the click to the sub-interval it landed in. Idle bars
      // keep section-level targets — you can't aim at what you can't see.
      if (seg._bounds && bar.classList.contains('active')) {
        const rect = seg.getBoundingClientRect();
        const lf = (e.clientY - rect.top) / rect.height;
        let j = 0;
        while (j < seg._bounds.length - 2 && lf >= seg._bounds[j + 1]) j++;
        target = seg._targets[j];
      }
      scrollToEl(document.getElementById(target), true);
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
  // Duplicate paragraph numbers mint ids like `para-5-2`; fall back to the
  // numeric prefix so the lookup still lands in the right chapter.
  const chIdx = paraToChIdx[curPara] ?? paraToChIdx[parseInt(curPara)] ?? 0;
  const activePart = chapters[chIdx]?.part;
  bars.forEach((b, i) => {
    const isActive = i === chIdx;
    b.classList.toggle('active', isActive);
    b.classList.toggle('part-active', !isActive && chapters[i].part === activePart);
    // Fisheye: the active bar takes ~1.8× its proportional height so its
    // segs (and notches) get real room; the others compress to make way.
    // flex-grow interpolates, so the CSS transition animates the shift.
    b.style.flexGrow = (chapters[i].paras.length || 1) * (isActive ? 1.8 : 1);
    const cp = parseInt(curPara);
    b.querySelectorAll('.ch-seg').forEach(s => {
      const selected = s.dataset.key
        ? s.dataset.key === curPara
        : cp >= parseInt(s.dataset.first) && cp <= parseInt(s.dataset.last);
      if (s._bounds) {
        // Notched seg: the split-lane marker replaces whole-seg cur-para.
        const on = isActive && selected;
        s._edge.classList.toggle('on', on);
        s._band.classList.toggle('on', on);
        if (on) {
          const first = parseInt(s.dataset.first);
          const span = parseInt(s.dataset.last) - first + 1;
          const lf = (cp - first) / span;
          const bounds = s._bounds;
          let j = 0;
          while (j < bounds.length - 2 && lf >= bounds[j + 1]) j++;
          s._band.style.top = (bounds[j] * 100) + '%';
          s._band.style.height = ((bounds[j + 1] - bounds[j]) * 100) + '%';
        }
      } else {
        s.classList.toggle('cur-para', isActive && selected);
      }
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
// Masthead convention: clicking the corner title re-homes to the top of the
// document and clears the hash. Mouse-only (the element is aria-hidden and
// unfocusable); keyboard users have the skip link and the Home key.
docTitleCorner.addEventListener('click', () => {
  window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'instant' : 'smooth' });
  history.replaceState(null, '', location.pathname);
});

publishBarH();
publishTitleClearance();
if ('ResizeObserver' in window) {
  new ResizeObserver(publishTitleClearance).observe(docTitleCorner);
}
window.addEventListener('resize', () => {
  publishBarH();
  publishTitleClearance();
});

// ── Long documents: pin only the current paragraph number ──
// Every number normally sits beside its paragraph's first line. Once that
// paragraph scrolls under the sticky bar, its number alone stays pinned until
// the paragraph bottom carries it away. Following numbers remain in ordinary
// document flow — no pre-emptive sliding or multi-number choreography.
if (document.body.classList.contains('layout-long')) {
  const paragraphs = Array.from(document.querySelectorAll('.paragraph'));
  let activeNum = null;
  let raf = 0;

  function clearNumState(num) {
    if (!num) return;
    num.classList.remove('para-num-pinned', 'para-num-at-bottom');
    num.style.left = '';
    num.style.width = '';
  }

  function pinNum(num) {
    if (num.classList.contains('para-num-pinned')) return;
    const rect = num.getBoundingClientRect();
    num.classList.remove('para-num-at-bottom');
    num.style.left = rect.left + 'px';
    num.style.width = rect.width + 'px';
    num.classList.add('para-num-pinned');
  }

  function updateActiveNum() {
    raf = 0;
    if (window.innerWidth <= 900) {
      clearNumState(activeNum);
      activeNum = null;
      return;
    }

    const anchorY = stickyBar.offsetHeight + 6;
    let activePara = null;
    let activeRect = null;

    for (const para of paragraphs) {
      const rect = para.getBoundingClientRect();
      if (rect.top > anchorY) break;
      if (rect.bottom > anchorY) {
        activePara = para;
        activeRect = rect;
      }
    }

    const nextNum = activePara && activePara.querySelector('.para-num');
    if (activeNum !== nextNum) clearNumState(activeNum);
    activeNum = nextNum;
    if (!activeNum) return;

    if (activeRect.bottom <= anchorY + activeNum.offsetHeight) {
      activeNum.classList.remove('para-num-pinned');
      activeNum.classList.add('para-num-at-bottom');
      activeNum.style.left = '';
      activeNum.style.width = '';
    } else {
      pinNum(activeNum);
    }
  }

  function scheduleActiveNum() {
    if (!raf) raf = requestAnimationFrame(updateActiveNum);
  }
  function resetActiveNum() {
    clearNumState(activeNum);
    activeNum = null;
    scheduleActiveNum();
  }
  window.addEventListener('scroll', scheduleActiveNum, {passive: true});
  window.addEventListener('resize', resetActiveNum);
  updateActiveNum();
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
// Keyed by document slug so bookmarks survive layout-flag changes (the old
// key used body.className, which shifts whenever a layout class is added).
const BOOKMARK_KEY = 'va_reader_bookmarks:' + __DOC_SLUG__;
let bookmarks = [];
try {
  const legacy = localStorage.getItem('va_reader_bookmarks:' + document.body.className);
  const stored = JSON.parse(localStorage.getItem(BOOKMARK_KEY) || legacy || '[]');
  if (Array.isArray(stored)) bookmarks = stored.filter(id => tocByTarget.has(id));
} catch (e) {}

// Whichever element opened the drawer (the toggle or an in-text footnote
// ref) gets focus back when Escape closes it.
let drawerOpener = null;

function setDrawerOpen(open, opener) {
  drawer.classList.toggle('open', open);
  tab.setAttribute('aria-expanded', String(open));
  drawerOpener = open ? (opener || tab) : null;
}

tab.addEventListener('click', () => {
  const opening = !drawer.classList.contains('open');
  setDrawerOpen(opening);
  // Keyboard users shouldn't have to traverse half the document to reach
  // the panel they just opened: focus lands on the active view tab.
  if (opening) {
    const activeTab = drawerTabs.find(b => b.classList.contains('active'));
    (activeTab || drawerTabs[0]).focus();
  }
});

document.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || !drawer.classList.contains('open')) return;
  const opener = drawerOpener;
  setDrawerOpen(false);
  if (opener) opener.focus();
});

let textTapStart = null;
document.addEventListener('pointerdown', e => {
  if (e.pointerType !== 'touch' || !drawer.classList.contains('open')) return;
  if (!e.target.closest('.paragraph, .doc-title, .appendix, .doc-end-matter')) return;
  if (e.target.closest('a, button, input, summary')) return;
  textTapStart = {id: e.pointerId, x: e.clientX, y: e.clientY};
});
document.addEventListener('pointerup', e => {
  if (!textTapStart || e.pointerId !== textTapStart.id) return;
  const moved = Math.hypot(e.clientX - textTapStart.x, e.clientY - textTapStart.y);
  textTapStart = null;
  if (e.pointerType === 'touch' && moved < 10) setDrawerOpen(false);
});
document.addEventListener('pointercancel', () => {
  textTapStart = null;
});

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
  const removing = bookmarks.includes(target);
  if (removing) {
    bookmarks = bookmarks.filter(id => id !== target);
  } else {
    bookmarks.push(target);
  }
  saveBookmarks();
  renderBookmarks();
  const label = tocByTarget.get(target)?.dataset.label || '';
  announce(removing ? `Bookmark removed: ${label}` : `Bookmarked: ${label}`);
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
  // Contents and footnotes views share heading targets, so a toggle in
  // either panel reflects (and flips) the same saved state.
  document.querySelectorAll(
    '#drawer-toc .bookmark-toggle, #drawer-footnotes .bookmark-toggle'
  ).forEach(button => {
    const saved = bookmarks.includes(button.dataset.bookmarkTarget);
    button.classList.toggle('saved', saved);
    button.setAttribute('aria-pressed', saved ? 'true' : 'false');
  });
}

document.querySelectorAll(
  '#drawer-toc .bookmark-toggle, #drawer-footnotes .bookmark-toggle'
).forEach(wireBookmarkButton);
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
    const divisor = window.matchMedia('(max-width: 900px)').matches ? 4.5 : 3;
    notesPanel.scrollTop += rect.top - cRect.top - notesPanel.clientHeight / divisor;
  }
  // Move focus to the note so SR/keyboard users land on what they asked
  // for; preventScroll keeps the panel maths above authoritative.
  target.setAttribute('tabindex', '-1');
  target.focus({preventScroll: true});
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
    setDrawerOpen(true, a);
    showDrawerView('footnotes');
    selectFn(a.getAttribute('href').slice(1));
  });
});

const home = document.getElementById('action-home');
if (home) home.addEventListener('click', () => window.location.assign('index.html'));

// ── corner panels: shared open/close plumbing ──
// Both popovers sync their trigger's aria-expanded, close on outside click
// or Escape (returning focus to the trigger when focus was inside), and
// move focus into the panel on open — the panel itself when it's prose
// (info, tabindex="-1"), else its first control.
function setPanelOpen(trig, panel, open) {
  panel.hidden = !open;
  trig.setAttribute('aria-expanded', String(open));
}

function wirePanel(trig, panel, closeOther) {
  trig.addEventListener('click', e => {
    e.stopPropagation();
    const opening = panel.hidden;
    setPanelOpen(trig, panel, opening);
    if (opening) {
      closeOther();
      const focusTarget = panel.matches('[tabindex]')
        ? panel
        : (panel.querySelector('button, a') || panel);
      focusTarget.focus();
    }
  });
  document.addEventListener('click', e => {
    if (!panel.hidden && !panel.contains(e.target) && !trig.contains(e.target)) {
      setPanelOpen(trig, panel, false);
    }
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !panel.hidden) {
      const inside = panel.contains(document.activeElement);
      setPanelOpen(trig, panel, false);
      if (inside) trig.focus();
    }
  });
}

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
      const active = expected === actual;
      b.classList.toggle('active', active);
      b.setAttribute('aria-pressed', String(active));
    });
  }

  panel.querySelectorAll('button[data-pref]').forEach(b => {
    b.addEventListener('click', () => {
      prefs[b.dataset.pref] = b.dataset.value;
      localStorage.setItem(KEY, JSON.stringify(prefs));
      apply();
      announce(`${b.dataset.pref} set to ${b.dataset.value}`);
    });
  });

  wirePanel(trig, panel, () => info && setPanelOpen(
    document.getElementById('action-info'), info, false
  ));

  apply();
})();

// ── edition information ──
(function () {
  const trig  = document.getElementById('action-info');
  const panel = document.getElementById('info-panel');
  const prefs = document.getElementById('prefs-panel');
  if (!trig || !panel) return;

  wirePanel(trig, panel, () => prefs && setPanelOpen(
    document.getElementById('action-prefs'), prefs, false
  ));
})();
