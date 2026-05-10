# 🛸 Mind Cache — Context Completion Agent

Mind Cache is an agentic AI pipeline designed to debunk viral misinformation and add the "missing context" to social media posts. It uses a tiered LLM routing system (Claude 4.7 & Qwen-3.5) with integrated web research and automated image generation.

---

## 🏗 Project Architecture

The project is structured for production-grade reliability and modularity:

```text
mind_cache_pipeline/
├── bot/                # Telegram interaction layer
│   ├── handlers.py     # State machine & command logic
│   └── messenger.py    # Robust HTML delivery & photo handling
├── llm/                # Intelligence layer
│   ├── router.py       # Tiered routing (Claude -> Ollama)
│   ├── ollama.py       # Agentic search loop (Qwen-3.5)
│   └── images.py       # Infographic generation (Z-Image-Turbo)
├── pipeline/           # Business logic
│   ├── analysis.py     # Phase 1: Deep Analytical Dive (Temp: 0.1)
│   └── output_gen.py   # Phase 2: Human-Flair Social Drafting (Temp: 0.7)
├── prompts/            # System & user instructions
├── main.py             # Entry point with state persistence
└── config.py           # Configuration & Environment loading
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Ollama** (for fallback intelligence and image generation)
- **Claude CLI** (optional, for primary analysis)

### 2. Installation
```bash
git clone <your-repo-url>
cd mind_cache_pipeline
pip install -r requirements.txt
```

### 3. Environment Setup
Create a `.env` file in the root directory:
```env
# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_OUTPUT_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Intelligence
OLLAMA_API_KEY=...
OLLAMA_CLOUD_MODEL=qwen3.5:397b
OLLAMA_IMAGE_MODEL=z-image-turbo
CLAUDE_CLI_PATH=claude
```

---

## 🛠 Usage

### Start the Bot
Run the main entry point. The bot uses `PicklePersistence`, so it will remember your progress even if restarted.
```bash
python3 main.py
```

### Production Deployment (PM2)
The project includes an `ecosystem.config.js` for PM2 management:
```bash
pm2 start ecosystem.config.js
```

---

## 🧠 The "Mind Cache" Workflow

1. **Content Accumulation**: Paste any article or tweet into the Input Bot. You can send multiple chunks.
2. **Analysis (/go)**:
   - The bot enters **Deep Dive Phase** (Temperature 0.1).
   - It performs real-time web searches to verify claims.
   - It delivers a raw, factual analysis for your review.
3. **Approval (✅)**:
   - The bot enters **Human Flair Phase** (Temperature 0.7).
   - It drafts a Short Reply + long-form Thread.
   - It automatically generates a 1024x1024 Infographic image.
4. **Delivery**: Final outputs are sent to your dedicated Output Channel.

---

## 🛡 Production Features
- **State Persistence**: Recovers from crashes automatically.
- **HTML Safety**: Automatically splits and cleans long messages for Telegram.
- **Image Overwrite**: Keeps disk usage low by overwriting the `/tmp/mind_cache_infographic.png` scratchpad.
- **Tiered Routing**: Seamlessly fails over from Claude to Ollama if quotas are hit.