# News Aggregation Agent

## Project Overview

This is a Python-based news aggregation and curation agent that delivers personalized daily news digests. The agent
scrapes news from RSS feeds and APIs, uses AI (local Llama model) for relevance filtering and summarization, and emails
a curated digest every morning at 7:00 AM.

**Target User**: Individual staying informed across AI, software, investment, opportunities, politics, NBA, and health
topics.

**Tech Stack**:

- Python 3.10+
- Ollama with Llama 3.1 8B (local AI)
- RSS feed parsing (feedparser)
- News APIs (NewsAPI free tier)
- Email delivery (SMTP/SendGrid)
- Scheduling (cron or GitHub Actions)

## Development Environment

### Required Tools

```bash
# Install Ollama for local AI
brew install ollama

# Download Llama model (8B recommended for M4 Pro)
ollama pull llama3.1:8b

# Install Python dependencies
pip install feedparser requests beautifulsoup4 python-dotenv schedule

# Optional: SendGrid for email
pip install sendgrid
```

### Environment Variables

Create a `.env` file in project root:

```
EMAIL_RECIPIENT=your-email@example.com
SENDGRID_API_KEY=your_key_here  # Optional if using Gmail SMTP
GMAIL_USER=your-gmail@gmail.com  # If using Gmail
GMAIL_APP_PASSWORD=your_app_password  # If using Gmail
NEWSAPI_KEY=your_newsapi_key  # Optional, free tier available
```

## File Structure

```
news-agent/
├── CLAUDE.md                  # This file
├── .env                       # Environment variables (gitignored)
├── .gitignore
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── aggregator.py         # RSS/API news fetching
│   ├── filter.py             # Relevance scoring and filtering
│   ├── summarizer.py         # AI summarization with Ollama
│   ├── formatter.py          # Digest formatting (Markdown/HTML)
│   ├── sender.py             # Email delivery
│   └── scheduler.py          # Daily scheduling logic
├── config/
│   │   ├── sources.yaml           # RSS feeds and API endpoints
│   │   └── topics.yaml            # Topic keywords and weights
├── tests/
│   ├── test_aggregator.py
│   ├── test_filter.py
│   └── test_summarizer.py
└── logs/
    └── news_agent.log
```

## Coding Standards

### Python Style

- **PEP 8 compliant**: Use `black` for formatting, `flake8` for linting
- **Type hints**: All function signatures must include type hints
- **Docstrings**: Google-style docstrings for all functions and classes
- **Error handling**: Always use try-except blocks for external API calls and file operations
- **Logging**: Use Python's `logging` module, not print statements

### Example Function Signature

```python
def fetch_rss_feed(feed_url: str, max_articles: int = 50) -> list[dict[str, str]]:
    """
    Fetch articles from an RSS feed.
    
    Args:
        feed_url: URL of the RSS feed to parse
        max_articles: Maximum number of articles to return
        
    Returns:
        List of article dictionaries with keys: title, link, summary, published
        
    Raises:
        requests.RequestException: If feed cannot be fetched
    """
    pass
```

### Configuration Management

- **All configurable values** (RSS feeds, keywords, API keys) go in `config/` YAML files or `.env`
- **Never hardcode** URLs, API keys, or topic lists in Python files
- Use `pydantic` for config validation if config grows complex

### Testing

- Write tests for all core functions (aggregation, filtering, summarization)
- Use `pytest` as the test framework
- Mock external API calls in tests using `pytest-mock` or `responses`
- Aim for >80% code coverage

### Dependencies

- Keep `requirements.txt` minimal and pinned to specific versions
- Document why each dependency is needed in comments
- Prefer standard library solutions when possible

## Architecture Decisions

### Why Local AI (Ollama/Llama) vs API?

- **Cost**: $0 vs $5-10/month for Claude/OpenAI API
- **Privacy**: News preferences stay local
- **Speed**: Acceptable for batch processing (50 articles in 2-5 minutes on M4 Pro)
- **Tradeoff**: Slightly lower quality summaries than Claude API, but good enough for this use case

### Why RSS Feeds vs Web Scraping?

- **Reliability**: RSS feeds are structured and less likely to break
- **Ethics**: RSS is intended for programmatic access
- **Performance**: Much faster than scraping HTML
- **Maintenance**: No need to update selectors when sites change

### Email Delivery Options

1. **Gmail SMTP** (recommended for personal use):
    - Free, reliable
    - Requires app-specific password (not regular Gmail password)
    - Limit: ~500 emails/day (more than enough)

2. **SendGrid** (alternative):
    - Free tier: 100 emails/day
    - More features (templates, analytics)
    - Requires API key

### Scheduling Options

