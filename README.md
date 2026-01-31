# AI News Aggregation Agent

Personalized daily news digest delivered to your inbox. Powered by local LLM (Ollama) for relevance scoring and summarization.

**Cost: $0** - All local/open-source components.

## Features

- **Smart Filtering**: LLM scores articles based on your interests (configurable topics/keywords)
- **AI Summaries**: Each article gets a concise AI-generated summary
- **Multi-Topic Coverage**: AI, Software Engineering, Startups, Finance, Health
- **Deduplication**: Fuzzy matching removes duplicate stories across sources
- **Email Delivery**: Daily HTML digest via Gmail SMTP

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Cron (7:00 AM) ──► python run_digest.py                │
│                           │                             │
│                           ▼                             │
│  ┌───────────────────────────────────────────────────┐ │
│  │           LangGraph Agent                          │ │
│  │                                                    │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │ │
│  │  │  Fetch   │─►│  Score   │─►│  Format  │─►Email │ │
│  │  │  (MCP)   │  │ (Ollama) │  │  & Send  │        │ │
│  │  └──────────┘  └──────────┘  └──────────┘        │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Stack:**
- **LangGraph** - Agent orchestration with state management
- **MCP** - Model Context Protocol for RSS fetching
- **Ollama + Llama 3.1 8B** - Local LLM for scoring/summarization
- **Gmail SMTP** - Email delivery

## Quick Start

### 1. Prerequisites

```bash
# Install Ollama
brew install ollama

# Start Ollama service
brew services start ollama

# Pull the model
ollama pull llama3.1:8b
```

### 2. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Email

Create `.env` file:

```env
EMAIL_RECIPIENT=your-email@example.com
GMAIL_USER=your-sender@gmail.com
GMAIL_APP_PASSWORD=your_app_password
```

> **Note**: Use a [Gmail App Password](https://myaccount.google.com/apppasswords), not your regular password. Requires 2FA enabled.

### 4. Run

```bash
# Preview digest (no email)
python run_digest.py --dry-run

# Send digest
python run_digest.py

# Quick test (3 articles only)
python run_digest.py --dry-run --test
```

## Configuration

### RSS Sources (`config/sources.yaml`)

```yaml
rss_feeds:
  ai:
    - https://techcrunch.com/tag/artificial-intelligence/feed/
    - https://www.marktechpost.com/feed/
  software:
    - https://news.ycombinator.com/rss
    - https://blog.bytebytego.com/feed
  # ... more topics
```

### Topics & Scoring (`config/topics.yaml`)

```yaml
topics:
  ai_technical:
    keywords:
      - machine learning
      - LLM
      - transformer
      - RAG
    weight: 1.8  # Higher = more important

  agentic_ai:
    keywords:
      - AI agent
      - LangGraph
      - function calling
      - MCP
    weight: 1.8

scoring:
  min_score: 5  # Articles below this are filtered out
```

## Project Structure

```
├── run_digest.py           # CLI entry point
├── src/
│   ├── agent.py            # LangGraph pipeline
│   ├── mcp_rss_server.py   # MCP server for RSS fetching
│   ├── sender.py           # Gmail SMTP delivery
│   ├── models.py           # Data models
│   └── tools/
│       └── ollama_tools.py # LLM scoring & summarization
├── config/
│   ├── sources.yaml        # RSS feed URLs
│   └── topics.yaml         # Keywords & weights
└── logs/                   # Daily run logs
```

## CLI Options

```bash
python run_digest.py [OPTIONS]

Options:
  --dry-run       Preview digest, don't send email
  --test          Process only 3 articles (fast testing)
  --min-score N   Override minimum score (default: from config)
  --verbose, -v   Enable debug logging
  --output FILE   Save digest to markdown file
```

## Cron Setup (Daily Automation)

```bash
# Edit crontab
crontab -e

# Add line (runs at 7:00 AM daily)
0 7 * * * cd /path/to/ai-news-aggregation && .venv/bin/python run_digest.py >> logs/cron.log 2>&1
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Ollama not running" | `brew services start ollama` |
| "Model not found" | `ollama pull llama3.1:8b` |
| "Gmail auth failed" | Use App Password, not regular password |
| "SSL certificate error" | `pip install --upgrade certifi` |
| "No articles fetched" | Check feed URLs in sources.yaml |

## License

MIT