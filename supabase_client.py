import aiohttp
import logging
from config import SUPABASE_URL, SUPABASE_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

_clean_url = SUPABASE_URL.rstrip("/") if SUPABASE_URL else ""
_clean_url = _clean_url.removesuffix("/rest/v1")
REST_URL = f"{_clean_url}/rest/v1/favorites"
USERS_URL = f"{_clean_url}/rest/v1/users"


async def get_favorites(user_id: int):
    params = {
        "user_id": f"eq.{user_id}",
        "select": "*",
    }
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(REST_URL, params=params) as resp:
            data = await resp.json()
            if not isinstance(data, list):
                logging.error(
                    f"SUPABASE get_favorites xato: "
                    f"status={resp.status} javob={data}"
                )
                return []
            return [item for item in data if isinstance(item, dict)]


async def get_all_favorites():
    params = {"select": "*"}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(REST_URL, params=params) as resp:
            data = await resp.json()
            if not isinstance(data, list):
                logging.error(
                    f"SUPABASE get_all_favorites xato: "
                    f"status={resp.status} javob={data}"
                )
                return []
            return [item for item in data if isinstance(item, dict)]


async def add_favorite(user_id: int, team_id: int, team_name: str):
    body = {
        "user_id": user_id,
        "team_id": team_id,
        "team_name": team_name,
        "notified_fixtures": "",
    }
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.post(REST_URL, json=body) as resp:
            data = await resp.json()
            if resp.status not in (200, 201):
                logging.error(
                    f"SUPABASE add_favorite xato: "
                    f"status={resp.status} javob={data}"
                )
            return data


async def remove_favorite(user_id: int, team_id: int):
    params = {
        "user_id": f"eq.{user_id}",
        "team_id": f"eq.{team_id}",
    }
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.delete(REST_URL, params=params) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                logging.error(
                    f"SUPABASE remove_favorite xato: "
                    f"status={resp.status} javob={text}"
                )
            return resp.status


async def mark_notified(row_id: int, notified_fixtures: str):
    params = {"id": f"eq.{row_id}"}
    body = {"notified_fixtures": notified_fixtures}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.patch(
            REST_URL, params=params, json=body
        ) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                logging.error(
                    f"SUPABASE mark_notified xato: "
                    f"status={resp.status} javob={text}"
                )
            return resp.status


async def get_user_language(user_id: int):
    params = {
        "user_id": f"eq.{user_id}",
        "select": "language",
    }
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(USERS_URL, params=params) as resp:
            data = await resp.json()
            if isinstance(data, list) and data:
                return data[0].get("language")
    return None


async def set_user_language(user_id: int, language: str):
    params = {"user_id": f"eq.{user_id}"}
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(USERS_URL, params=params) as resp:
            existing = await resp.json()

        if isinstance(existing, list) and existing:
            body = {"language": language}
            async with session.patch(
                USERS_URL, params=params, json=body
            ) as resp2:
                return resp2.status

        body = {"user_id": user_id, "language": language}
        async with session.post(USERS_URL, json=body) as resp3:
            return resp3.status
