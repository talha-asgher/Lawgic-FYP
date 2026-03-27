from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class OllamaServiceError(Exception):
    pass


def get_ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def get_ollama_model() -> str:
    m = os.environ.get("OLLAMA_MODEL", "").strip()
    if not m:
        logger.warning("OLLAMA_MODEL is not set; set it to an Ollama model name (e.g. llama3.2)")
        raise OllamaServiceError("OLLAMA_MODEL is not set")
    return m


def get_ollama_read_timeout_sec() -> float:
    """Max time to wait for Ollama to finish generating the full /api/chat response."""
    return float(os.environ.get("OLLAMA_TIMEOUT_SEC", "600"))


def get_ollama_connect_timeout_sec() -> float:
    return float(os.environ.get("OLLAMA_CONNECT_TIMEOUT_SEC", "15"))


def get_ollama_temperature() -> float:
    return float(os.environ.get("OLLAMA_TEMPERATURE", "0.1"))


def get_ollama_top_p() -> float:
    return float(os.environ.get("OLLAMA_TOP_P", "0.9"))


def chat_completion(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    json_format: bool = False,
) -> str:
    base = get_ollama_base_url()
    model = get_ollama_model()
    url = f"{base}/api/chat"
    temp = get_ollama_temperature() if temperature is None else float(temperature)
    tp = get_ollama_top_p() if top_p is None else float(top_p)
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temp, "top_p": tp},
    }
    if json_format:
        payload["format"] = "json"
    read_s = get_ollama_read_timeout_sec()
    connect_s = get_ollama_connect_timeout_sec()
    timeout = httpx.Timeout(
        connect=connect_s,
        read=read_s,
        write=connect_s,
        pool=connect_s,
    )
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = (e.response.text or "")[:500]
        except Exception:
            pass
        err = f"Ollama HTTP {e.response.status_code} at {url}: {body or e.response.reason_phrase}"
        logger.warning("%s", err)
        raise OllamaServiceError(err) from e
    except httpx.RequestError as e:
        err = f"Ollama request failed ({url}): {e!s}"
        logger.warning("%s", err)
        raise OllamaServiceError(err) from e
    except Exception as e:
        err = f"Ollama error: {e!s}"
        logger.warning("%s", err)
        raise OllamaServiceError(err) from e

    msg = data.get("message") or {}
    content = msg.get("content")
    if not content or not str(content).strip():
        logger.warning("Ollama returned empty message.content")
        raise OllamaServiceError("Ollama returned empty content")
    return str(content).strip()
