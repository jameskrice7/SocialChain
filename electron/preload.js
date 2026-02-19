'use strict';

const { contextBridge, ipcRenderer } = require('electron');

/**
 * Expose a minimal, safe API to the renderer process (web pages served by Flask).
 * The renderer can call window.socialchain.<method>() for native desktop features.
 */
contextBridge.exposeInMainWorld('socialchain', {
  /** Returns the app version string (e.g. "1.0.0"). */
  getVersion: () => ipcRenderer.invoke('app:version'),

  /** Returns the current OS platform: "win32", "darwin", or "linux". */
  getPlatform: () => ipcRenderer.invoke('app:platform'),

  /** True when running inside Electron (desktop), false in a browser. */
  isDesktop: true,
});
