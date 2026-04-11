"""SerpAPI wrapper for web searches.

Used by the company research agent to find news, funding info, and layoff
history. Gracefully returns empty results if SERPAPI_KEY is not configured
so the research agent works (at reduced quality) without an API key.
"""

from config import settings


def search_web(query: str, num_results: int = 5) -> list[dict]:
    """Search the web via SerpAPI and return structured results.

    Args:
        query: Search query string.
        num_results: Max number of results to return.

    Returns:
        List of {title, url, snippet} dicts. Empty list if key not configured
        or if the search fails.
    """
    if not settings.serpapi_key:
        return []

    try:
        from serpapi import GoogleSearch
    except ImportError:
        try:
            from serpapi.google_search import GoogleSearch
        except ImportError:
            return []

    try:
        params = {
            "q": query,
            "api_key": settings.serpapi_key,
            "num": num_results,
            "hl": "en",
            "gl": "us",
        }
        results = GoogleSearch(params).get_dict()
        organic = results.get("organic_results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in organic[:num_results]
            if r.get("title") and r.get("link")
        ]
    except Exception:
        return []
