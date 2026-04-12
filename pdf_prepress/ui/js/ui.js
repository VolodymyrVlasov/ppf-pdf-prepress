/**
 * ui.js — DOM interactions: tabs, warp preview drawing, hover effects.
 * No Python API calls here — those live in api.js / main.js.
 */

// ── Tab switcher ──────────────────────────────────────────────────────────

const Tabs = (() => {
  function init() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => activate(btn));
    });
    // Activate the first tab in each group automatically
    document.querySelectorAll('.tab-bar').forEach(bar => {
      const first = bar.querySelector('.tab-btn.active') || bar.querySelector('.tab-btn');
      if (first) activate(first);
    });
  }

  function activate(clickedBtn) {
    const bar = clickedBtn.closest('.tab-bar');
    if (!bar) return;
    const tabId = clickedBtn.dataset.tab;

    // Update button states within this bar
    bar.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    clickedBtn.classList.add('active');

    // Show the matching content panel, hide others
    // Content panels are siblings of the tab-bar's parent (the card)
    const card = bar.closest('.card, .settings-card');
    if (!card) return;
    card.querySelectorAll('.tab-content').forEach(panel => {
      panel.classList.toggle('active', panel.id === tabId);
    });
  }

  return { init, activate };
})();


// ── Warp preview (SVG) ────────────────────────────────────────────────────

const WarpPreview = (() => {
  const PAGE_W = 100;
  const PAGE_H = 141;

  const SVG_NS = 'http://www.w3.org/2000/svg';

  function _cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  const COLOR_ORIGINAL = () => _cssVar('--color-warp-original') || '#AAAAAA';
  const COLOR_FRONT    = () => _cssVar('--color-warp-front')    || '#2979FF';
  const COLOR_BACK     = () => _cssVar('--color-warp-back')     || '#FF6D00';
  const COLOR_DISABLED = () => _cssVar('--color-warp-disabled') || '#909090';

  /**
   * Describes one preview instance.
   * @typedef {{ svg: SVGElement, inputs: Object<string, HTMLInputElement[]>, color: string, disabled: boolean }} Preview
   */

  const _previews = {};

  /**
   * Register a preview.
   * @param {string}       id     - Unique key (e.g. 'front' / 'back')
   * @param {SVGElement}   svg    - The <svg> element
   * @param {object}       inputs - { tl: [xEl, yEl], tr: [...], bl: [...], br: [...] }
   * @param {string}       color  - Stroke color for warped quad
   */
  function register(id, svg, inputs, color) {
    // Normalize: accept a hex string or a function that returns the color
    const colorFn = typeof color === 'function' ? color : () => color;
    _previews[id] = { svg, inputs, color: colorFn, disabled: false };

    // Redraw on any input change
    Object.values(inputs).forEach(([xEl, yEl]) => {
      xEl.addEventListener('input', () => draw(id));
      yEl.addEventListener('input', () => draw(id));
    });

    // Redraw on resize (ResizeObserver is more reliable than window resize for SVG)
    const ro = new ResizeObserver(() => draw(id));
    ro.observe(svg);

    draw(id);
  }

  function setDisabled(id, disabled) {
    if (_previews[id]) {
      _previews[id].disabled = disabled;
      draw(id);
    }
  }

  function draw(id) {
    const p = _previews[id];
    if (!p) return;

    const svg = p.svg;
    // Clear
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const W = svg.clientWidth  || svg.getBoundingClientRect().width  || 120;
    const H = svg.clientHeight || svg.getBoundingClientRect().height || 160;
    if (W < 10 || H < 10) return;

    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

    const margin = 14;
    const scaleX = (W - margin * 2) / PAGE_W;
    const scaleY = (H - margin * 2) / PAGE_H;
    const scale  = Math.min(Math.max(scaleX, 0.2), Math.min(scaleY, 2.5));

    const cx = W / 2;
    const cy = H / 2;
    const hw = PAGE_W * scale / 2;
    const hh = PAGE_H * scale / 2;

    const orig = {
      tl: [cx - hw, cy - hh],
      tr: [cx + hw, cy - hh],
      br: [cx + hw, cy + hh],
      bl: [cx - hw, cy + hh],
    };
    const order = ['tl', 'tr', 'br', 'bl'];

    // Dashed original rectangle
    const dashed = document.createElementNS(SVG_NS, 'polygon');
    dashed.setAttribute('points', order.map(k => orig[k].join(',')).join(' '));
    dashed.setAttribute('fill', 'none');
    dashed.setAttribute('stroke', COLOR_ORIGINAL());
    dashed.setAttribute('stroke-width', '1');
    dashed.setAttribute('stroke-dasharray', '5,4');
    svg.appendChild(dashed);

    // Parse corner offsets
    const offsets = {};
    for (const key of order) {
      const [xEl, yEl] = p.inputs[key];
      const x = parseFloat((xEl.value || '0').replace(',', '.'));
      const y = parseFloat((yEl.value || '0').replace(',', '.'));
      if (isNaN(x) || isNaN(y)) return; // invalid input — don't draw
      offsets[key] = [x, y];
    }

    const color = p.disabled ? COLOR_DISABLED() : p.color();

    // Warped quad
    const warped = {};
    for (const key of order) {
      warped[key] = [
        orig[key][0] + offsets[key][0] * scale,
        orig[key][1] + offsets[key][1] * scale,
      ];
    }

    const poly = document.createElementNS(SVG_NS, 'polygon');
    poly.setAttribute('points', order.map(k => warped[k].join(',')).join(' '));
    poly.setAttribute('fill', 'none');
    poly.setAttribute('stroke', color);
    poly.setAttribute('stroke-width', '2');
    svg.appendChild(poly);

    // Corner dots
    const R = 4;
    for (const key of order) {
      const [px, py] = warped[key];
      const dot = document.createElementNS(SVG_NS, 'circle');
      dot.setAttribute('cx', px);
      dot.setAttribute('cy', py);
      dot.setAttribute('r', R);
      dot.setAttribute('fill', color);
      svg.appendChild(dot);
    }
  }

  function redrawAll() {
    Object.keys(_previews).forEach(draw);
  }

  return { register, setDisabled, draw, redrawAll };
})();


