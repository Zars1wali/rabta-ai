import urllib.request
import urllib.parse
import html
import re
import logging

logger = logging.getLogger(__name__)

async def search_product_specs(product_name: str, query: str = "") -> str:
    """
    Search official manufacturer specs for a confirmed catalog item.
    Scoped ONLY to manufacturer specifications and official facts.
    """
    if not product_name:
        return ""

    search_term = f"{product_name} {query} specifications".strip()
    encoded = urllib.parse.quote(search_term)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&utf8=&format=json"
    
    headers = {
        "User-Agent": "RabtaAI-CatalogSpecLookup/1.0 (info@haiderarms.pk)"
    }
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        def _fetch():
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                import json
                data = json.loads(response.read().decode("utf-8", errors="ignore"))
                results = data.get("query", {}).get("search", [])
                clean_snippets = []
                for r in results[:3]:
                    snip = r.get("snippet", "")
                    clean_text = html.unescape(re.sub(r'<[^>]+>', '', snip)).strip()
                    if clean_text:
                        clean_snippets.append(clean_text)
                return " ".join(clean_snippets)
                
        text = await loop.run_in_executor(None, _fetch)
        return text.strip()
    except Exception as e:
        logger.warning(f"Spec lookup for {product_name} failed: {e}")
        return ""

if __name__ == "__main__":
    import asyncio, sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    async def main():
        res = await search_product_specs("Smith & Wesson 1911", "barrel length weight")
        print("SPEC RESULT:", res[:300])
    asyncio.run(main())
