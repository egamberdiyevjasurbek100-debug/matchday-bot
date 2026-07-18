import asyncio
import logging
import os
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import BOT_TOKEN, LEAGUES, ALL_LEAGUE_IDS
from api_client import (
    get_live_fixtures,
    get_fixtures_by_date,
    get_upcoming_fixtures,
    get_current_season,
    get_standings,
    get_top_scorers,
    get_top_assists,
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

LEAGUE_NAME_TO_KEY = {league["name"]: key for key, league in LEAGUES.items()}


class Nav(StatesGroup):
    choosing_league = State()
    choosing_fixtures_type = State()


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔴 Live natijalar"), KeyboardButton(text="📅 O'yinlar jadvali")],
            [KeyboardButton(text="🏆 Turnir jadvali"), KeyboardButton(text="⚽ Top buombardirlar")],
            [KeyboardButton(text="🎯 Top assistentlar"), KeyboardButton(text="⭐ Sevimli jamoam")],
        ],
        resize_keyboard=True,
    )


def fixtures_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📆 Bugungi o'yinlar"), KeyboardButton(text="🗓 Yaqin o'yinlar")],
            [KeyboardButton(text="⬅️ Orqaga")],
        ],
        resize_keyboard=True,
    )


def league_kb(include_all: bool) -> ReplyKeyboardMarkup:
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
        rows.append([KeyboardButton(text="🌍 Barchasi")])
    rows.append([KeyboardButton(text="⬅️ Orqaga")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def format_fixture(fixture: dict) -> str:
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
        return f"⏸ Tanaffus  {home} {goals_home}:{goals_away} {away}"
    elif status == "FT":
        return f"✅ Yakunlandi  {home} {goals_home}:{goals_away} {away}"
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


def filter_by_league(fixtures: list, key: str) -> tuple[list, str]:
    if key == "all":
        title = "🌍 Barcha ligalar"
        filtered = [f for f in fixtures if f["league"]["id"] in ALL_LEAGUE_IDS]
    else:
        league = LEAGUES[key]
        title = league["name"]
        filtered = [f for f in fixtures if f["league"]["id"] == league["id"]]
    return filtered, title


def format_standings(standings: list, league_name: str) -> str:
    lines = [f"<b>{league_name} — Turnir jadvali</b>\n"]
    lines.append("<code>#   Jamoa                 O   G   D   M   Ochko</code>")
    for team in standings:
        rank = team["rank"]
        name = team["team"]["name"][:19]
        played = team["all"]["played"]
        win = team["all"]["win"]
        draw = team["all"]["draw"]
        lose = team["all"]["lose"]
        points = team["points"]
        lines.append(
            f"<code>{rank:<4}{name:<22}{played:<4}{win:<4}{draw:<4}{lose:<4}{points}</code>"
        )
    lines.append("\n<i>O-o'yin, G-g'alaba, D-durang, M-mag'lubiyat</i>")
    return "\n".join(lines)


def format_top_players(players: list, league_name: str, stat_type: str) -> str:
    label = "⚽ Top buombardirlar" if stat_type == "scorers" else "🎯 Top assistentlar"
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
    text = (
        f"⚽ Salom, <b>{message.from_user.first_name}</b>!\n\n"
        "Men <b>MatchDay Live</b> — futbol muxlislari uchun birinchi raqamli yordamchi botman.\n"
        "Top 5 Yevropa ligasi va O'zbekiston Superligasi bo'yicha "
        "live natijalar, jadval va statistikani shu yerdan olasiz.\n\n"
        "Pastdagi menyudan birini tanlang 👇"
    )
    await message.answer(text, reply_markup=main_menu_kb())


@dp.message(F.text == "⬅️ Orqaga")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=main_menu_kb())


@dp.message(F.text == "🔴 Live natijalar")
async def menu_live(message: Message, state: FSMContext):
    await state.set_state(Nav.choosing_league)
    await state.update_data(action="live", include_all=True)
    await message.answer("Qaysi liga bo'yicha live natijalarni ko'rmoqchisiz?", reply_markup=league_kb(True))


@dp.message(F.text == "📅 O'yinlar jadvali")
async def menu_fixtures(message: Message, state: FSMContext):
    await state.set_state(Nav.choosing_fixtures_type)
    await message.answer("Qaysi turdagi o'yinlar jadvalini ko'rmoqchisiz?", reply_markup=fixtures_type_kb())


@dp.message(Nav.choosing_fixtures_type, F.text == "📆 Bugungi o'yinlar")
async def menu_today(message: Message, state: FSMContext):
    await state.set_state(Nav.choosing_league)
    await state.update_data(action="today", include_all=True)
    await message.answer("Qaysi liga bo'yicha bugungi o'yinlarni ko'rmoqchisiz?", reply_markup=league_kb(True))


@dp.message(Nav.choosing_fixtures_type, F.text == "🗓 Yaqin o'yinlar")
async def menu_upcoming(message: Message, state: FSMContext):
    await state.set_state(Nav.choosing_league)
    await state.update_data(action="upcoming", include_all=False)
    await message.answer("Qaysi liganing yaqin o'yinlarini ko'rmoqchisiz?", reply_markup=league_kb(False))


@dp.message(F.text == "🏆 Turnir jadvali")
async def menu_standings(message: Message, state: FSMContext):
    await state.set_state(Nav.choosing_league)
    await state.update_data(action="standings", include_all=False)
    await message.answer("Qaysi liga jadvalini ko'rmoqchisiz?", reply_markup=league_kb(False))


@dp.message(F.text == "⚽ Top buombardirlar")
async def menu_topscorers(message: Message, state: FSMContext):
    await state.set_state(Nav.choosing_league)
    await state.update_data(action="topscorers", include_all=False)
    await message.answer("Qaysi liga bo'yicha top buombardirlarni ko'rmoqchisiz?", reply_markup=league_kb(False))


@dp.message(F.text == "🎯 Top assistentlar")
async def menu_topassists(message: Message, state: FSMContext):
    await state.set_state(Nav.choosing_league)
    await state.update_data(action="topassists", include_all=False)
    await message.answer("Qaysi liga bo'yicha top assistentlarni ko'rmoqchisiz?", reply_markup=league_kb(False))


@dp.message(F.text == "⭐ Sevimli jamoam")
async def menu_favorite(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🔧 Bu funksiya keyingi bosqichda ulanadi.", reply_markup=main_menu_kb())


@dp.message(Nav.choosing_league)
async def handle_league_choice(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("action")
    include_all = data.get("include_all", False)
    text = message.text

    if text == "🌍 Barchasi" and include_all:
        key = "all"
    elif text in LEAGUE_NAME_TO_KEY:
        key = LEAGUE_NAME_TO_KEY[text]
    else:
        await message.answer("Iltimos, pastdagi tugmalardan birini tanlang 👇")
        return

    await message.answer("Yuklanmoqda... ⏳")

    if action == "live":
        all_fixtures = await get_live_fixtures()
        fixtures, title = filter_by_league(all_fixtures, key)
        if not fixtures:
            result = f"<b>{title}</b>\n\nHozir jonli o'yin yo'q ⚽😴"
        else:
            lines = [format_fixture(f) for f in fixtures]
            result = f"<b>{title} — Live natijalar</b>\n\n" + "\n".join(lines)

    elif action == "today":
        today = datetime.now().strftime("%Y-%m-%d")
        all_fixtures = await get_fixtures_by_date(today)
        fixtures, title = filter_by_league(all_fixtures, key)
        if not fixtures:
            result = f"<b>{title}</b>\n\nBugun o'yin yo'q 📅"
        else:
            lines = [format_fixture(f) for f in fixtures]
            result = f"<b>{title} — Bugungi o'yinlar</b>\n\n" + "\n".join(lines)

    elif action == "upcoming":
        league = LEAGUES[key]
        season = await get_current_season(league["id"])
        fixtures = await get_upcoming_fixtures(league["id"], season)
        if not fixtures:
            result = f"<b>{league['name']}</b>\n\nYaqin kunlarda o'yin topilmadi."
        else:
            lines = [format_upcoming_fixture(f) for f in fixtures]
            result = f"<b>{league['name']} — Yaqin o'yinlar</b>\n\n" + "\n".join(lines)

    elif action == "standings":
        league = LEAGUES[key]
        season = await get_current_season(league["id"])
        standings = await get_standings(league["id"], season)
        if not standings:
            result = f"<b>{league['name']}</b>\n\nJadval hozircha topilmadi."
        else:
            result = format_standings(standings, league["name"])

    elif action == "topscorers":
        league = LEAGUES[key]
        season = await get_current_season(league["id"])
        players = await get_top_scorers(league["id"], season)
        if not players:
            result = f"<b>{league['name']}</b>\n\nMa'lumot hozircha topilmadi."
        else:
            result = format_top_players(players, league["name"], "scorers")

    elif action == "topassists":
        league = LEAGUES[key]
        season = await get_current_season(league["id"])
        players = await get_top_assists(league["id"], season)
        if not players:
            result = f"<b>{league['name']}</b>\n\nMa'lumot hozircha topilmadi."
        else:
            result = format_top_players(players, league["name"], "assists")

    else:
        result = "Xatolik yuz berdi."

    await state.clear()
    await message.answer(result, reply_markup=main_menu_kb())


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
    await start_web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
