import aiohttp
import logging
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
            data = await resp.json()
            logging.error(f"DEBUG get_favorites: status={resp.status} type={type(data)} data={data}")
            if not isinstance(data, list):
                return []
            return [item for item in data if isinstance(item, dict)]


async def get_all_favorites():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(REST_URL, params={"select": "*"}) as resp:
            data = await resp.json()
            if not isinstance(data, list):
                logging.error(f"SUPABASE get_all_favorites xato: status={resp.status} javob={data}")
                return []
            return [item for item in data if isinstance(item, dict)]


async def add_favorite(user_id: int, team_id: int, team_name: str):
    body = {"user_id": user_id, "team_id": team_id, "team_name": team_name, "notified_fixtures": ""}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.post(REST_URL, json=body) as resp:
            data = await resp.json()
            if resp.status not in (200, 201):
                logging.error(f"SUPABASE add_favorite xato: status={resp.status} javob={data}")
            return data


async def remove_favorite(user_id: int, team_id: int):
    params = {"user_id": f"eq.{user_id}", "team_id": f"eq.{team_id}"}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.delete(REST_URL, params=params) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                logging.error(f"SUPABASE remove_favorite xato: status={resp.status} javob={text}")
            return resp.status


async def mark_notified(row_id: int, notified_fixtures: str):
    params = {"id": f"eq.{row_id}"}
    body = {"notified_fixtures": notified_fixtures}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.patch(REST_URL, params=params, json=body) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                logging.error(f"SUPABASE mark_notified xato: status={resp.status} javob={text}")
            return resp.status