1. **Local cron job** (simplest):
   ```bash
   # Add to crontab: Run at 7:00 AM daily
   0 7 * * * cd /path/to/news-agent && /path/to/python src/scheduler.py
   ```

2. **GitHub Actions** (cloud-based):
    - Runs even if laptop is off
    - Free tier: 2,000 minutes/month
    - Requires pushing code to GitHub

## Common Commands

### Development

```bash
# Run the aggregator once (for testing)
python src/aggregator.py

# Test AI summarization
python src/summarizer.py --test

# Generate and preview digest without sending
python src/scheduler.py --dry-run

# Send digest immediately (for testing)
python src/scheduler.py --send-now

# Run all tests
pytest tests/

# Format code
black src/

# Lint code
flake8 src/
```

### Deployment

```bash
# Add to crontab for daily 7 AM execution
crontab -e
# Add line: 0 7 * * * cd /path/to/news-agent && /usr/local/bin/python3 src/scheduler.py

# View cron logs
tail -f logs/news_agent.log
```

## Data Flow

```
1. AGGREGATE (aggregator.py)
   ├─ Fetch RSS feeds from config/sources.yaml
   ├─ Fetch from NewsAPI (if configured)
   └─ Return raw articles (title, link, summary, source, published)

2. FILTER (filter.py)
   ├─ Score each article for relevance (1-10)
   ├─ Use keyword matching from config/topics.yaml
   ├─ Deduplicate similar articles
   └─ Return articles with score ≥ 6

3. SUMMARIZE (summarizer.py)
   ├─ Group articles by topic category
   ├─ For each article, call Ollama API with prompt
   ├─ Generate 2-3 sentence summary
   └─ Return enriched articles with AI summaries

4. FORMAT (formatter.py)
   ├─ Build Markdown digest using template
   ├─ Convert to HTML for email
   ├─ Add CSS styling
   └─ Return formatted email body

5. SEND (sender.py)
   ├─ Connect to SMTP server or SendGrid API
   ├─ Send digest to EMAIL_RECIPIENT
   └─ Log success/failure
```

## Prompt Engineering for Ollama

### System Prompt for Summarization

The AI receives this context before each article:

```
You are a news curation assistant. Summarize articles concisely while preserving key facts and implications. Follow these rules:

1. Write 2-3 sentences maximum
2. Use active voice, present tense
3. Focus on "what happened" and "why it matters"
4. No marketing language or hype
5. Highlight specific numbers, dates, and names
6. Flag speculation vs confirmed facts

Example:
Input: [long article about GPT-5 release]
Output: OpenAI launched GPT-5 with enhanced reasoning capabilities, showing 40% improvement on math and coding benchmarks. The model uses chain-of-thought processing visible to users. API pricing starts at $20/month.
```

### Relevance Scoring Prompt

For filtering, we use keyword matching rather than AI to save compute time. If you want AI-based filtering:

```
Rate this article's relevance to [TOPIC] on a scale of 1-10. Consider:
- Direct relevance to the topic (40%)
- Timeliness and actionability (30%)
- Information quality and newness (20%)
- Alignment with user interests (10%)

Return only a single integer score with no explanation.
```

## Configuration Files

### config/sources.yaml

```yaml
rss_feeds:
  ai:
    - https://www.theverge.com/ai-artificial-intelligence/rss/index.xml
    - https://techcrunch.com/tag/artificial-intelligence/feed/
  software:
    - https://news.ycombinator.com/rss
    - https://github.blog/feed/
  finance:
    - https://www.reuters.com/business/finance/rss
    - https://www.bloomberg.com/feed/podcast/markets.rss
  politics:
    - https://www.reuters.com/politics/rss
  nba:
    - https://www.espn.com/espn/rss/nba/news
  health:
    - https://www.nature.com/nature.rss

news_api:
  enabled: false  # Set to true if you have API key
  queries:
    - "artificial intelligence"
    - "startup funding"
    - "NBA trades"
```

### config/topics.yaml

```yaml
topics:
  ai:
    keywords:
      - artificial intelligence
      - machine learning
      - GPT
      - LLM
      - neural network
      - deep learning
    weight: 1.5  # Boost AI articles

  software:
    keywords:
      - programming
      - software development
      - framework
      - open source
      - API
    weight: 1.2

  investment:
    keywords:
      - startup
      - funding
      - venture capital
      - IPO
      - stock market
      - cryptocurrency
    weight: 1.3

  # ... similar for other topics
```

## Error Handling

### Common Issues

**Ollama connection fails**:

```bash
# Check if Ollama is running
ollama list

# Restart Ollama
pkill ollama
ollama serve
```

