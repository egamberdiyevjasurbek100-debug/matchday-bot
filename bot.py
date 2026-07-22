import asyncio
import logging
import os
import urllib.parse
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import BOT_TOKEN, LEAGUES, ALL_LEAGUE_IDS
from api_client import (
    get_live_fixtures,
    get_fixtures_by_date,
    get_upcoming_fixtures,
    get_current_season,
    get_standings,
    get_top_scorers,
    get_top_assists,
    get_teams_by_league,
    get_upcoming_fixtures_for_team,
)
from supabase_client import (
    get_favorites,
    get_all_favorites,
    add_favorite,
    remove_favorite,
    mark_notified,
    get_user_language,
    set_user_language,
)
from translations import t, all_variants

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())

LEAGUE_NAME_TO_KEY = {
    league["name"]: key for key, league in LEAGUES.items()
}
OFFICIAL_HIGHLIGHT_CHANNELS = {
    "uzbekistan": "https://www.youtube.com/@uzbekistanpfl",
}


def get_highlights_url(league_key: str, league_name: str) -> str:
    if league_key in OFFICIAL_HIGHLIGHT_CHANNELS:
        return OFFICIAL_HIGHLIGHT_CHANNELS[league_key]
    query = urllib.parse.quote_plus(f"{league_name} highlights")
    return f"https://www.youtube.com/results?search_query={query}"
CHECK_INTERVAL_SECONDS = 3 * 60 * 60
NOTIFY_WINDOW_HOURS = 24

_lang_cache = {}


async def get_lang(user_id: int):
    if user_id in _lang_cache:
        return _lang_cache[user_id]
    lang = await get_user_language(user_id)
    if lang:
        _lang_cache[user_id] = lang
    return lang


async def save_lang(user_id: int, lang: str):
    await set_user_language(user_id, lang)
    _lang_cache[user_id] = lang


BACK_TEXTS = all_variants("btn_back")
LIVE_TEXTS = all_variants("btn_live")
FIXTURES_TEXTS = all_variants("btn_fixtures")
STANDINGS_TEXTS = all_variants("btn_standings")
TOPSCORERS_TEXTS = all_variants("btn_topscorers")
TOPASSISTS_TEXTS = all_variants("btn_topassists")
FAVORITES_TEXTS = all_variants("btn_favorites")
CHANGE_LANG_TEXTS = all_variants("btn_change_language")
TODAY_TEXTS = all_variants("btn_today")
UPCOMING_TEXTS = all_variants("btn_upcoming")
ADD_TEAM_TEXTS = all_variants("btn_add_team")
REMOVE_TEAM_TEXTS = all_variants("btn_remove_team")
HIGHLIGHTS_TEXTS = all_variants("btn_highlights")

class Nav(StatesGroup):
    choosing_language = State()
    choosing_league = State()
    choosing_fixtures_type = State()
    choosing_team = State()
    removing_team = State()
    favorites_menu = State()


def language_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇿 O'zbekcha")],
            [KeyboardButton(text="🇷🇺 Русский")],
            [KeyboardButton(text="🇬🇧 English")],
        ],
        resize_keyboard=True,
    )


def main_menu_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn_live")),
                KeyboardButton(text=t(lang, "btn_fixtures")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_standings")),
                KeyboardButton(text=t(lang, "btn_topscorers")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_topassists")),
                KeyboardButton(text=t(lang, "btn_favorites")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_highlights")),
                KeyboardButton(text=t(lang, "btn_change_language")),
            ],
        ],
        resize_keyboard=True,
    )


