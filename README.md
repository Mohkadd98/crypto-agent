# Crypto Intelligence Agent

An advanced autonomous AI agent specialized in cryptocurrency research, market intelligence, historical analysis, on-chain analytics, and discovering high-potential cryptocurrencies.

## Features

- **Interactive TUI Interface** - Opencode-style terminal user interface (recommended)
- **Conversational Intelligence** - Multi-turn conversations with context awareness
- **Dynamic Skills System** - Modular, extensible skill architecture
- **Comprehensive Tool Set** - Market data, technical analysis, on-chain, research tools
- **Autonomous Workflows** - Plan, execute, and synthesize research automatically
- **Persistent Memory** - SQLite-based storage for conversations, analyses, predictions
- **Kilo AI Integration** - Configurable model selection and task routing
- **Multi-source Market Data** - CoinGecko, Binance, DexScreener, GeckoTerminal
- **Multi-chain On-chain Analysis** - Ethereum, BSC, Polygon, Arbitrum, Optimism, Base, Avalanche
- **Advanced Analytics (no paid keys required)** - Derivatives positioning, market breadth, correlation/beta, sector rotation, order book, Fibonacci, volume profile, volatility, momentum, mean reversion, Ichimoku, Wyckoff, new DEX pairs, gas tracker
- **Web Search (web_search)** - Live news/context search via Google News RSS so the agent can research coins, not just stop at market data
- **Trade Journal** - Record trades and track win rate, PnL, and profit factor

## Quick Start

### Prerequisites

- Python 3.11+
- Python 3.11+ (PEP 668 managed - always use `venv/bin/python`)
- Kilo API key (free at https://kilo.ai) - *optional for core functionality*

### Installation

```bash
cd crypto-agent
source venv/bin/activate  # activate the virtual environment
pip install -r requirements.txt
cp config/api_keys.env.example config/api_keys.env
# Edit config/api_keys.env - Kilo API key is optional
python tui_main.py     # launch the TUI, or: python main.py for CLI
```

### Configuration

Edit `config/api_keys.env`:

```env
# Kilo API (optional - core features work without it)
KILO_API_KEY=sk-...  # Get free at https://kilo.ai

# CoinGecko (optional - higher rate limits with key)
COINGECKO_API_KEY=your_key  # Optional

# Binance (optional - API keys for signed endpoints)
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# RPC URLs for on-chain analysis (optional - free public endpoints included)
ETH_RPC_URL=https://eth.llamarpc.com
BSC_RPC_URL=https://bsc-dataseed.binance.org/
POL_RPC_URL=https://polygon.llamarpc.com/

# Etherscan for wallet tracking
ETHERSCAN_API_KEY=your_key  # Optional
```

## TUI Quick Start

```bash
source venv/bin/activate
python tui_main.py
```

Layout: titlebar · sidebar (sessions + skills) · chat · composer (always visible, focused) · status bar.

### Composer & writing place

- The composer is **always visible at the bottom** and keeps focus.
- It is a multi-line text area with a real writing area (4 text lines visible).
- `Enter` sends · `Ctrl+J` newline · `Ctrl+Up/Down` history · `Tab` command completion
- Placeholder: `Ask anything, or type / for a command…`

### Copy (from chat)

- `Ctrl+C` copies the last response (or your current selection) to the clipboard.
- `/copy` command does the same (works anytime, even while the agent is working).

### Keybindings

| Key | Action |
| --- | --- |
| `Ctrl+P` | Command palette |
| `Ctrl+N` | New session |
| `Ctrl+L` | Clear transcript |
| `Ctrl+B` | Toggle sidebar |
| `Ctrl+U` / `Ctrl+D` | Scroll chat |
| `F1` | Help screen |
| `Esc` | Back to composer |
| `Ctrl+C` | Copy last response |
| `Ctrl+Q` | Quit |

## Kilo AI

- Base URL: `https://ai-gateway.kilo.ai/api/v1` (AI Gateway, OpenAI-compatible).
- Models: task defaults are `kilo-auto/free` (free tier) — override in `config/settings.yaml` → `models:`.
- Get a key at https://app.kilo.ai/profile (or kilo.ai).

## Free AI Provider (Google Gemini) — recommended for Arabic answers

- The agent automatically uses **Google Gemini** (OpenAI-compatible endpoint) when `GEMINI_API_KEY` is set.
- Free tier: no credit card required — get a key at https://aistudio.google.com/apikey
- Base URL: `https://generativelanguage.googleapis.com/v1beta/openai/`
- Default model: `gemini-3.8-flash`
- If `GEMINI_API_KEY` is empty, the agent falls back to the Kilo provider (`kilo-auto/free`).
- AI answers are generated in Arabic when the user writes in Arabic.