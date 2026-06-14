"""Ollama HTTP client — thin wrapper for local LLM inference.

Ollama exposes a REST API at http://localhost:11434. Two endpoints matter:

  POST /api/generate   — raw text completion (simpler, faster)
  POST /api/chat       — chat-style with system/user/assistant messages

We use /api/chat because it lets us separate system prompt (agent persona)
from user content (the data). This maps cleanly to our two-agent design:
the Analyst gets one system prompt, the Voice gets another.

Key design decisions:
  - Timeout: 60s per call. A 3B model on Pi 5 does ~15-20 tok/s.
    At ~150 tokens output, that's 8-10s. 60s gives headroom.
  - Graceful failure: returns None on any error. Callers fall back
    to rule-based output. The LLM is a bonus, never a dependency.
  - No streaming: we run this in background jobs, not on page load.
    We want the complete response, not partial tokens.
  - No LangChain: direct HTTP. One dependency (requests), zero magic.

Ollama API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Default Ollama endpoint — override via OLLAMA_BASE_URL env var
DEFAULT_BASE_URL = "http://localhost:11434"

# Default model — Ministral 3B quantized fits in 4GB RAM
DEFAULT_MODEL = "ministral-3b"

# Request timeout in seconds
TIMEOUT = 60


class OllamaClient:
    """Minimal Ollama HTTP client.

    Usage:
        client = OllamaClient()
        response = client.chat(
            system="You are a health data analyst.",
            prompt="Here is the user's data: {data}",
        )
        if response:
            print(response)  # The model's text output
        else:
            print("Ollama unavailable, using fallback")
    """

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL

    def is_available(self) -> bool:
        """Check if Ollama is running and the model is loaded.

        Quick health check — useful before committing to a multi-step
        analysis pipeline. Returns False on any error.
        """
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = resp.json().get("models", [])
            # Check if our model (or a close match) is available
            model_base = self.model.split(":")[0]
            return any(model_base in m.get("name", "") for m in models)
        except Exception:
            return False

    def chat(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> Optional[str]:
        """Send a chat request and return the model's response text.

        Args:
            system:      System prompt — defines the agent's role and behavior.
            prompt:      User message — the actual data/question.
            temperature: 0.0 = deterministic, 1.0 = creative. Default 0.7.
            max_tokens:  Maximum response length. Keep short for Pi performance.

        Returns:
            The model's response text, or None if anything fails.
            None means "fall back to rule-based" — never crash the app.

        Technical note on the Ollama /api/chat endpoint:
            - stream: false  → returns complete response in one JSON object
            - The response JSON has: {"message": {"content": "..."}, ...}
            - options.num_predict controls max output tokens
            - options.temperature controls randomness
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=TIMEOUT,
            )

            if resp.status_code != 200:
                logger.warning(
                    f"Ollama returned {resp.status_code}: {resp.text[:200]}"
                )
                return None

            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()

            if not content:
                logger.warning("Ollama returned empty content")
                return None

            # Log performance for tuning
            eval_duration = data.get("eval_duration", 0)  # nanoseconds
            eval_count = data.get("eval_count", 0)
            if eval_duration > 0 and eval_count > 0:
                tok_per_sec = eval_count / (eval_duration / 1e9)
                logger.info(
                    f"Ollama: {eval_count} tokens in {eval_duration/1e9:.1f}s "
                    f"({tok_per_sec:.1f} tok/s)"
                )

            return content

        except requests.Timeout:
            logger.warning(f"Ollama timed out after {TIMEOUT}s")
            return None
        except requests.ConnectionError:
            logger.info("Ollama not running — using rule-based fallback")
            return None
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return None

    def chat_json(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 500,
    ) -> Optional[dict]:
        """Chat request that expects JSON output.

        Same as chat(), but:
          - Adds "format": "json" to tell Ollama to constrain output
          - Uses lower temperature (0.3) for more deterministic structure
          - Parses the response as JSON, returns None on parse failure

        Used by the Analyst agent, which outputs structured insights.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=TIMEOUT,
            )

            if resp.status_code != 200:
                logger.warning(
                    f"Ollama returned {resp.status_code}: {resp.text[:200]}"
                )
                return None

            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()

            if not content:
                return None

            import json
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.warning(f"Ollama returned invalid JSON: {content[:200]}")
                return None

        except requests.Timeout:
            logger.warning(f"Ollama JSON request timed out after {TIMEOUT}s")
            return None
        except requests.ConnectionError:
            logger.info("Ollama not running — using rule-based fallback")
            return None
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return None