def fixtures_type_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn_today")),
                KeyboardButton(text=t(lang, "btn_upcoming")),
            ],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def league_kb(lang: str, include_all: bool) -> ReplyKeyboardMarkup:
    rows = []
    row = []
    for league in LEAGUES.values():
        row.append(KeyboardButton(text=league["name"]))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if include_all:
        rows.append([KeyboardButton(text=t(lang, "btn_all"))])
    rows.append([KeyboardButton(text=t(lang, "btn_back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def favorites_menu_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_add_team"))],
            [KeyboardButton(text=t(lang, "btn_remove_team"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def team_selection_kb(lang: str, names: list) -> ReplyKeyboardMarkup:
    rows = []
    row = []
    for name in names:
        row.append(KeyboardButton(text=name))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text=t(lang, "btn_back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def format_fixture(fixture: dict, lang: str) -> str:
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    goals_home = fixture["goals"]["home"]
    goals_away = fixture["goals"]["away"]
    status = fixture["fixture"]["status"]["short"]
    elapsed = fixture["fixture"]["status"]["elapsed"]

    if status == "NS":
        time_str = fixture["fixture"]["date"][11:16]
        return f"⏳ {time_str}  {home} — {away}"
    elif status in ("1H", "2H", "ET", "LIVE"):
        return f"🔴 {elapsed}'  {home} {goals_home}:{goals_away} {away}"
    elif status == "HT":
        label = t(lang, "status_halftime")
        return f"⏸ {label}  {home} {goals_home}:{goals_away} {away}"
    elif status == "FT":
        label = t(lang, "status_finished")
        return f"✅ {label}  {home} {goals_home}:{goals_away} {away}"
    else:
        gh = goals_home if goals_home is not None else "-"
        ga = goals_away if goals_away is not None else "-"
        return f"{home} {gh}:{ga} {away} ({status})"


def format_upcoming_fixture(fixture: dict) -> str:
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    dt = fixture["fixture"]["date"]
    date_part = dt[5:10]
    time_part = dt[11:16]
    return f"🗓 {date_part} {time_part}  {home} — {away}"


def filter_by_league(fixtures: list, key: str):
    if key == "all":
        title = "🌍"
        filtered = [
            f for f in fixtures if f["league"]["id"] in ALL_LEAGUE_IDS
        ]
    else:
        league = LEAGUES[key]
        title = league["name"]
        filtered = [
            f for f in fixtures if f["league"]["id"] == league["id"]
        ]
    return filtered, title


def format_standings(standings: list, league_name: str, lang: str) -> str:
    title = t(lang, "standings_title")
    lines = [f"<b>{league_name} — {title}</b>\n"]
    columns = t(lang, "standings_columns")
    lines.append(f"<code>{columns}</code>")
    for team in standings:
        rank = team["rank"]
        name = team["team"]["name"][:19]
        played = team["all"]["played"]
        win = team["all"]["win"]
        draw = team["all"]["draw"]
        lose = team["all"]["lose"]
        points = team["points"]
        lines.append(
            f"<code>{rank:<4}{name:<22}{played:<4}"
            f"{win:<4}{draw:<4}{lose:<4}{points}</code>"
        )
    footer = t(lang, "standings_footer")
    lines.append(f"\n<i>{footer}</i>")
    return "\n".join(lines)


def format_top_players(
    players: list, league_name: str, stat_type: str, lang: str
) -> str:
    if stat_type == "scorers":
        label = t(lang, "topscorers_label")
    else:
        label = t(lang, "topassists_label")
    lines = [f"<b>{league_name}</b>\n{label}\n"]
    for i, item in enumerate(players[:10], start=1):
        name = item["player"]["name"]
        stats = item["statistics"][0]
        team = stats["team"]["name"]
        if stat_type == "scorers":
            count = stats["goals"]["total"] or 0
        else:
            count = stats["goals"]["assists"] or 0
        lines.append(f"{i}. {name} ({team}) — {count}")
    return "\n".join(lines)


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    if lang is None:
        await state.set_state(Nav.choosing_language)
        await message.answer(
            t("uz", "choose_language"),
            reply_markup=language_kb(),
        )
        return
    text = t(lang, "welcome", name=message.from_user.first_name)
    await message.answer(text, reply_markup=main_menu_kb(lang))


@dp.message(Nav.choosing_language)
async def handle_language_choice(message: Message, state: FSMContext):
    lang_map = {
        "🇺🇿 O'zbekcha": "uz",
        "🇷🇺 Русский": "ru",
        "🇬🇧 English": "en",
    }
    chosen = lang_map.get(message.text)
    if not chosen:
        await message.answer(
            t("uz", "choose_language"), reply_markup=language_kb()
        )
        return
    await save_lang(message.from_user.id, chosen)
    await state.clear()
    text = t(chosen, "welcome", name=message.from_user.first_name)
    await message.answer(text, reply_markup=main_menu_kb(chosen))


@dp.message(F.text.in_(CHANGE_LANG_TEXTS))
async def menu_change_language(message: Message, state: FSMContext):
    await state.set_state(Nav.choosing_language)
    await message.answer(
        t("uz", "choose_language"), reply_markup=language_kb()
    )


@dp.message(F.text.in_(BACK_TEXTS))
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_lang(message.from_user.id)
    await message.answer(
        t(lang, "main_menu_label"), reply_markup=main_menu_kb(lang)
    )


@dp.message(F.text.in_(LIVE_TEXTS))
async def menu_live(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_league)
    await state.update_data(action="live", include_all=True, lang=lang)
    await message.answer(
        t(lang, "live_league_prompt"),
        reply_markup=league_kb(lang, True),
    )


@dp.message(F.text.in_(FIXTURES_TEXTS))
async def menu_fixtures(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_fixtures_type)
    await state.update_data(lang=lang)
    await message.answer(
        t(lang, "fixtures_type_prompt"),
        reply_markup=fixtures_type_kb(lang),
    )


@dp.message(Nav.choosing_fixtures_type, F.text.in_(TODAY_TEXTS))
async def menu_today(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_league)
    await state.update_data(action="today", include_all=True, lang=lang)
    await message.answer(
        t(lang, "today_league_prompt"),
        reply_markup=league_kb(lang, True),
    )


@dp.message(Nav.choosing_fixtures_type, F.text.in_(UPCOMING_TEXTS))
async def menu_upcoming(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_league)
    await state.update_data(
        action="upcoming", include_all=False, lang=lang
    )
    await message.answer(
        t(lang, "upcoming_league_prompt"),
        reply_markup=league_kb(lang, False),
    )


@dp.message(F.text.in_(STANDINGS_TEXTS))
async def menu_standings(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_league)
    await state.update_data(
        action="standings", include_all=False, lang=lang
    )
    await message.answer(
        t(lang, "standings_league_prompt"),
        reply_markup=league_kb(lang, False),
    )


@dp.message(F.text.in_(TOPSCORERS_TEXTS))
async def menu_topscorers(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_league)
    await state.update_data(
        action="topscorers", include_all=False, lang=lang
    )
    await message.answer(
        t(lang, "topscorers_league_prompt"),
        reply_markup=league_kb(lang, False),
    )


@dp.message(F.text.in_(TOPASSISTS_TEXTS))
async def menu_topassists(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_league)
    await state.update_data(
        action="topassists", include_all=False, lang=lang
    )
    await message.answer(
        t(lang, "topassists_league_prompt"),
        reply_markup=league_kb(lang, False),
    )
@dp.message(F.text.in_(HIGHLIGHTS_TEXTS))
async def menu_highlights(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_league)
    await state.update_data(
        action="highlights", include_all=False, lang=lang
    )
    await message.answer(
        t(lang, "highlights_league_prompt"),
        reply_markup=league_kb(lang, False),
    )

@dp.message(F.text.in_(FAVORITES_TEXTS))
async def menu_favorite(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.clear()
    favorites = await get_favorites(message.from_user.id)
    if favorites:
        lines = [t(lang, "your_favorites_header")]
        for fav in favorites:
            lines.append(f"⭐ {fav['team_name']}")
        text = "\n".join(lines)
    else:
        text = t(lang, "no_favorites")
    await state.set_state(Nav.favorites_menu)
    await state.update_data(lang=lang)
    await message.answer(text, reply_markup=favorites_menu_kb(lang))


@dp.message(Nav.favorites_menu, F.text.in_(ADD_TEAM_TEXTS))
async def add_favorite_start(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or await get_lang(message.from_user.id)
    await state.set_state(Nav.choosing_league)
    await state.update_data(
        action="pick_team_league", include_all=False, lang=lang
    )
    await message.answer(
        t(lang, "pick_league_for_team"),
        reply_markup=league_kb(lang, False),
    )


@dp.message(Nav.favorites_menu, F.text.in_(REMOVE_TEAM_TEXTS))
async def remove_favorite_start(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or await get_lang(message.from_user.id)
    favorites = await get_favorites(message.from_user.id)
    if not favorites:
        await message.answer(
            t(lang, "no_favorite_teams"),
            reply_markup=favorites_menu_kb(lang),
        )
        return
    fav_map = {f["team_name"]: f["team_id"] for f in favorites}
    await state.update_data(fav_map=fav_map, lang=lang)
    await state.set_state(Nav.removing_team)
    await message.answer(
        t(lang, "pick_team_to_remove"),
        reply_markup=team_selection_kb(lang, list(fav_map.keys())),
    )


@dp.message(Nav.removing_team)
async def handle_team_removal(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or await get_lang(message.from_user.id)
    fav_map = data.get("fav_map", {})
    text = message.text
    if text not in fav_map:
        await message.answer(t(lang, "choose_from_buttons"))
        return
    team_id = fav_map[text]
    await remove_favorite(message.from_user.id, team_id)
    await state.clear()
    await message.answer(
        t(lang, "team_removed", team=text),
        reply_markup=main_menu_kb(lang),
    )


@dp.message(Nav.choosing_team)
async def handle_team_choice(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang") or await get_lang(message.from_user.id)
    team_map = data.get("team_map", {})
    text = message.text
    if text not in team_map:
        await message.answer(t(lang, "choose_from_buttons"))
        return
    team_id = team_map[text]
    await add_favorite(message.from_user.id, team_id, text)
    await state.clear()
    await message.answer(
        t(lang, "team_added", team=text),
        reply_markup=main_menu_kb(lang),
    )


@dp.message(Nav.choosing_league)
async def handle_league_choice(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("action")
    include_all = data.get("include_all", False)
    lang = data.get("lang") or await get_lang(message.from_user.id)
    text = message.text

    if text == t(lang, "btn_all") and include_all:
        key = "all"
    elif text in LEAGUE_NAME_TO_KEY:
        key = LEAGUE_NAME_TO_KEY[text]
    else:
        await message.answer(t(lang, "choose_from_buttons"))
        return

    if action == "pick_team_league":
        league = LEAGUES[key]
        await message.answer(t(lang, "loading"))
        season = await get_current_season(league["id"])
        teams = await get_teams_by_league(league["id"], season)
        if not teams:
            await state.set_state(Nav.favorites_menu)
            await message.answer(
                t(lang, "no_teams_found"),
                reply_markup=favorites_menu_kb(lang),
            )
            return
        team_map = {
            tm["team"]["name"]: tm["team"]["id"] for tm in teams
        }
        await state.update_data(team_map=team_map, lang=lang)
        await state.set_state(Nav.choosing_team)
        await message.answer(
            t(lang, "pick_team_prompt", league=league["name"]),
            reply_markup=team_selection_kb(
                lang, list(team_map.keys())
            ),
        )
        return

    await message.answer(t(lang, "loading"))

    if action == "live":
        all_fixtures = await get_live_fixtures()
        fixtures, title = filter_by_league(all_fixtures, key)
        if not fixtures:
            result = t(lang, "live_no_matches", title=title)
        else:
            lines = "\n".join(
                format_fixture(f, lang) for f in fixtures
            )
            result = t(lang, "live_header", title=title, lines=lines)

    elif action == "today":
        today = datetime.now().strftime("%Y-%m-%d")
        all_fixtures = await get_fixtures_by_date(today)
        fixtures, title = filter_by_league(all_fixtures, key)
        if not fixtures:
            result = t(lang, "no_games_today", title=title)
        else:
            lines = "\n".join(
                format_fixture(f, lang) for f in fixtures
            )
            result = t(lang, "today_header", title=title, lines=lines)

    elif action == "upcoming":
        league = LEAGUES[key]
        season = await get_current_season(league["id"])
        fixtures = await get_upcoming_fixtures(league["id"], season)
        if not fixtures:
            result = t(lang, "no_upcoming", league=league["name"])
        else:
            lines = "\n".join(
                format_upcoming_fixture(f) for f in fixtures
            )
            result = t(
                lang, "upcoming_header",
                league=league["name"], lines=lines,
            )

    elif action == "standings":
        league = LEAGUES[key]
        season = await get_current_season(league["id"])
        standings = await get_standings(league["id"], season)
        if not standings:
            result = t(lang, "no_standings", league=league["name"])
        else:
            result = format_standings(
                standings, league["name"], lang
            )

    elif action == "topscorers":
        league = LEAGUES[key]
        season = await get_current_season(league["id"])
        players = await get_top_scorers(league["id"], season)
        if not players:
            result = t(lang, "no_stats", league=league["name"])
        else:
            result = format_top_players(
                players, league["name"], "scorers", lang
            )

    elif action == "topassists":
        league = LEAGUES[key]
        season = await get_current_season(league["id"])
        players = await get_top_assists(league["id"], season)
        if not players:
            result = t(lang, "no_stats", league=league["name"])
        else:
            result = format_top_players(
                players, league["name"], "assists", lang
            )
    elif action == "highlights":
        league = LEAGUES[key]
        url = get_highlights_url(key, league["name"])
        caption = t(lang, "highlights_caption", league=league["name"])
        open_label = t(lang, "highlights_open")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=open_label, url=url)]
            ]
        )
        await state.clear()
        await message.answer(caption, reply_markup=kb)
        await message.answer(
            t(lang, "main_menu_label"),
            reply_markup=main_menu_kb(lang),
        )
        return
    else:
        result = "Error."

    await state.clear()
    await message.answer(result, reply_markup=main_menu_kb(lang))


async def check_favorite_notifications():
    while True:
        try:
            favorites = await get_all_favorites()
            teams_map = {}
            for fav in favorites:
                teams_map.setdefault(fav["team_id"], []).append(fav)

            for team_id, rows in teams_map.items():
                fixtures = await get_upcoming_fixtures_for_team(
                    team_id, count=1
                )
                if not fixtures:
                    continue
                fixture = fixtures[0]
                fixture_id = str(fixture["fixture"]["id"])
                fixture_time = datetime.fromisoformat(
                    fixture["fixture"]["date"]
                )
                now = datetime.now(fixture_time.tzinfo)
                hours_left = (
                    fixture_time - now
                ).total_seconds() / 3600

                if 0 < hours_left <= NOTIFY_WINDOW_HOURS:
                    home = fixture["teams"]["home"]["name"]
                    away = fixture["teams"]["away"]["name"]
                    time_str = fixture["fixture"]["date"][11:16]
                    date_str = fixture["fixture"]["date"][5:10]

                    for row in rows:
                        notified = row.get("notified_fixtures") or ""
                        notified_list = (
                            notified.split(",") if notified else []
                        )
                        if fixture_id in notified_list:
                            continue
                        try:
                            user_lang = (
                                await get_lang(row["user_id"]) or "uz"
                            )
                            text = t(
                                user_lang,
                                "notification_text",
                                team=row["team_name"],
                                date=date_str,
                                time=time_str,
                                home=home,
                                away=away,
                            )
                            await bot.send_message(
                                row["user_id"], text
                            )
                            notified_list.append(fixture_id)
                            await mark_notified(
                                row["id"], ",".join(notified_list)
                            )
                        except Exception as e:
                            logging.error(
                                f"Bildirishnoma yuborishda xato: {e}"
                            )
        except Exception as e:
            logging.error(f"Bildirishnoma tekshiruvida xato: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def set_bot_commands():
    commands = [
        BotCommand(
            command="start",
            description="🔄 Qayta boshlash / Restart / Перезапуск",
        ),
    ]
    await bot.set_my_commands(commands)


async def handle_ping(request):
    return web.Response(text="MatchDay Live bot ishlab turibdi ✅")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main():
    print("MatchDay Live bot ishga tushdi...")
    await set_bot_commands()
    await start_web_server()
    asyncio.create_task(check_favorite_notifications())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
