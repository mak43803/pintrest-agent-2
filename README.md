# 🤖 Pinterest AI Agent

> **Production-grade local AI application** for autonomous Pinterest automation,
> powered by a local LLM (Ollama + Qwen3), Playwright browser automation, and SQLite persistence.

---

## ⚡ Tech Stack

| Component        | Technology                     |
|------------------|--------------------------------|
| **Language**     | Python 3.12+                   |
| **LLM**         | Ollama (Qwen 3)                |
| **Browser**      | Playwright (Chromium)          |
| **Database**     | SQLite (via aiosqlite)         |
| **Architecture** | Modular, OOP, Fully Async      |

---

## 📁 Project Structure

```
pinterest-ai-agent/
│
├── main.py                  # Application entry point
├── config.py                # Root configuration loader
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore               # Git ignore rules
│
├── agent/                   # 🧠 Core AI Agent
│   ├── __init__.py
│   ├── base_agent.py        # Abstract base agent class
│   ├── pinterest_agent.py   # Main Pinterest agent implementation
│   └── agent_state.py       # Agent state machine & lifecycle
│
├── browser/                 # 🌐 Playwright Browser Automation
│   ├── __init__.py
│   ├── browser_manager.py   # Browser lifecycle management
│   ├── page_controller.py   # Page interaction API
│   └── screenshot_handler.py# Screenshot capture & storage
│
├── database/                # 🗄️ SQLite Persistence Layer
│   ├── __init__.py
│   ├── db_manager.py        # Database connection & migrations
│   ├── models.py            # Data models / table schemas
│   └── repositories.py      # Data access objects (DAOs)
│
├── memory/                  # 🧠 Agent Memory System
│   ├── __init__.py
│   ├── memory_manager.py    # Memory orchestrator
│   ├── conversation_history.py  # Chat history management
│   └── context_builder.py   # LLM context assembly
│
├── planner/                 # 📋 Task Planning & Execution
│   ├── __init__.py
│   ├── task_planner.py      # Goal → action step decomposition
│   ├── action_parser.py     # LLM output → structured actions
│   └── plan_executor.py     # Sequential step execution
│
├── scheduler/               # ⏰ Task Scheduling
│   ├── __init__.py
│   ├── task_scheduler.py    # Async cron-like scheduler
│   └── job_store.py         # Persistent job storage
│
├── prompts/                 # 💬 LLM Prompt Templates
│   ├── __init__.py
│   ├── system_prompts.py    # Agent identity & behavior
│   ├── task_prompts.py      # Task-specific templates
│   └── prompt_templates.py  # Reusable prompt utilities
│
├── tools/                   # 🔧 Agent Tools / Actions
│   ├── __init__.py
│   ├── base_tool.py         # Abstract tool base class
│   ├── tool_registry.py     # Tool discovery & invocation
│   └── pinterest_tools.py   # Pinterest-specific tools
│
├── config/                  # ⚙️ Configuration
│   ├── __init__.py
│   ├── settings.py          # Typed settings with validation
│   └── constants.py         # App-wide constants
│
├── utils/                   # 🛠️ Shared Utilities
│   ├── __init__.py
│   ├── logger.py            # Structured logging setup
│   ├── helpers.py           # General-purpose helpers
│   └── exceptions.py        # Custom exception hierarchy
│
├── tests/                   # 🧪 Test Suite
│   ├── __init__.py
│   ├── test_agent.py
│   ├── test_database.py
│   ├── test_memory.py
│   ├── test_planner.py
│   └── test_tools.py
│
├── logs/                    # 📝 Runtime Logs (gitignored)
├── downloads/               # 📥 Downloaded Files (gitignored)
└── images/                  # 🖼️ Downloaded Images (gitignored)
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.ai/) installed and running
- Qwen 3 model pulled: `ollama pull qwen3`

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd pinterest-ai-agent

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium

# 5. Configure environment
copy .env.example .env
# Edit .env with your settings

# 6. Run the agent
python main.py
```

---

## 🏗️ Architecture Principles

- **Modular Design** — Each folder is a self-contained module with clear boundaries
- **Object-Oriented** — Abstract base classes define contracts; concrete classes implement them
- **Fully Async** — All I/O operations use `async/await` for non-blocking execution
- **Dependency Injection** — Subsystems are injected into the agent, enabling testability
- **Fail-Fast Configuration** — Settings are validated at startup, not at runtime
- **Structured Logging** — Every action is logged with timestamps and context
- **Custom Exceptions** — Domain-specific error hierarchy for precise error handling

---

## 📄 License

MIT
