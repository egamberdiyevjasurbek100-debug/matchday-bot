import asyncio
import time
import aiohttp
import logging
from datetime import datetime
from config import API_BASE_URL, API_FOOTBALL_KEY

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

_cache = {}


def _cache_get(key, ttl):
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None


def _cache_set(key, value):
    _cache[key] = (time.time(), value)


async def _get(endpoint: str, params: dict, ttl: int = 300):
    key = (endpoint, tuple(sorted(params.items())))
    cached = _cache_get(key, ttl)
    if cached is not None:
        return cached

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(
            f"{API_BASE_URL}/{endpoint}",
            params=params,
        ) as resp:
            data = await resp.json()
            errors = data.get("errors")
            if errors:
                logging.error(
                    f"API_FOOTBALL errors: endpoint={endpoint} "
                    f"params={params} errors={errors}"
                )
            result = data.get("response", [])
            _cache_set(key, result)
            return result


async def _get_with_season_fallback(
    endpoint: str,
    league_id: int,
    season: int,
    extra_params: dict = None,
    years_back: int = 5,
    ttl: int = 3600,
):
    extra_params = extra_params or {}
    for offset in range(years_back):
        yr = season - offset
        params = {
            "league": league_id,
            "season": yr,
        }
        params.update(extra_params)
        data = await _get(endpoint, params, ttl=ttl)
        if data:
            return data
        await asyncio.sleep(0.5)
    return []


async def get_live_fixtures():
    params = {
        "live": "all",
        "timezone": "Asia/Tashkent",
    }
    return await _get("fixtures", params, ttl=60)


async def get_fixtures_by_date(date_str: str):
    params = {
        "date": date_str,
        "timezone": "Asia/Tashkent",
    }
    return await _get("fixtures", params, ttl=600)


async def get_upcoming_fixtures(league_id: int, season: int, count: int = 8):
    extra = {
        "next": count,
        "timezone": "Asia/Tashkent",
    }
    return await _get_with_season_fallback(
        "fixtures",
        league_id,
        season,
        extra,
        ttl=1800,
    )


async def get_current_season(league_id: int) -> int:
    data = await _get("leagues", {"id": league_id}, ttl=86400)
    if data:
        seasons = data[0].get("seasons", [])
        for season in seasons:
            if season.get("current"):
                return season["year"]
        if seasons:
            return seasons[-1]["year"]
    return datetime.now().year


async def get_standings(league_id: int, season: int):
    data = await _get_with_season_fallback("standings", league_id, season, ttl=3600)
    if data:
        try:
            return data[0]["league"]["standings"][0]
        except (KeyError, IndexError):
            return []
    return []


async def get_top_scorers(league_id: int, season: int):
    return await _get_with_season_fallback(
        "players/topscorers",
        league_id,
        season,
        ttl=3600,
    )


async def get_top_assists(league_id: int, season: int):
    return await _get_with_season_fallback(
        "players/topassists",
        league_id,
        season,
        ttl=3600,
    )


async def get_teams_by_league(league_id: int, season: int):
    return await _get_with_season_fallback(
        "teams", league_id, season, ttl=86400
    )


async def get_upcoming_fixtures_for_team(team_id: int, count: int = 1):
    params = {
        "team": team_id,
        "next": count,
        "timezone": "Asia/Tashkent",
    }
    return await _get("fixtures", params, ttl=3600)
