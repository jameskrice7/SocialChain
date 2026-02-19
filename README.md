# SocialChain

A universal blockchain-based social network that connects devices, users, and AI agents across the internet.

## Architecture

```
socialchain/
├── blockchain/     # Core blockchain: Block, Transaction, Blockchain, Identity (DID)
├── network/        # P2P layer: NetworkNode, PeerRegistry
├── social/         # Social layer: Profile, NetworkMap, SocialRequest
├── agents/         # AI Agent layer: AIAgent, AgentTask
└── api/            # REST API (Flask): chain, network, social, agents routes
```

### Components

- **Blockchain Core**: SHA-256 proof-of-work (difficulty=4), ECDSA secp256k1 identities (DIDs), transactions with signatures
- **P2P Network**: Peer registry, HTTP broadcast, chain sync
- **Social Layer**: Profiles (human/device/agent), connection graph, social requests (feature requests, messages, agent deployments)
- **AI Agents**: Blockchain-registered agents with task queues and capability handlers
- **REST API**: Full CRUD over all subsystems via Flask blueprints

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
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
| PATCH | /api/social/requests/<id> | Update request status |
| GET | /api/agents | List agents |
| POST | /api/agents | Register agent |
| POST | /api/agents/<did>/tasks | Submit task to agent |
| GET | /api/agents/<did>/tasks | List agent tasks |

## Running Tests

```bash
pytest tests/ -v
```

## DID Format

Every entity (user, device, agent, node) gets a decentralized identifier:
```
did:socialchain:<compressed-secp256k1-pubkey-hex>
```
A new app for connecting devices in a technophysical network
