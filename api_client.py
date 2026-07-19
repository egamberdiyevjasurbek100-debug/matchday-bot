import aiohttp
from datetime import datetime
from config import API_BASE_URL, API_FOOTBALL_KEY

HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}


async def _get(endpoint: str, params: dict):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(f"{API_BASE_URL}/{endpoint}", params=params) as resp:
            data = await resp.json()
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
    return await _get_with_season_fallback("fixtures", league_id, season, {"next": count, "timezone": "Asia/Tashkent"})


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
    return await _get_with_season_fallback("players/topscorers", league_id, season)


async def get_top_assists(league_id: int, season: int):
    return await _get_with_season_fallback("players/topassists", league_id, season)


async def get_teams_by_league(league_id: int, season: int):
    return await _get_with_season_fallback("teams", league_id, season)


async def get_upcoming_fixtures_for_team(team_id: int, count: int = 1):
    return await _get("fixtures", {"team": team_id, "next": count, "timezone": "Asia/Tashkent"})