// ── File list manager ────────────────────────────────────────────────────

const FileList = (() => {
  const _paths = [];
  let _select  = null;

  function init(selectEl) {
    _select = selectEl;
    _render();
  }

  function add(paths) {
    let added = false;
    for (const p of paths) {
      if (!_paths.includes(p)) { _paths.push(p); added = true; }
    }
    if (added) _render(_paths.length - 1);
  }

  function current() {
    if (!_select || !_paths.length) return null;
    const idx = _select.selectedIndex;
    return (idx >= 0 && idx < _paths.length) ? _paths[idx] : null;
  }

  function _render(selectIdx) {
    if (!_select) return;
    // Save current selection
    const prevIdx = _select.selectedIndex;
    _select.innerHTML = '';
    if (!_paths.length) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = '— файли не обрано —';
      _select.appendChild(opt);
      return;
    }
    _paths.forEach((p, i) => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = `${i + 1}. ${p.split(/[\\/]/).pop()}`;
      _select.appendChild(opt);
    });
    const idx = selectIdx !== undefined ? selectIdx : prevIdx;
    _select.selectedIndex = Math.min(Math.max(idx, 0), _paths.length - 1);
  }

  function lastFolder() {
    const c = current();
    if (!c) return null;
    const parts = c.replace(/\\/g, '/').split('/');
    parts.pop();
    return parts.join('/') || null;
  }

  return { init, add, current, lastFolder };
})();


// ── Progress / status helpers ─────────────────────────────────────────────

const Progress = (() => {
  let _bar    = null;
  let _status = null;
  let _counter= null;
  let _spinner= null;

  function init(barEl, statusEl, counterEl, spinnerEl) {
    _bar     = barEl;
    _status  = statusEl;
    _counter = counterEl;
    _spinner = spinnerEl;
  }

  function show(text) {
    if (_bar)    _bar.classList.remove('hidden');
    if (_status) { _status.textContent = text; _status.style.color = ''; }
    if (_counter) _counter.textContent = 'Сторінка 0 / ?';
  }

  function update(page, total) {
    if (_counter) _counter.textContent = `Сторінка ${page} / ${total}`;
  }

  function updateText(text) {
    if (_status) _status.textContent = text;
  }

  function hide() {
    if (_bar) _bar.classList.add('hidden');
  }

  function setSuccess(text) {
    if (_status) {
      _status.textContent = text;
      _status.style.color = 'var(--color-btn-launch)';
    }
  }

  function setError(text) {
    if (_status) {
      _status.textContent = text;
      _status.style.color = 'var(--color-btn-stop)';
    }
  }

  return { init, show, hide, update, updateText, setSuccess, setError };
})();


// ── Status bar ────────────────────────────────────────────────────────────

const StatusBar = (() => {
  let _el = null;
  function init(el) { _el = el; }
  function set(text)  { if (_el) _el.textContent = `  ${text}`; }
  function clear()    { if (_el) _el.textContent = ''; }
  return { init, set, clear };
})();
