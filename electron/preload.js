'use strict';

const { contextBridge, ipcRenderer } = require('electron');

// Allowlist of safe external URL prefixes the renderer may open
const ALLOWED_EXTERNAL_PREFIXES = [
  'https://',
  'http://localhost',
  'http://127.0.0.1',
];

// Allowlist of in-app routes the renderer may navigate to
const ALLOWED_ROUTES = [
  '/',
  '/dashboard',
  '/profile',
  '/network',
  '/my-network',
  '/ide',
  '/login',
  '/register',
];

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

  /**
   * Open a URL in the system default browser.
   * Only https:// URLs and localhost are permitted.
   * @param {string} url
   */
  openExternal: (url) => {
    if (typeof url !== 'string') return;
    const safe = ALLOWED_EXTERNAL_PREFIXES.some((p) => url.startsWith(p));
    if (!safe) {
      console.warn('[preload] openExternal blocked:', url);
      return;
    }
    ipcRenderer.send('shell:openExternal', url);
  },

  /**
   * Ask the main window to navigate to an in-app route.
   * Only routes in the allowlist are permitted.
   * @param {string} route  e.g. "/dashboard"
   */
  navigate: (route) => {
    if (typeof route !== 'string') return;
    // Strip query string and fragment before allowlist check
    const base = route.split(/[?#]/)[0];
    if (!ALLOWED_ROUTES.includes(base)) {
      console.warn('[preload] navigate blocked:', route);
      return;
    }
    ipcRenderer.send('app:navigate', route);
  },

  /**
   * Show a native OS notification.
   * @param {string} title
   * @param {string} body
   */
  showNotification: (title, body) => {
    if (typeof title !== 'string' || typeof body !== 'string') return;
    ipcRenderer.send('app:notify', {
      title: title.slice(0, 120),
      body: body.slice(0, 250),
    });
  },

  /**
   * Listen for an event sent from the main process.
   * Returns a cleanup function – call it to unsubscribe.
   * Supported channels: 'update:available', 'update:downloaded'
   * @param {string} channel
   * @param {Function} listener
   * @returns {Function} unsubscribe
   */
  on: (channel, listener) => {
    const ALLOWED_CHANNELS = ['update:available', 'update:downloaded'];
    if (!ALLOWED_CHANNELS.includes(channel)) return () => {};
    const wrapped = (_event, ...args) => listener(...args);
    ipcRenderer.on(channel, wrapped);
    return () => ipcRenderer.removeListener(channel, wrapped);
  },
});
