'use strict';

const { app, BrowserWindow, Menu, Tray, shell, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn, execFile } = require('child_process');
const http = require('http');
const fs = require('fs');

// ── Configuration ────────────────────────────────────────────────────────────
const FLASK_PORT = 5000;
const FLASK_STARTUP_TIMEOUT_MS = 15000; // 15 seconds
const FLASK_POLL_INTERVAL_MS = 300;

let mainWindow = null;
let splashWindow = null;
let tray = null;
let flaskProcess = null;
let isQuitting = false;

// ── Resolve the Python executable and backend root ───────────────────────────
function getPythonExecutable() {
  // When packaged with electron-builder the Python backend lives in extraResources
  const resourcesPath = process.resourcesPath || path.join(__dirname, '..');
  const appDir = path.join(resourcesPath, 'app');

  // Check for a PyInstaller-bundled server executable first
  const bundledExe = path.join(
    appDir,
    process.platform === 'win32' ? 'socialchain-server.exe' : 'socialchain-server'
  );
  if (fs.existsSync(bundledExe)) {
    return { exe: bundledExe, args: [], cwd: appDir, bundled: true };
  }

  // Fall back to the system Python interpreter (development mode)
  const pythonCandidates =
    process.platform === 'win32'
      ? ['python', 'python3']
      : ['python3', 'python'];

  for (const candidate of pythonCandidates) {
    try {
      require('child_process').execSync(`${candidate} --version`, { stdio: 'ignore' });
      const runScript = fs.existsSync(path.join(appDir, 'run.py'))
        ? path.join(appDir, 'run.py')
        : path.join(__dirname, '..', 'run.py');
      return { exe: candidate, args: [runScript], cwd: path.dirname(runScript), bundled: false };
    } catch (_) {
      // try next
    }
  }

  return null;
}

