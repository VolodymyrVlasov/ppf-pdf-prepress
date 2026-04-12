/**
 * api.js — All calls to Python via window.pywebview.api.*
 *
 * Each exported function returns a Promise.
 * When running outside pywebview (browser dev), stubs return safe defaults.
 */

const API = (() => {

  function _api() {
    return window.pywebview && window.pywebview.api;
  }

  /** Returns true when the pywebview bridge is available. */
  function isAvailable() {
    return Boolean(_api());
  }

  /**
   * Waits for pywebview to initialise then resolves.
   * Polls every 50 ms, times out after 10 s.
   */
  function ready() {
    return new Promise((resolve, reject) => {
      if (isAvailable()) { resolve(); return; }
      let tries = 0;
      const id = setInterval(() => {
        tries++;
        if (isAvailable()) { clearInterval(id); resolve(); }
        else if (tries > 200) { clearInterval(id); reject(new Error('pywebview timeout')); }
      }, 50);
    });
  }

  // ── Settings ────────────────────────────────────────────────

  async function getSettings() {
    const a = _api();
    if (!a) return {};
    return a.get_settings();
  }

  async function saveSettings(data) {
    const a = _api();
    if (!a) return false;
    return a.save_settings(data);
  }

  // ── Profiles ────────────────────────────────────────────────

  async function getProfiles(colorSpace) {
    const a = _api();
    if (!a) return [];
    return a.get_profiles(colorSpace);
  }

  // ── File dialogs ────────────────────────────────────────────

  async function openFileDialog() {
    const a = _api();
    if (!a) return [];
    return a.open_file_dialog();
  }

  async function openFolder(path) {
    const a = _api();
    if (!a) return;
    return a.open_folder(path);
  }

  async function openFile(path) {
    const a = _api();
    if (!a) return;
    return a.open_file(path);
  }

  // ── Processing ──────────────────────────────────────────────

  async function startProcessing(params) {
    const a = _api();
    if (!a) return;
    return a.start_processing(params);
  }

  async function stopProcessing() {
    const a = _api();
    if (!a) return;
    return a.stop_processing();
  }

  // ── Metadata ────────────────────────────────────────────────

  async function getModes() {
    const a = _api();
    if (!a) return [];
    return a.get_modes();
  }

  async function getIccSpaces() {
    const a = _api();
    if (!a) return [];
    return a.get_icc_spaces();
  }

  return {
    ready,
    isAvailable,
    getSettings,
    saveSettings,
    getProfiles,
    openFileDialog,
    openFolder,
    openFile,
    startProcessing,
    stopProcessing,
    getModes,
    getIccSpaces,
  };
})();
