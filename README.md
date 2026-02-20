# SocialChain

A **VS Code-style blockchain network workbench** for creating, maintaining, and visualizing networks of **people, devices, and AI agents** — available as a downloadable desktop app for Windows, macOS, and Linux, powered by [Electron](https://electronjs.org).

Every participant — human, IoT device, or autonomous agent — is a cryptographically-verified blockchain node with a self-sovereign decentralized identity (DID). The workbench gives you the tools to design, deploy, inspect, and evolve the network without leaving the app.

## Downloads

Get started instantly — no terminal required. Download the desktop app for your platform from the [latest GitHub Release](https://github.com/jameskrice7/SocialChain/releases/latest):

| Platform | Installer | Notes |
|----------|-----------|-------|
| **Windows** | [⬇ SocialChain-Setup.exe](https://github.com/jameskrice7/SocialChain/releases/latest/download/SocialChain-Setup.exe) | NSIS installer, 64-bit |
| **macOS (Intel)** | [⬇ SocialChain-x64.dmg](https://github.com/jameskrice7/SocialChain/releases/latest/download/SocialChain-x64.dmg) | macOS 10.15+ |
| **macOS (Apple Silicon)** | [⬇ SocialChain-arm64.dmg](https://github.com/jameskrice7/SocialChain/releases/latest/download/SocialChain-arm64.dmg) | M1/M2/M3 |
| **Linux** | [⬇ SocialChain-x86_64.AppImage](https://github.com/jameskrice7/SocialChain/releases/latest/download/SocialChain-x86_64.AppImage) | AppImage, no install needed |
| **Linux (.deb)** | [⬇ SocialChain-amd64.deb](https://github.com/jameskrice7/SocialChain/releases/latest/download/SocialChain-amd64.deb) | Debian / Ubuntu |

> **No Python or Node.js required.** The desktop installer bundles everything you need.  
> After installing, launch SocialChain, create your node identity, and you're on the network.

All releases are published automatically via GitHub Actions when a version tag is pushed. See [Releases](https://github.com/jameskrice7/SocialChain/releases) for previous versions and release notes.

## Workbench Features

| Panel | Description |
|-------|-------------|
| **Node Registry** | Browse all nodes (people, devices, AI agents), filter by type, inspect DIDs and metadata, trigger on-chain verification |
| **Topology Builder** | Drag-and-drop canvas to design network topologies; add node types and draw connections; commit to blockchain in one click |
| **Transaction Inspector** | Browse every transaction across every block and the mempool; full JSON payload + signature view |
| **Contract Editor** | Write Solidity smart contracts with built-in templates; simulate compile/deploy; send source to the AI agent for an audit |
| **Agent Chat Panel** | Always-available AI assistant (`Ctrl+\``) — answers questions about contracts, transactions, DIDs, and topology in real time |
| **Network Map (2D)** | Live force-directed D3 graph of all nodes and connections, updated in real time |
| **3D Network Globe** | Full 3D interactive WebGL force graph — drag, zoom, and explore the network at fractal depth |

## Desktop App

The desktop edition wraps the full SocialChain workbench in a native application window — no browser required. The Electron shell starts the Python/Flask backend automatically on launch, then displays the workbench UI inside a frameless native window, exactly like VS Code or Positron.

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Node.js     | ≥ 18    |
| npm         | ≥ 9     |
| Python      | ≥ 3.8   |

### Quick start (development)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Node.js dependencies
npm install

# 3. Launch the desktop app
npm start
```

### Build a distributable installer

```bash
# Auto-detect current OS
./build-desktop.sh

# Target a specific OS (cross-compile where supported)
./build-desktop.sh --win     # Windows NSIS installer (.exe)
./build-desktop.sh --mac     # macOS DMG + ZIP
./build-desktop.sh --linux   # Linux AppImage + .deb

# Optional: bundle the Python interpreter (self-contained, no Python install needed)
BUNDLE_PYTHON=1 ./build-desktop.sh
```

Installers are written to the `dist/` directory.

### Keyboard shortcuts

| Shortcut              | Action                    |
|-----------------------|---------------------------|
| `Ctrl/Cmd + R`        | Reload                    |
| `Ctrl/Cmd + Shift + I`| Developer tools           |
| `Ctrl/Cmd + 1`        | Dashboard                 |
| `Ctrl/Cmd + 2`        | Profile                   |
| `Ctrl/Cmd + 3`        | Network Map               |
| `Ctrl/Cmd + 4`        | My Network (3D)           |
| `Ctrl/Cmd + 5`        | Network Workbench (IDE)   |
| `Ctrl/Cmd + \``       | Toggle Agent Chat Panel   |
| `Ctrl/Cmd + Q`        | Quit                      |

---

## Architecture

```
SocialChain/
├── electron/           # Electron desktop shell
│   ├── main.js         # Main process: spawns Flask, creates window, workbench menu
│   ├── preload.js      # Secure context bridge (renderer ↔ Node.js)
│   └── splash.html     # Startup splash screen
├── socialchain/        # Python / Flask application
│   ├── blockchain/     # Core blockchain: Block, Transaction, Blockchain, Identity (DID)
│   ├── network/        # P2P layer: NetworkNode, PeerRegistry
│   ├── social/         # Social layer: Profile, NetworkMap, SocialRequest
│   ├── agents/         # AI Agent layer: AIAgent (chat + autonomous_post), AgentTask
│   └── api/            # REST API (Flask): chain, network, social, agents routes
│       └── templates/
│           ├── base.html          # VS Code workbench shell (activity bar, chat panel, status bar)
│           ├── ide.html           # Network Workbench IDE (4 tabbed panels)
│           ├── dashboard.html     # Blockchain dashboard
│           ├── network.html       # 2D force-directed network map
│           ├── user_network.html  # Full-screen 3D network globe
│           ├── profile.html       # Node profile & social requests
│           ├── landing.html       # Public landing page
│           ├── login.html         # Authentication
│           └── register.html      # Node registration
├── package.json        # Electron + electron-builder configuration
└── build-desktop.sh    # Convenience build script
```

### Components

- **Desktop Shell**: Electron main process manages the app lifecycle, spawns the Python backend as a child process, and presents the workbench UI in a native BrowserWindow with VS Code-style keyboard shortcuts.
- **Workbench UI**: Activity bar (left), tabbed IDE panels (Node Registry, Topology Builder, Transaction Inspector, Contract Editor), Agent Chat panel (right, `Ctrl+\``), status bar (bottom).
- **Blockchain Core**: SHA-256 proof-of-work (difficulty=4), ECDSA secp256k1 identities (DIDs), transactions with signatures
- **P2P Network**: Peer registry, HTTP broadcast, chain sync
- **Social Layer**: Profiles (human/device/agent), connection graph, social requests
- **AI Agents**: Blockchain-registered agents with task queues, chat capability (IDE assistant), and autonomous-post capability
- **REST API**: Full CRUD over all subsystems via Flask blueprints

## Web / Server mode

The original web server mode is still fully supported:

```bash
pip install -r requirements.txt
python run.py
```

The server starts on `http://localhost:5000`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/chain | Get full blockchain |
| POST | /api/transactions | Create transaction |
| POST | /api/mine | Mine pending transactions |
| GET | /api/network/peers | List peers |
| POST | /api/network/peers | Register peer |
| GET | /api/social/profiles | List profiles |
| POST | /api/social/profiles | Create/update profile |
| GET | /api/social/map | Get network adjacency map |
| POST | /api/social/requests | Create social request |
| GET | /api/social/requests | List social requests |
| PATCH | /api/social/requests/\<id\> | Update request status |
| GET | /api/agents | List agents |
| POST | /api/agents | Register agent |
| POST | /api/agents/chat | Chat with agent assistant (IDE chat panel) |
| GET | /api/agents/feed | Autonomous agent activity feed |
| POST | /api/agents/\<did\>/tasks | Submit task to agent |
| GET | /api/agents/\<did\>/tasks | List agent tasks |

## Running Tests

```bash
pytest tests/ -v
```

## DID Format

Every entity (user, device, agent, node) gets a decentralized identifier:
```
did:socialchain:<compressed-secp256k1-pubkey-hex>
```
