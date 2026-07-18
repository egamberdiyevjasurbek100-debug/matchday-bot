import aiohttp
from config import SUPABASE_URL, SUPABASE_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

REST_URL = f"{SUPABASE_URL}/rest/v1/favorites"


async def get_favorites(user_id: int):
    params = {"user_id": f"eq.{user_id}", "select": "*"}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(REST_URL, params=params) as resp:
            return await resp.json()


async def get_all_favorites():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(REST_URL, params={"select": "*"}) as resp:
            return await resp.json()


async def add_favorite(user_id: int, team_id: int, team_name: str):
    body = {"user_id": user_id, "team_id": team_id, "team_name": team_name, "notified_fixtures": ""}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.post(REST_URL, json=body) as resp:
            return await resp.json()


async def remove_favorite(user_id: int, team_id: int):
    params = {"user_id": f"eq.{user_id}", "team_id": f"eq.{team_id}"}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.delete(REST_URL, params=params) as resp:
            return resp.status


async def mark_notified(row_id: int, notified_fixtures: str):
    params = {"id": f"eq.{row_id}"}
    body = {"notified_fixtures": notified_fixtures}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.patch(REST_URL, params=params, json=body) as resp:
            return resp.status
