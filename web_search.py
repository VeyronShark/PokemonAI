from ddgs import DDGS


def web_search(query: str):

    results = DDGS().text(
        query,
        max_results=5
    )

    return [
        {
            "title": result["title"],
            "url": result["href"],
            "snippet": result["body"]
        }
        for result in results
    ]