**RSS feed returns 403/403**:

- Some feeds block programmatic access
- Add User-Agent header: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)`
- Consider removing problematic feeds from sources.yaml

**Gmail SMTP fails**:

- Ensure 2FA is enabled on Gmail account
- Generate app-specific password (not regular password)
- Use port 587 for TLS, not 465

**Too many/too few articles**:

- Adjust relevance threshold in filter.py (default: 6/10)
- Modify max_articles in sources.yaml
- Refine keywords in topics.yaml

## Workflow Guidelines

### Adding a New News Source

1. Find RSS feed URL (usually /rss or /feed)
2. Test it manually: `curl [feed_url]`
3. Add to `config/sources.yaml` under appropriate topic
4. Run aggregator to test: `python src/aggregator.py`
5. Review output, adjust if needed

### Adding a New Topic

1. Add topic section to `config/topics.yaml` with keywords
2. Update topic list in `src/filter.py` (if using enum)
3. Add topic emoji/header to `src/formatter.py` template
4. Test end-to-end: `python src/scheduler.py --dry-run`

### Tuning Summary Quality

If summaries are too short/long/off-topic:

1. Edit system prompt in `src/summarizer.py`
2. Test with single article: `python src/summarizer.py --test`
3. Iterate on prompt wording
4. Consider upgrading model (llama3.1:8b → llama3.3:70b)

### Debugging

```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
python src/scheduler.py --dry-run

# Check what articles were fetched
cat logs/news_agent.log | grep "Fetched"

# See which articles passed filtering
cat logs/news_agent.log | grep "Filtered"

# Test email sending in isolation
python src/sender.py --test
```

## Performance Optimization

### Current Performance (M4 Pro with 48GB RAM)

- Fetch 200 articles from RSS: ~5 seconds
- Filter to ~50 relevant: <1 second
- Summarize 50 articles with Llama 8B: ~2-5 minutes
- Format and send email: <1 second
- **Total: ~3-6 minutes**

### If Too Slow

1. Reduce max_articles in sources.yaml
2. Increase relevance threshold (fewer articles to summarize)
3. Use smaller model (llama3.2:3b is 3x faster)
4. Parallelize summarization (use multiprocessing)

### If Too Fast/Missing News

1. Add more RSS feeds
2. Lower relevance threshold
3. Enable NewsAPI in sources.yaml

## Security Considerations

- **Never commit `.env` file** (contains API keys)
- Add `.env` to `.gitignore`
- Use environment variables for all secrets
- If using SendGrid, rotate API key every 90 days
- For Gmail, use app-specific password (revoke if compromised)
- RSS feeds are public data, no auth needed

## Deployment Checklist

Before setting up daily automation:

- [ ] Test aggregator: `python src/aggregator.py`
- [ ] Test filter: `python src/filter.py`
- [ ] Test summarizer: `python src/summarizer.py --test`
- [ ] Test email sending: `python src/sender.py --test`
- [ ] Verify Ollama is running: `ollama list`
- [ ] Run full pipeline: `python src/scheduler.py --dry-run`
- [ ] Check digest in preview (don't send yet)
- [ ] Send test digest: `python src/scheduler.py --send-now`
- [ ] Confirm email received and looks good
- [ ] Set up cron job or GitHub Action
- [ ] Monitor logs for first 3 days: `tail -f logs/news_agent.log`

## Future Enhancements

Ideas for v2 (not in current scope):

- Web UI to preview/customize digest before sending
- User feedback loop (rate articles to improve filtering)
- Multi-user support (different digests for different people)
- Slack/Discord delivery option
- Mobile push notifications for breaking news
- Historical archive of past digests
- Analytics dashboard (most-read topics, click-through rates)

## Getting Help

If Claude encounters unclear requirements:

1. Run tests first to understand current behavior
2. Check logs for error messages
3. Review configuration files for relevant settings
4. Test isolated components before full pipeline

If Claude needs to make architectural decisions:

- Prioritize simplicity and maintainability
- Prefer standard library over external dependencies
- Document tradeoffs in code comments
- Ask user for clarification on:
    - Performance vs quality tradeoffs
    - Cost constraints (API vs local)
    - Deployment environment (local vs cloud)

## Notes for Claude

- The user has an M4 Pro MacBook with 48GB RAM, so local AI is very feasible
- User wants $0 operating cost if possible (hence local Llama over API)
- Focus on reliability over fancy features
- Daily digest should take <10 minutes to generate
- Keep code modular so user can swap components (e.g., email → Slack)
- User is technical but not an ML expert, so use clear abstractions for AI parts

---

**Last Updated**: 2026-01-30  
**Version**: 1.0  
**Maintainer**: User