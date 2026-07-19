import aiohttp
import logging
from datetime import datetime
from config import API_BASE_URL, API_FOOTBALL_KEY

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}


async def _get(endpoint: str, params: dict):
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
            return data.get("response", [])


async def _get_with_season_fallback(
    endpoint: str,
    league_id: int,
    season: int,
    extra_params: dict = None,
    years_back: int = 5,
):
    extra_params = extra_params or {}
    for offset in range(years_back):
        yr = season - offset
        params = {
            "league": league_id,
            "season": yr,
        }
        params.update(extra_params)
        data = await _get(endpoint, params)
        if data:
            return data
    return []


async def get_live_fixtures():
    params = {
        "live": "all",
        "timezone": "Asia/Tashkent",
    }
    return await _get("fixtures", params)


async def get_fixtures_by_date(date_str: str):
    params = {
        "date": date_str,
        "timezone": "Asia/Tashkent",
    }
    return await _get("fixtures", params)


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
    )


async def get_current_season(league_id: int) -> int:
    data = await _get("leagues", {"id": league_id})
    if data:
        seasons = data[0].get("seasons", [])
        for season in seasons:
            if season.get("current"):
                return season["year"]
        if seasons:
            return seasons[-1]["year"]
    return datetime.now().year


async def get_standings(league_id: int, season: int):
    data = await _get_with_season_fallback("standings", league_id, season)
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
    )


async def get_top_assists(league_id: int, season: int):
    return await _get_with_season_fallback(
        "players/topassists",
        league_id,
        season,
    )


async def get_teams_by_league(league_id: int, season: int):
    return await _get_with_season_fallback("teams", league_id, season)


async def get_upcoming_fixtures_for_team(team_id: int, count: int = 1):
    params = {
        "team": team_id,
        "next": count,
        "timezone": "Asia/Tashkent",
    }
    return await _get("fixtures", params)
