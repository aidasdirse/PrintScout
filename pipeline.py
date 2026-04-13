import os
import asyncio
import aiohttp
import json
import time
from datetime import datetime
import database

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EBAY_APP_ID = os.environ.get("EBAY_APP_ID", "")
ETSY_API_KEY = os.environ.get("ETSY_API_KEY", "")

REDDIT_SUBREDDITS = [
    "3Dprinting", "ender3", "resinprinting", "FDMprinting",
    "Etsy", "smallbusiness", "sidehustle", "passive_income"
]

HEADERS = {"User-Agent": "PrintScout/1.0 (market research bot)"}

# ─── Reddit ────────────────────────────────────────────────────────────────────

async def fetch_reddit(session: aiohttp.ClientSession, subreddit: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=50"
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            posts = data.get("data", {}).get("children", [])
            return [
                {
                    "title": p["data"].get("title", ""),
                    "selftext": p["data"].get("selftext", "")[:300],
                    "score": p["data"].get("score", 0),
                    "subreddit": subreddit,
                }
                for p in posts
            ]
    except Exception as e:
        print(f"Reddit fetch failed for r/{subreddit}: {e}")
        return []

async def scrape_reddit(session: aiohttp.ClientSession) -> list[dict]:
    tasks = [fetch_reddit(session, sub) for sub in REDDIT_SUBREDDITS]
    results = await asyncio.gather(*tasks)
    all_posts = []
    for posts in results:
        all_posts.extend(posts)
    return all_posts

# ─── Claude ────────────────────────────────────────────────────────────────────

async def extract_keywords(session: aiohttp.ClientSession, posts: list[dict]) -> list[str]:
    sample = posts[:80]
    text = "\n".join(f"- [{p['subreddit']}] {p['title']}" for p in sample)

    prompt = f"""You are a 3D printing business analyst. Below are Reddit posts from 3D printing and entrepreneurship communities.

Extract the top 12 most promising 3D-printable product keywords/niches mentioned or implied. Focus on things people are asking for, complaining about not finding, or selling successfully.

Reddit posts:
{text}

Respond ONLY with a JSON array of 12 keyword strings. Short, specific, sellable. No markdown.
Example: ["cable organizer", "D&D miniatures", "custom phone stand"]"""

    try:
        async with session.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            data = await resp.json()
            text_out = data["content"][0]["text"].strip()
            clean = text_out.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
    except Exception as e:
        print(f"Keyword extraction failed: {e}")
        return ["desk organizer", "cable clip", "phone stand", "wall planter",
                "D&D miniatures", "pet portrait", "custom keychain", "cable management"]

async def analyze_keyword(session: aiohttp.ClientSession, keyword: str, market_data: dict) -> dict:
    prompt = f"""You are a 3D printing market research analyst.

Keyword: "{keyword}"
Market data gathered:
- eBay avg sold price: ${market_data.get('ebay_avg_price', 'unknown')}
- Etsy listing count: {market_data.get('etsy_listing_count', 'unknown')}
- Google Trends score (0-100): {market_data.get('google_trend_score', 'unknown')}
- Reddit mentions this scan: {market_data.get('reddit_mentions', 0)}

Respond ONLY with a JSON object (no markdown):
{{
  "opportunity_score": <0-100>,
  "demand_score": <0-100>,
  "competition_score": <0-100, higher=worse>,
  "trend": "up"|"flat"|"down",
  "trend_note": "<one sentence>",
  "avg_price_low": <USD number>,
  "avg_price_high": <USD number>,
  "margin_estimate": "low"|"medium"|"high",
  "platform_scores": [{{"label":"Etsy","value":80}}, ...],
  "top_search_terms": ["<term1>", ...5 terms],
  "why_buy": ["<reason1>", "<reason2>", "<reason3>"],
  "pitfalls": ["<pitfall1>", "<pitfall2>", "<pitfall3>"],
  "tips": ["<tip1>", "<tip2>", "<tip3>"],
  "related_niches": ["<niche1>", "<niche2>", "<niche3>", "<niche4>"]
}}"""

    try:
        async with session.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 800,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            data = await resp.json()
            text_out = data["content"][0]["text"].strip()
            clean = text_out.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
    except Exception as e:
        print(f"Analysis failed for {keyword}: {e}")
        return {}

# ─── eBay ──────────────────────────────────────────────────────────────────────

async def fetch_ebay(session: aiohttp.ClientSession, keyword: str) -> dict:
    if not EBAY_APP_ID:
        return {"ebay_avg_price": None}
    url = (
        f"https://svcs.ebay.com/services/search/FindingService/v1"
        f"?OPERATION-NAME=findCompletedItems"
        f"&SERVICE-VERSION=1.0.0"
        f"&SECURITY-APPNAME={EBAY_APP_ID}"
        f"&RESPONSE-DATA-FORMAT=JSON"
        f"&keywords={keyword.replace(' ', '+')}"
        f"&itemFilter(0).name=SoldItemsOnly&itemFilter(0).value=true"
        f"&paginationInput.entriesPerPage=20"
    )
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json(content_type=None)
            items = (data.get("findCompletedItemsResponse", [{}])[0]
                        .get("searchResult", [{}])[0]
                        .get("item", []))
            prices = []
            for item in items:
                try:
                    price = float(item["sellingStatus"][0]["convertedCurrentPrice"][0]["__value__"])
                    prices.append(price)
                except:
                    pass
            avg = round(sum(prices) / len(prices), 2) if prices else None
            return {"ebay_avg_price": avg}
    except Exception as e:
        print(f"eBay fetch failed for {keyword}: {e}")
        return {"ebay_avg_price": None}

# ─── Etsy ──────────────────────────────────────────────────────────────────────

async def fetch_etsy(session: aiohttp.ClientSession, keyword: str) -> dict:
    if not ETSY_API_KEY:
        return {"etsy_listing_count": None}
    url = f"https://openapi.etsy.com/v3/application/listings/active?keywords={keyword.replace(' ', '+')}&limit=1"
    try:
        async with session.get(url, headers={"x-api-key": ETSY_API_KEY},
                               timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()
            count = data.get("count", None)
            return {"etsy_listing_count": count}
    except Exception as e:
        print(f"Etsy fetch failed for {keyword}: {e}")
        return {"etsy_listing_count": None}

# ─── Google Trends ─────────────────────────────────────────────────────────────

def fetch_google_trends(keyword: str) -> dict:
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pt.build_payload([keyword], timeframe="today 3-m")
        df = pt.interest_over_time()
        if df.empty or keyword not in df.columns:
            return {"google_trend_score": None}
        score = int(df[keyword].mean())
        return {"google_trend_score": score}
    except Exception as e:
        print(f"Google Trends failed for {keyword}: {e}")
        return {"google_trend_score": None}

# ─── Main pipeline ─────────────────────────────────────────────────────────────

async def run():
    async with aiohttp.ClientSession() as session:
        # Step 1: Scrape Reddit
        database.set_status("running", "Scanning Reddit communities...")
        posts = await scrape_reddit(session)
        print(f"Fetched {len(posts)} Reddit posts")

        # Step 2: Extract keywords via Claude
        database.set_status("running", "Extracting trending product keywords...")
        keywords = await extract_keywords(session, posts)
        print(f"Keywords: {keywords}")

        # Count Reddit mentions per keyword
        all_text = " ".join(p["title"].lower() + " " + p["selftext"].lower() for p in posts)
        mention_counts = {kw: all_text.count(kw.lower()) for kw in keywords}

        # Step 3: For each keyword, gather market data in parallel
        database.set_status("running", f"Gathering market data for {len(keywords)} keywords...")

        async def gather_market_data(kw):
            ebay_data, etsy_data = await asyncio.gather(
                fetch_ebay(session, kw),
                fetch_etsy(session, kw)
            )
            trend_data = await asyncio.get_event_loop().run_in_executor(
                None, fetch_google_trends, kw
            )
            return {
                **ebay_data,
                **etsy_data,
                **trend_data,
                "reddit_mentions": mention_counts.get(kw, 0)
            }

        market_results = await asyncio.gather(*[gather_market_data(kw) for kw in keywords])

        # Step 4: Analyze each keyword with Claude
        database.set_status("running", "Scoring opportunities with AI...")
        for i, (kw, market_data) in enumerate(zip(keywords, market_results)):
            database.set_status("running", f"Analyzing {i+1}/{len(keywords)}: {kw}...")
            analysis = await analyze_keyword(session, kw, market_data)
            if analysis:
                combined = {
                    "keyword": kw,
                    **market_data,
                    **analysis,
                    "sources": ["Reddit", "eBay", "Etsy", "Google Trends"]
                }
                database.upsert_opportunity(combined)
            await asyncio.sleep(0.5)  # gentle rate limiting

        print(f"Pipeline complete. Processed {len(keywords)} keywords.")
