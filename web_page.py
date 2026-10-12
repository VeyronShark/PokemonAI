import requests
from bs4 import BeautifulSoup


def fetch_web_page(url: str):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=10
    )

    response.raise_for_status()

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

    return {
        "url": url,
        "content": text
    }