"""
Ollama LLM tools for article scoring and summarization.

Uses local Ollama with Llama 3.1 8B for $0 cost operation.
"""

import json
import logging
import re
from pathlib import Path

import yaml
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# Default model configuration
DEFAULT_MODEL = "llama3.1:8b"
OLLAMA_BASE_URL = "http://localhost:11434"


def get_llm(model: str = DEFAULT_MODEL, temperature: float = 0.3) -> ChatOllama:
    """
    Get configured Ollama LLM instance.

    Args:
        model: Ollama model name.
        temperature: Sampling temperature (lower = more deterministic).

    Returns:
        Configured ChatOllama instance.
    """
    return ChatOllama(
        model=model,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
    )


def load_user_interests() -> str:
    """
    Build user interest description from topics.yaml for LLM context.

    Returns:
        Formatted string describing user's interests and priorities.
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "topics.yaml"

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("topics.yaml not found, using default interests")
        return "AI, software development, technology, business, and current events"

    topics = config.get("topics", {})

    # Sort topics by weight (higher weight = more important)
    sorted_topics = sorted(
        topics.items(),
        key=lambda x: x[1].get("weight", 1.0),
        reverse=True,
    )

    interest_parts = []
    for topic_name, topic_config in sorted_topics:
        weight = topic_config.get("weight", 1.0)
        keywords = topic_config.get("keywords", [])

        # Format based on priority
        if weight >= 1.5:
            priority = "highest priority"
        elif weight >= 1.3:
            priority = "high priority"
        elif weight >= 1.1:
            priority = "moderate priority"
        else:
            priority = "standard priority"

        # Include some example keywords for context
        keyword_sample = ", ".join(keywords[:5])
        interest_parts.append(
            f"- {topic_name.upper()} ({priority}): {keyword_sample}"
        )

    return "\n".join(interest_parts)


def parse_score_response(response_text: str) -> tuple[float, str]:
    """
    Parse LLM response to extract score and summary.

    Args:
        response_text: Raw text response from LLM.

    Returns:
        Tuple of (score, summary). Returns (0.0, "") on parse failure.
    """
    # Try JSON parsing first
    try:
        json_match = re.search(r"\{[^}]+\}", response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            score = float(data.get("score", 0))
            summary = str(data.get("summary", ""))
            return (min(score, 10), summary)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"JSON parse failed: {e}")

    # Fallback: extract from plain text
    try:
        score_match = re.search(r"score[:\s]+(\d+(?:\.\d+)?)", response_text, re.I)
        score = float(score_match.group(1)) if score_match else 0.0

        summary_match = re.search(r"summary[:\s]+(.+)", response_text, re.I | re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""

        return (min(score, 10), summary)
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        return (0.0, "")


def score_and_summarize_article(
    title: str,
    content: str,
    source: str,
    interests: str | None = None,
    llm: ChatOllama | None = None,
) -> tuple[float, str]:
    """
    Score article relevance and generate summary in one LLM call.

    Args:
        title: Article title.
        content: Article content/summary.
        source: Source name.
        interests: User interests string. If None, loads from config.
        llm: ChatOllama instance. If None, creates default.

    Returns:
        Tuple of (relevance_score 1-10, summary string).
    """
    if interests is None:
        interests = load_user_interests()

    if llm is None:
        llm = get_llm()

    system_prompt = """You are a news curator assistant. Your job is to evaluate articles for relevance and create concise summaries.

Always respond with ONLY a JSON object in this exact format:
{"score": <number 1-10>, "summary": "<2-3 sentence summary>"}

Scoring guide:
- 9-10: Directly about user's high-priority interests, breaking/important news
- 7-8: Relevant to user's interests, newsworthy
- 5-6: Tangentially related, might be interesting
- 3-4: Loosely connected to interests
- 1-2: Not relevant to user's stated interests

Summary rules:
- 2-3 sentences maximum
- Focus on key facts and why it matters
- Use active voice, present tense
- No marketing language or hype"""

    user_prompt = f"""User interests:
{interests}

ARTICLE TO EVALUATE:
Title: {title}
Source: {source}
Content: {content[:1500]}

Respond with JSON only: {{"score": N, "summary": "..."}}"""

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = llm.invoke(messages)
        response_text = response.content

        score, summary = parse_score_response(response_text)
        logger.debug(f"Scored '{title[:50]}': {score}")

        return (score, summary)

    except Exception as e:
        logger.error(f"LLM error scoring article: {e}")
        return (0.0, "")


def check_ollama_available(model: str = DEFAULT_MODEL) -> bool:
    """
    Check if Ollama is running and model is available.

    Args:
        model: Model name to check.

    Returns:
        True if available.

    Raises:
        ConnectionError: If Ollama is not available.
    """
    import requests

    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code != 200:
            raise ConnectionError(f"Ollama returned status {response.status_code}")

        models = response.json().get("models", [])
        model_names = [m.get("name", "") for m in models]

        # Check if model is available
        base_model = model.split(":")[0]
        model_found = any(base_model in name for name in model_names)

        if not model_found:
            raise ConnectionError(
                f"Model '{model}' not found. Available: {model_names}. "
                f"Run: ollama pull {model}"
            )

        return True

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Cannot connect to Ollama. Is it running? Start with: ollama serve"
        )