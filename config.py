import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
API_BASE_URL = "https://v3.football.api-sports.io"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

LEAGUES = {
    "epl": {"id": 39, "name": "🏴 Premier League", "type": "league"},
    "laliga": {"id": 140, "name": "🇪🇸 La Liga", "type": "league"},
    "seriea": {"id": 135, "name": "🇮🇹 Serie A", "type": "league"},
    "bundesliga": {"id": 78, "name": "🇩🇪 Bundesliga", "type": "league"},
    "ligue1": {"id": 61, "name": "🇫🇷 Ligue 1", "type": "league"},
    "uzbekistan": {"id": 369, "name": "🇺🇿 Superliga", "type": "league"},

    "ucl": {"id": 2, "name": "⭐ Champions League", "type": "cup"},
    "uel": {"id": 3, "name": "🥈 Europa League", "type": "cup"},
    "uz_cup": {"id": 802, "name": "🇺🇿 O'zbekiston kubogi", "type": "cup"},

    "uecl": {"id": 848, "name": "🥉 Conference League", "type": "cup"},
    "facup": {"id": 45, "name": "🏴 FA Cup", "type": "cup"},
    "community_shield": {"id": 528, "name": "🏴 Community Shield", "type": "cup"},
    "copadelrey": {"id": 143, "name": "🇪🇸 Copa del Rey", "type": "cup"},
    "supercopa": {"id": 556, "name": "🇪🇸 Super Cup", "type": "cup"},
    "acl": {"id": 480, "name": "🌏 AFC Champions League Elite", "type": "cup"},
}

ALL_LEAGUE_IDS = {league["id"] for league in LEAGUES.values()}
