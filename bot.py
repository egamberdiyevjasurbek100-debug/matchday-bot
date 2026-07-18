import asyncio
import logging
import os
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
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
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🔴 Live natijalar", callback_data="live_scores")],
        [InlineKeyboardButton(text="📅 O'yinlar jadvali", callback_data="fixtures")],
        [InlineKeyboardButton(text="🏆 Turnir jadvali", callback_data="standings")],
        [InlineKeyboardButton(text="⚽ Top buombardirlar", callback_data="top_scorers")],
        [InlineKeyboardButton(text="🎯 Top assistentlar", callback_data="top_assists")],
        [InlineKeyboardButton(text="⭐ Sevimli jamoam", callback_data="favorite_team")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def league_selection_keyboard(prefix: str, include_all: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for key, league in LEAGUES.items():
        row.append(InlineKeyboardButton(text=league["name"], callback_data=f"{prefix}:{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if include_all:
        buttons.append([InlineKeyboardButton(text="🌍 Barchasi", callback_data=f"{prefix}:all")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def fixtures_type_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="📆 Bugungi o'yinlar", callback_data="today_menu")],
        [InlineKeyboardButton(text="🗓 Yaqin o'yinlar (taqvim)", callback_data="upcoming_menu")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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
async def cmd_start(message: Message):
    text = (
        f"⚽ Salom, <b>{message.from_user.first_name}</b>!\n\n"
        "Men <b>MatchDay Live</b> — futbol muxlislari uchun birinchi raqamli yordamchi botman.\n"
        "Top 5 Yevropa ligasi va O'zbekiston Superligasi bo'yicha "
        "live natijalar, jadval va statistikani shu yerdan olasiz.\n\n"
        "Quyidagi menyudan birini tanlang 👇"
    )
    await message.answer(text, reply_markup=main_menu())


@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu())


@dp.callback_query(F.data == "live_scores")
async def show_live_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Qaysi liga bo'yicha live natijalarni ko'rmoqchisiz?",
        reply_markup=league_selection_keyboard("live"),
    )


@dp.callback_query(F.data.startswith("live:"))
async def show_live_results(callback: CallbackQuery):
    await callback.answer("Yuklanmoqda...")
    key = callback.data.split(":")[1]
    all_fixtures = await get_live_fixtures()
    fixtures, title = filter_by_league(all_fixtures, key)
    if not fixtures:
        await callback.message.answer(f"<b>{title}</b>\n\nHozir jonli o'yin yo'q ⚽😴")
        return
    lines = [format_fixture(f) for f in fixtures]
    text = f"<b>{title} — Live natijalar</b>\n\n" + "\n".join(lines)
    await callback.message.answer(text)


@dp.callback_query(F.data == "fixtures")
async def show_fixtures_type_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Qaysi turdagi o'yinlar jadvalini ko'rmoqchisiz?",
        reply_markup=fixtures_type_menu_keyboard(),
    )


@dp.callback_query(F.data == "today_menu")
async def show_today_league_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Qaysi liga bo'yicha bugungi o'yinlarni ko'rmoqchisiz?",
        reply_markup=league_selection_keyboard("today", include_all=True),
    )


@dp.callback_query(F.data.startswith("today:"))
async def show_today_fixtures(callback: CallbackQuery):
    await callback.answer("Yuklanmoqda...")
    key = callback.data.split(":")[1]
    today = datetime.now().strftime("%Y-%m-%d")
    all_fixtures = await get_fixtures_by_date(today)
    fixtures, title = filter_by_league(all_fixtures, key)
    if not fixtures:
        await callback.message.answer(f"<b>{title}</b>\n\nBugun o'yin yo'q 📅")
        return
    lines = [format_fixture(f) for f in fixtures]
    text = f"<b>{title} — Bugungi o'yinlar</b>\n\n" + "\n".join(lines)
    await callback.message.answer(text)


@dp.callback_query(F.data == "upcoming_menu")
async def show_upcoming_league_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Qaysi liganing yaqin kunlardagi o'yinlarini ko'rmoqchisiz?",
        reply_markup=league_selection_keyboard("upcoming", include_all=False),
    )


@dp.callback_query(F.data.startswith("upcoming:"))
async def show_upcoming_fixtures_handler(callback: CallbackQuery):
    await callback.answer("Yuklanmoqda...")
    key = callback.data.split(":")[1]
    league = LEAGUES[key]
    season = await get_current_season(league["id"])
    fixtures = await get_upcoming_fixtures(league["id"], season)
    if not fixtures:
        await callback.message.answer(f"<b>{league['name']}</b>\n\nYaqin kunlarda o'yin topilmadi.")
        return
    lines = [format_upcoming_fixture(f) for f in fixtures]
    text = f"<b>{league['name']} — Yaqin o'yinlar</b>\n\n" + "\n".join(lines)
    await callback.message.answer(text)


@dp.callback_query(F.data == "standings")
async def show_standings_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Qaysi liga jadvalini ko'rmoqchisiz?",
        reply_markup=league_selection_keyboard("standings", include_all=False),
    )


@dp.callback_query(F.data.startswith("standings:"))
async def show_standings_table(callback: CallbackQuery):
    await callback.answer("Yuklanmoqda...")
    key = callback.data.split(":")[1]
    league = LEAGUES[key]
    season = await get_current_season(league["id"])
    standings = await get_standings(league["id"], season)
    if not standings:
        await callback.message.answer(f"<b>{league['name']}</b>\n\nJadval hozircha topilmadi.")
        return
    text = format_standings(standings, league["name"])
    await callback.message.answer(text)


@dp.callback_query(F.data == "top_scorers")
async def show_top_scorers_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Qaysi liga bo'yicha top buombardirlarni ko'rmoqchisiz?",
        reply_markup=league_selection_keyboard("topscorers", include_all=False),
    )


@dp.callback_query(F.data.startswith("topscorers:"))
async def show_top_scorers(callback: CallbackQuery):
    await callback.answer("Yuklanmoqda...")
    key = callback.data.split(":")[1]
    league = LEAGUES[key]
    season = await get_current_season(league["id"])
    players = await get_top_scorers(league["id"], season)
    if not players:
        await callback.message.answer(f"<b>{league['name']}</b>\n\nMa'lumot hozircha topilmadi.")
        return
    text = format_top_players(players, league["name"], "scorers")
    await callback.message.answer(text)


@dp.callback_query(F.data == "top_assists")
async def show_top_assists_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Qaysi liga bo'yicha top assistentlarni ko'rmoqchisiz?",
        reply_markup=league_selection_keyboard("topassists", include_all=False),
    )


@dp.callback_query(F.data.startswith("topassists:"))
async def show_top_assists(callback: CallbackQuery):
    await callback.answer("Yuklanmoqda...")
    key = callback.data.split(":")[1]
    league = LEAGUES[key]
    season = await get_current_season(league["id"])
    players = await get_top_assists(league["id"], season)
    if not players:
        await callback.message.answer(f"<b>{league['name']}</b>\n\nMa'lumot hozircha topilmadi.")
        return
    text = format_top_players(players, league["name"], "assists")
    await callback.message.answer(text)


@dp.callback_query(F.data == "favorite_team")
async def handle_placeholder(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔧 Bu funksiya keyingi bosqichda ulanadi.")


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
