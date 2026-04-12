/**
 * main.js — App init, event listeners, app state.
 * Depends on: api.js, ui.js
 */

// ── App state ─────────────────────────────────────────────────────────────

const App = (() => {

  let _processing  = false;
  let _lastOutputFolder = '';
  let _iccSpaces   = [];   // [{csKey, label, settingsKey}, ...]
  let _autoOpen    = true;

  // ── Gather all form field references ──────────────────────────────────

  const el = {};

  function _refs() {
    el.fileSelect     = document.getElementById('file-select');
    el.btnAddFiles    = document.getElementById('btn-add-files');
    el.btnOpenFolder  = document.getElementById('btn-open-folder');
    el.radioSingle    = document.getElementById('radio-single');
    el.radioDouble    = document.getElementById('radio-double');
    el.dpiSelect      = document.getElementById('dpi-select');
    el.interpSelect   = document.getElementById('interp-select');
    el.comprSelect    = document.getElementById('compression-select');
    el.suffixCmyk     = document.getElementById('suffix-cmyk');
    el.suffixGray     = document.getElementById('suffix-gray');
    el.suffixRgb      = document.getElementById('suffix-rgb');
    el.iccUse         = document.getElementById('icc-use');
    el.iccGrid        = document.getElementById('icc-grid');
    el.modeSelect     = document.getElementById('mode-select');
    el.autoOpen       = document.getElementById('auto-open');
    el.btnRun         = document.getElementById('btn-run');
    el.progressBar    = document.getElementById('progress-bar');
    el.progressStatus = document.getElementById('progress-status');
    el.pageCounter    = document.getElementById('page-counter');
    el.spinner        = document.getElementById('spinner');
    el.statusLabel    = document.getElementById('status-label');
    el.backHint       = document.getElementById('back-hint');

    // Corner inputs: odd (FRONT)
    el.odd = {
      tl: [document.getElementById('odd-tl-x'), document.getElementById('odd-tl-y')],
      tr: [document.getElementById('odd-tr-x'), document.getElementById('odd-tr-y')],
      bl: [document.getElementById('odd-bl-x'), document.getElementById('odd-bl-y')],
      br: [document.getElementById('odd-br-x'), document.getElementById('odd-br-y')],
    };
    // Corner inputs: even (BACK)
    el.even = {
      tl: [document.getElementById('even-tl-x'), document.getElementById('even-tl-y')],
      tr: [document.getElementById('even-tr-x'), document.getElementById('even-tr-y')],
      bl: [document.getElementById('even-bl-x'), document.getElementById('even-bl-y')],
      br: [document.getElementById('even-br-x'), document.getElementById('even-br-y')],
    };
  }

  // ── Build dynamic content (modes, ICC rows) ───────────────────────────

  async function _buildModes() {
    const modes = await API.getModes();
    el.modeSelect.innerHTML = '';
    modes.forEach(({ display, key }) => {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = display;
      el.modeSelect.appendChild(opt);
    });
  }

  async function _buildIccRows() {
    _iccSpaces = await API.getIccSpaces();
    el.iccGrid.innerHTML = '';

    for (const { csKey, label, settingsKey } of _iccSpaces) {
      const profiles = await API.getProfiles(csKey);
      const hasProfiles = profiles && profiles.length > 0;

      // Label
      const lbl = document.createElement('span');
      lbl.className = 'icc-label';
      lbl.textContent = label;
      el.iccGrid.appendChild(lbl);

      // Select
      const sel = document.createElement('select');
      sel.className = 'select-field';
      sel.id = `icc-${csKey}`;
      sel.disabled = !hasProfiles;
      if (hasProfiles) {
        profiles.forEach(name => {
          const opt = document.createElement('option');
          opt.value = name;
          opt.textContent = name;
          sel.appendChild(opt);
        });
      } else {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = '— не знайдено —';
        sel.appendChild(opt);
      }
      el.iccGrid.appendChild(sel);

      // Refresh button
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm';
      btn.textContent = '⟳';
      btn.title = `Оновити список ${label}`;
      btn.addEventListener('click', () => _refreshIccDropdown(csKey));
      el.iccGrid.appendChild(btn);
    }

    _updateIccState();
  }

  async function _refreshIccDropdown(csKey) {
    const sel = document.getElementById(`icc-${csKey}`);
    if (!sel) return;
    const profiles = await API.getProfiles(csKey);
    const current  = sel.value;
    sel.innerHTML  = '';
    if (profiles && profiles.length) {
      profiles.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        sel.appendChild(opt);
      });
      sel.value = profiles.includes(current) ? current : profiles[0];
      sel.disabled = !el.iccUse.checked;
    } else {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = '— не знайдено —';
      sel.appendChild(opt);
      sel.disabled = true;
    }
  }

  function _updateIccState() {
    const enabled = el.iccUse.checked;
    _iccSpaces.forEach(({ csKey }) => {
      const sel = document.getElementById(`icc-${csKey}`);
      if (!sel) return;
      // Only enable if there are real profiles (not the placeholder)
      const hasProfiles = sel.options.length > 0 && sel.options[0].value !== '';
      if (sel) sel.disabled = !(enabled && hasProfiles);
    });
  }

  // ── Load settings into form ───────────────────────────────────────────

  async function _loadSettings() {
    const s = await API.getSettings();
    if (!s) return;

    // DPI
    if (s.dpi) {
      const opt = el.dpiSelect.querySelector(`option[value="${s.dpi}"]`);
      if (opt) el.dpiSelect.value = String(s.dpi);
    }

    // Interpolation
    if (s.interpolation) el.interpSelect.value = s.interpolation;

    // Compression
    if (s.compression) el.comprSelect.value = s.compression;

    // Suffixes
    if (s.output_suffix_cmyk) el.suffixCmyk.value = s.output_suffix_cmyk;
    if (s.output_suffix_gray) el.suffixGray.value = s.output_suffix_gray;
    if (s.output_suffix_rgb)  el.suffixRgb.value  = s.output_suffix_rgb;

    // Corners
    _fillCorners(el.odd,  s.odd_corners  || {});
    _fillCorners(el.even, s.even_corners || {});

    // ICC
    el.iccUse.checked = s.use_icc_profile !== false;
    for (const { csKey, settingsKey } of _iccSpaces) {
      const sel = document.getElementById(`icc-${csKey}`);
      if (!sel) continue;
      const saved = s[settingsKey];
      if (saved) {
        const opt = sel.querySelector(`option[value="${CSS.escape ? saved : saved}"]`);
        if (opt) sel.value = saved;
      }
    }
    _updateIccState();

    // Print mode
    const pm = s.print_mode || 'double';
    (pm === 'single' ? el.radioSingle : el.radioDouble).checked = true;
    _onPrintModeChange();

    // Auto open
    el.autoOpen.checked = s.auto_open_file !== false;
    _autoOpen = el.autoOpen.checked;

    // Last output folder
    _lastOutputFolder = s.last_output_folder || '';

    // Pre-load initial file from CLI argument
    if (s.initial_file) {
      FileList.add([s.initial_file]);
    }

    // Redraw previews after loading
    WarpPreview.redrawAll();
  }

  function _fillCorners(inputs, data) {
    const keys = ['tl', 'tr', 'bl', 'br'];
    keys.forEach(key => {
      const vals = data[key];
      if (!vals) return;
      inputs[key][0].value = String(vals[0] ?? 0);
      inputs[key][1].value = String(vals[1] ?? 0);
    });
  }

  // ── Read current form state ───────────────────────────────────────────

  function _readCorners(inputs) {
    const result = {};
    ['tl', 'tr', 'bl', 'br'].forEach(key => {
      const x = parseFloat((inputs[key][0].value || '0').replace(',', '.')) || 0;
      const y = parseFloat((inputs[key][1].value || '0').replace(',', '.')) || 0;
      result[key] = [x, y];
    });
    return result;
  }

  function _collectSettings() {
    const iccSelections = {};
    _iccSpaces.forEach(({ csKey, settingsKey }) => {
      const sel = document.getElementById(`icc-${csKey}`);
      iccSelections[settingsKey] = (sel && sel.value && sel.value !== '') ? sel.value : '';
    });

    return {
      dpi:                parseInt(el.dpiSelect.value, 10) || 300,
      odd_corners:        _readCorners(el.odd),
      even_corners:       _readCorners(el.even),
      output_suffix_cmyk: el.suffixCmyk.value || '_CMYK',
      output_suffix_gray: el.suffixGray.value || '_GRAY',
      output_suffix_rgb:  el.suffixRgb.value  || '_RGB',
      use_icc_profile:    el.iccUse.checked,
      print_mode:         el.radioSingle.checked ? 'single' : 'double',
      interpolation:      el.interpSelect.value || 'INTER_LANCZOS4',
      compression:        el.comprSelect.value  || 'tiff_lzw',
      auto_open_file:     el.autoOpen.checked,
      last_output_folder: _lastOutputFolder,
      ...iccSelections,
    };
  }

  // ── Print-mode change ─────────────────────────────────────────────────

  function _onPrintModeChange() {
    const single = el.radioSingle.checked;
    // Disable even (BACK) corner inputs
    Object.values(el.even).forEach(([xEl, yEl]) => {
      xEl.disabled = single;
      yEl.disabled = single;
    });
    // Show/hide hint
    if (el.backHint) el.backHint.classList.toggle('visible', single);
    // Update BACK canvas color
    WarpPreview.setDisabled('back', single);
  }

  // ── Run / Stop ────────────────────────────────────────────────────────

  function _setRunBtn(state) {
    // state: 'idle' | 'running' | 'stopping'
    const btn = el.btnRun;
    btn.classList.remove('btn-launch', 'btn-stop');
    if (state === 'idle') {
      btn.className = 'btn btn-launch';
      btn.textContent = '▶\u00a0\u00a0Запустити';
      btn.disabled = false;
    } else if (state === 'running') {
      btn.className = 'btn btn-stop';
      btn.textContent = '⏹\u00a0\u00a0Зупинити';
      btn.disabled = false;
    } else {
      btn.className = 'btn btn-stop';
      btn.textContent = 'Зупиняємо...';
      btn.disabled = true;
    }
  }

  async function _onRunOrStop() {
    if (_processing) {
      _setRunBtn('stopping');
      await API.stopProcessing();
      return;
    }

    const pdfPath = FileList.current();
    if (!pdfPath) {
      alert('Будь ласка, додайте PDF-файл за допомогою кнопки «⊕ Додати».');
      return;
    }

    const settings = _collectSettings();
    await API.saveSettings(settings);

    const mode     = el.modeSelect.value || 'cmyk';
    const baseMode = mode.replace(/_warp$/, '');
    const suffixMap = {
      cmyk:      settings.output_suffix_cmyk,
      grayscale: settings.output_suffix_gray,
      rgb:       settings.output_suffix_rgb,
    };
    const outputSuffix = suffixMap[baseMode] || settings.output_suffix_cmyk;

    // Determine ICC cs_key
    const iccCsMap = {
      cmyk:      { csKey: 'cmyk', settingsKey: 'icc_profile_cmyk' },
      grayscale: { csKey: 'gray', settingsKey: 'icc_profile_gray' },
      rgb:       { csKey: 'rgb',  settingsKey: 'icc_profile_rgb'  },
    };
    const iccInfo = iccCsMap[baseMode] || iccCsMap.cmyk;
    const iccProfileName = settings.use_icc_profile ? (settings[iccInfo.settingsKey] || '') : '';

    const statusText = `Обробка: ${pdfPath.split(/[\\/]/).pop()}  [${mode}]`;
    Progress.show(statusText);
    StatusBar.set(`${statusText}…`);

    _processing = true;
    _setRunBtn('running');

    await API.startProcessing({
      pdf_path:         pdfPath,
      mode:             mode,
      dpi:              settings.dpi,
      odd_corners:      settings.odd_corners,
      even_corners:     settings.even_corners,
      output_suffix:    outputSuffix,
      use_icc_profile:  settings.use_icc_profile,
      icc_profile_name: iccProfileName,
      icc_cs_key:       iccInfo.csKey,
      print_mode:       settings.print_mode,
      interpolation:    settings.interpolation,
      compression:      settings.compression,
    });
  }

  // ── onProgress — called from Python via evaluate_js ───────────────────

  window.onProgress = function(payload) {
    if (payload.type === 'log') {
      Progress.updateText(payload.text);
    } else if (payload.type === 'progress') {
      Progress.update(payload.page, payload.total);
    } else if (payload.type === 'done') {
      _processing = false;
      _setRunBtn('idle');

      if (payload.cancelled) {
        Progress.setError('⛔ Зупинено');
        el.pageCounter.textContent = '';
        StatusBar.set('⛔ Конвертацію зупинено користувачем');
      } else if (!payload.success) {
        const msg = payload.error || 'Невідома помилка';
        Progress.setError(`Помилка: ${msg}`);
        StatusBar.set(`Помилка: ${msg}`);
        alert(`Помилка обробки:\n${msg}`);
      } else {
        const outPath = payload.output_path;
        const outName = outPath.split(/[\\/]/).pop();
        Progress.setSuccess(`✔ Готово: ${outName}`);
        StatusBar.set(`Готово: ${outPath}`);

        // Save last output folder
        const folder = outPath.replace(/[\\/][^\\/]+$/, '');
        _lastOutputFolder = folder;
        API.saveSettings({ last_output_folder: folder });

        if (_autoOpen) {
          API.openFile(outPath);
        }

        alert(`Файл збережено:\n${outPath}`);
      }
    }
  };

  // ── Event bindings ────────────────────────────────────────────────────

  function _bindEvents() {
    el.btnAddFiles.addEventListener('click', async () => {
      const paths = await API.openFileDialog();
      if (paths && paths.length) FileList.add(paths);
    });

    el.btnOpenFolder.addEventListener('click', async () => {
      const folder = _lastOutputFolder || FileList.lastFolder();
      if (folder) await API.openFolder(folder);
    });

    el.radioSingle.addEventListener('change', _onPrintModeChange);
    el.radioDouble.addEventListener('change', _onPrintModeChange);

    el.iccUse.addEventListener('change', _updateIccState);

    el.autoOpen.addEventListener('change', () => { _autoOpen = el.autoOpen.checked; });

    el.btnRun.addEventListener('click', _onRunOrStop);
  }

  // ── Warp preview setup ────────────────────────────────────────────────

  function _initPreviews() {
    const svgFront = document.getElementById('canvas-front');
    const svgBack  = document.getElementById('canvas-back');

    WarpPreview.register('front', svgFront, el.odd,  WarpPreview.COLOR_FRONT  || '#2979FF');
    WarpPreview.register('back',  svgBack,  el.even, WarpPreview.COLOR_BACK   || '#FF6D00');
  }

  // ── Entry point ───────────────────────────────────────────────────────

  async function init() {
    _refs();
    FileList.init(el.fileSelect);
    Progress.init(el.progressBar, el.progressStatus, el.pageCounter, el.spinner);
    StatusBar.init(el.statusLabel);
    Tabs.init();

    try {
      await API.ready();
    } catch (e) {
      console.warn('pywebview not available:', e);
    }

    await _buildModes();
    await _buildIccRows();
    await _loadSettings();

    _bindEvents();
    _initPreviews();
  }

  // Kick off when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
