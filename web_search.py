import logging
from time import perf_counter

from ddgs import DDGS

logger = logging.getLogger("pokemonai.web_search")


def web_search(query: str):
    started_at = perf_counter()
    logger.info("Web search started result_limit=5")

    try:
        results = DDGS().text(
            query,
            max_results=5
        )
    except Exception:
        logger.exception(
            "Web search failed duration_ms=%.1f",
            (perf_counter() - started_at) * 1000,
        )
        raise

    formatted_results = [
        {
            "title": result["title"],
            "url": result["href"],
            "snippet": result["body"]
        }
        for result in results
    ]
    logger.info(
        "Web search completed result_count=%d duration_ms=%.1f",
        len(formatted_results),
        (perf_counter() - started_at) * 1000,
    )
    return formatted_results