import logging
from time import perf_counter
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("pokemonai.web_page")


def fetch_web_page(url: str):
    started_at = perf_counter()
    host = urlparse(url).hostname or "unknown"
    logger.info("Webpage fetch started host=%s", host)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )
        logger.info("Webpage response received host=%s status=%d", host, response.status_code)
        response.raise_for_status()
    except Exception:
        logger.exception(
            "Webpage fetch failed host=%s duration_ms=%.1f",
            host,
            (perf_counter() - started_at) * 1000,
        )
        raise

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    for element in soup([
        "script",
        "style",
        "nav",
        "footer",
        "header"
    ]):
        element.decompose()

    text = soup.get_text(
        separator="\n",
        strip=True
    )

    # Limit the amount of text returned to the LLM
    text = text[:12000]
    logger.info(
        "Webpage extraction completed host=%s content_chars=%d duration_ms=%.1f",
        host,
        len(text),
        (perf_counter() - started_at) * 1000,
    )

    return {
        "url": url,
        "content": text
    }