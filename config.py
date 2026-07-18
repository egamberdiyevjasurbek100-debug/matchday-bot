import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
API_BASE_URL = "https://v3.football.api-sports.io"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

LEAGUES = {
    "epl": {"id": 39, "name": "🏴 Premier League"},
    "laliga": {"id": 140, "name": "🇪🇸 La Liga"},
    "seriea": {"id": 135, "name": "🇮🇹 Serie A"},
    "bundesliga": {"id": 78, "name": "🇩🇪 Bundesliga"},
    "ligue1": {"id": 61, "name": "🇫🇷 Ligue 1"},
    "uzbekistan": {"id": 369, "name": "🇺🇿 Superliga"},
}

ALL_LEAGUE_IDS = {league["id"] for league in LEAGUES.values()}
