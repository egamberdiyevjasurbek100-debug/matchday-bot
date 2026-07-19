import aiohttp
import logging
from datetime import datetime
from config import API_BASE_URL, API_FOOTBALL_KEY

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}


async def _get(endpoint: str, params: dict):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(f"{API_BASE_URL}/{endpoint}", params=params) as resp:
            data = await resp.json()
            errors = data.get("errors")
            if errors:
                logging.error(f"API_FOOTBALL errors: endpoint={endpoint} params={params} errors={errors}")
            return data.get("response", [])


async def _get_with_season_fallback(endpoint: str, league_id: int, season: int, extra_params: dict = None, years_back: int = 5):
    extra_params = extra_params or {}
    for offset in range(years_back):
        yr = season - offset
        params = {"league": league_id, "season": yr, **extra_params}
        data = await _get(endpoint, params)
        if data:
            return data
    return []


async def get_live_fixtures():
    return await _get("fixtures", {"live": "all", "timezone": "Asia/Tashkent"})


async def get_fixtures_by_date(date_str: str):
    return await _get("fixtures", {"date": date_str, "timezone": "Asia/Tashkent"})


async def get_upcoming_fixtures(league_id: int, season: int, count: int = 8):
    return await _get_with_season_fallback("fixtures", league_id, season, {"next": count, "time