// ── Start the Flask backend ───────────────────────────────────────────────────
function startFlaskServer() {
  const resolved = getPythonExecutable();

  if (!resolved) {
    dialog.showErrorBox(
      'Python not found',
      'SocialChain requires Python 3.8+ to be installed on your system.\n\n' +
      'Please install Python from https://python.org and try again.'
    );
    app.quit();
    return;
  }

  const env = {
    ...process.env,
    FLASK_ENV: 'production',
    FLASK_PORT: String(FLASK_PORT),
    // Prevent Python from buffering stdout/stderr
    PYTHONUNBUFFERED: '1',
  };

  console.log(`[SocialChain] Starting backend: ${resolved.exe} ${resolved.args.join(' ')}`);

  flaskProcess = spawn(resolved.exe, resolved.args, {
    cwd: resolved.cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  flaskProcess.stdout.on('data', (data) => {
    process.stdout.write(`[Flask] ${data}`);
  });
  flaskProcess.stderr.on('data', (data) => {
    process.stderr.write(`[Flask] ${data}`);
  });

  flaskProcess.on('exit', (code) => {
    if (!isQuitting) {
      console.error(`[SocialChain] Backend exited unexpectedly with code ${code}`);
      dialog.showErrorBox(
        'Backend Crashed',
        `The SocialChain backend exited with code ${code}.\nThe application will now close.`
      );
      app.quit();
    }
  });
}

// ── Poll until Flask is ready ─────────────────────────────────────────────────
function waitForFlask(callback) {
  const deadline = Date.now() + FLASK_STARTUP_TIMEOUT_MS;

  const attempt = () => {
    const req = http.get(`http://127.0.0.1:${FLASK_PORT}/`, (res) => {
      // Any HTTP response means the server is up
      res.resume();
      callback(null);
    });
    req.on('error', () => {
      if (Date.now() >= deadline) {
        callback(new Error('Flask server did not start within the timeout.'));
        return;
      }
      setTimeout(attempt, FLASK_POLL_INTERVAL_MS);
    });
    req.setTimeout(1000, () => req.destroy());
  };

  attempt();
}

// ── Splash window ─────────────────────────────────────────────────────────────
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 480,
    height: 300,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    center: true,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  splashWindow.loadFile(path.join(__dirname, 'splash.html'));
  splashWindow.once('ready-to-show', () => splashWindow.show());
}

// ── Main window ───────────────────────────────────────────────────────────────
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    title: 'SocialChain',
    backgroundColor: '#050510',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      // Allow loading the local Flask server
      webSecurity: true,
    },
  });

  // ── Application menu ──────────────────────────────────────────────────────
  const menuTemplate = [
    {
      label: 'SocialChain',
      submenu: [
        { label: 'About SocialChain', role: 'about' },
        { type: 'separator' },
        { label: 'Quit', accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q', click: onQuit },
      ],
    },
    {
      label: 'View',
      submenu: [
        { label: 'Reload', accelerator: 'CmdOrCtrl+R', click: () => mainWindow && mainWindow.webContents.reload() },
        { label: 'Force Reload', accelerator: 'CmdOrCtrl+Shift+R', click: () => mainWindow && mainWindow.webContents.reloadIgnoringCache() },
        { type: 'separator' },
        { label: 'Toggle Developer Tools', accelerator: 'CmdOrCtrl+Shift+I', click: () => mainWindow && mainWindow.webContents.toggleDevTools() },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Navigate',
      submenu: [
        { label: 'Dashboard', accelerator: 'CmdOrCtrl+1', click: () => navigateTo('/dashboard') },
        { label: 'Profile', accelerator: 'CmdOrCtrl+2', click: () => navigateTo('/profile') },
        { label: 'Network', accelerator: 'CmdOrCtrl+3', click: () => navigateTo('/network') },
        { label: 'My Network', accelerator: 'CmdOrCtrl+4', click: () => navigateTo('/my-network') },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Open API Documentation',
          click: () => shell.openExternal(`http://localhost:${FLASK_PORT}/api/chain`),
        },
        { type: 'separator' },
        {
          label: 'Report an Issue',
          click: () => shell.openExternal('https://github.com/jameskrice7/SocialChain/issues'),
        },
      ],
    },
  ];

  // On macOS add standard Edit menu
  if (process.platform === 'darwin') {
    menuTemplate.splice(1, 0, {
      label: 'Edit',
      submenu: [
        { role: 'undo' }, { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' },
        { role: 'selectAll' },
      ],
    });
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate(menuTemplate));

  mainWindow.loadURL(`http://127.0.0.1:${FLASK_PORT}/`);

  mainWindow.once('ready-to-show', () => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
    mainWindow.focus();
  });

  // Open external links in the default browser, not in the app window
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(`http://127.0.0.1:${FLASK_PORT}`)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  mainWindow.on('close', (e) => {
    if (!isQuitting && process.platform === 'darwin') {
      // On macOS, hide instead of quit when window is closed
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── System tray ───────────────────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
  if (!fs.existsSync(iconPath)) return; // skip if no icon asset present

  tray = new Tray(iconPath);
  tray.setToolTip('SocialChain');
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Open SocialChain', click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } } },
    { type: 'separator' },
    { label: 'Quit', click: onQuit },
  ]);
  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } });
}

// ── Helper: navigate main window ──────────────────────────────────────────────
function navigateTo(route) {
  if (mainWindow) {
    mainWindow.loadURL(`http://127.0.0.1:${FLASK_PORT}${route}`);
    mainWindow.show();
  }
}

// ── IPC handlers ──────────────────────────────────────────────────────────────
ipcMain.handle('app:version', () => app.getVersion());
ipcMain.handle('app:platform', () => process.platform);

// ── App lifecycle ─────────────────────────────────────────────────────────────
function onQuit() {
  isQuitting = true;
  app.quit();
}

app.whenReady().then(() => {
  createSplashWindow();
  startFlaskServer();

  waitForFlask((err) => {
    if (err) {
      if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close();
      dialog.showErrorBox('Startup Error', `Could not connect to the SocialChain backend:\n${err.message}`);
      app.quit();
      return;
    }
    createMainWindow();
    createTray();
  });
});

app.on('window-all-closed', () => {
  // On macOS the app stays active until explicitly quit
  if (process.platform !== 'darwin') {
    onQuit();
  }
});

app.on('activate', () => {
  // macOS: re-show window when dock icon is clicked
  if (mainWindow) {
    mainWindow.show();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
});

app.on('will-quit', () => {
  // Kill the Flask backend when the app exits
  if (flaskProcess && !flaskProcess.killed) {
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(flaskProcess.pid), '/f', '/t']);
      } else {
        flaskProcess.kill('SIGTERM');
      }
    } catch (e) {
      console.error('[SocialChain] Error killing backend:', e);
    }
  }
});
