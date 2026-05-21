from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from app.handlers.utils import safe_edit
from app.i18n.languages import LANGUAGE_CHOICES
from app.i18n.translator import get_language_pack
from app.keyboards.language import language_keyboard
from app.keyboards.menus import (
    display_name_keyboard,
    main_menu_keyboard,
    profile_keyboard,
    rankings_keyboard,
)
from app.keyboards.timezone import TIMEZONE_REGIONS, timezone_cities_keyboard, timezone_regions_keyboard
from app.services.sessions import (
    _TOP_MEDALS,
    get_cross_game_streak_line,
    get_game_stats_bulk,
    get_game_streaks_bulk,
    get_user_rankings,
)
from app.services.users import get_display_name, update_user_language, update_user_settings, upsert_user

# GAMES / _GAMES_BY_CODE live in common.py — imported here at top level (no circular dependency)
from app.handlers.common import GAMES, _GAMES_BY_CODE

router = Router()


def _user_identity_line(user) -> str:
    line = get_display_name(user)
    display_name = next(
        (name for name, code in LANGUAGE_CHOICES.items() if code == user.language_code),
        "🇬🇧 English",
    )
    line += f" | {display_name}"
    tz = (user.settings or {}).get("timezone")
    if tz:
        line += f" | 🌍 {tz}"
    return line


# ── Profile main screen ───────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:profile")
async def callback_menu_profile(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, _user_identity_line(user), reply_markup=profile_keyboard(lang))
    await callback.answer()


# ── Streaks / Stats / Rankings ────────────────────────────────────────────────

@router.callback_query(F.data == "profile:streaks")
async def callback_profile_streaks(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)

    stat_games = [g for g in GAMES if g.stat is not None]
    streak_map = await get_game_streaks_bulk(user.id, [g.code for g in stat_games])

    cross_streak = get_cross_game_streak_line(user, lang)

    # col widths (display): current=3, best=4, date=6
    col_hdr = (
        f"`{lang['stat-col-streak']:<2}"   # 2 Python → 3 display
        f"{lang['stat-col-best']:<3}"      # 3 Python → 4 display
        f"{lang['stat-col-date']:<5}`"     # 5 Python → 6 display
    )
    streak_lines: list[str] = [col_hdr]

    for g in stat_games:
        gs = streak_map.get(g.code)
        cur = (gs.current_win_streak or 0) if gs else 0
        best = (gs.best_win_streak or 0) if gs else 0
        last_date = gs.last_win_date if gs else None
        cur_str = str(cur) if cur else "—"
        best_str = str(best) if best else "—"
        date_str = last_date.strftime("%d.%m") if last_date else "—"

        name = lang.get(g.abbr_key, lang[f"game-{g.open_suffix}"]) if g.abbr_key else lang[f"game-{g.open_suffix}"]
        streak_lines.append(
            f"`{cur_str:<3}{best_str:<4}{date_str:<6}{lang[f"icon-{g.open_suffix}"]} {name}`"
        )

    streak_header = cross_streak.lstrip("\n") + "\n\n" if cross_streak else ""
    streaks_text = (
        f"{lang['stat-col-streak']} *{lang['stat-streak-ttl']}*\n\n"
        + streak_header
        + "\n".join(streak_lines)
        + "\n"
    )
    await safe_edit(callback.message, streaks_text, reply_markup=rankings_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "profile:stats")
async def callback_profile_stats(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)

    stat_games = [g for g in GAMES if g.stat is not None]
    stats_map = await get_game_stats_bulk(user.id, [g.code for g in stat_games])

    # col widths (display): played=4, wins=3, losses=3, draws=3
    col_hdr = (
        f"`{lang['stat-col-played']:<3}"   # 3 Python → 4 display
        f"{lang['stat-col-wins']:<2}"      # 2 Python → 3 display
        f"{lang['stat-col-losses']:<2}"    # 2 Python → 3 display
        f"{lang['stat-col-draws']:<2}`"    # 2 Python → 3 display
    )
    stats_lines: list[str] = [col_hdr]

    for g in stat_games:
        stat = stats_map.get(g.code)
        played = stat.played if stat is not None else 0
        wins = stat.wins if stat is not None else 0
        losses = stat.losses if stat is not None else 0
        draws = stat.draws if stat is not None else 0

        name = lang.get(g.abbr_key, lang[f"game-{g.open_suffix}"]) if g.abbr_key else lang[f"game-{g.open_suffix}"]
        stats_lines.append(
            f"`{played:<4}{wins:<3}{losses:<3}{draws:<3}{lang[f"icon-{g.open_suffix}"]} {name}`"
        )

    stats_text = f"{lang['icon-stat']} *{lang['stat-ttl']}*\n\n" + "\n".join(stats_lines) + "\n"
    await safe_edit(callback.message, stats_text, reply_markup=rankings_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "profile:rankings")
async def callback_profile_rankings(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    rankings = await get_user_rankings(user.id)

    if not rankings:
        text = lang["profile-rankings-empty"]
    else:
        lines = [f"*{lang['menu-rankings']}*", ""]
        for game_code, pos in rankings:
            g = _GAMES_BY_CODE.get(game_code)
            game_name = lang[f"game-{g.open_suffix}"] if g else game_code
            medal = _TOP_MEDALS[pos - 1] if pos <= len(_TOP_MEDALS) else f"#{pos}"
            lines.append(f"{medal}  {lang[f"icon-{g.open_suffix}"]} {game_name}")
        text = "\n".join(lines)

    await safe_edit(callback.message, text, parse_mode="Markdown", reply_markup=rankings_keyboard(lang))
    await callback.answer()


# ── Display name ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile:name")
async def callback_profile_name(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    purchased_anon = bool((user.settings or {}).get("purchased_anon"))
    current = get_display_name(user)
    text = lang["profile-name-ask"].format(value=current) + f"\n\n_{lang['profile-name-anon-hint']}_"
    await safe_edit(
        callback.message,
        text,
        parse_mode="Markdown",
        reply_markup=display_name_keyboard(lang, user.first_name, user.last_name, user.username, purchased_anon),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("profile:name:set:"))
async def callback_profile_name_set(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    fmt = callback.data.split(":", 3)[3]
    user = await upsert_user(callback.from_user)
    user = await update_user_settings(user.id, {"display_name_format": fmt})
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, _user_identity_line(user), reply_markup=profile_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "profile:name:buy:anon")
async def callback_profile_name_buy_anon(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await callback.message.answer_invoice(
        title=lang["anon-invoice-title"],
        description=lang["anon-invoice-desc"],
        payload="anon_purchase",
        currency="XTR",
        prices=[LabeledPrice(label=lang["anon-invoice-title"], amount=5)],
    )
    await callback.answer()


@router.pre_checkout_query(lambda q: q.invoice_payload == "anon_purchase")
async def pre_checkout_handler(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment.invoice_payload == "anon_purchase")
async def successful_payment_handler(message: Message) -> None:
    if message.from_user is None or message.successful_payment is None:
        return
    user = await upsert_user(message.from_user)
    user = await update_user_settings(user.id, {"purchased_anon": True, "display_name_format": "anon"})
    lang = get_language_pack(user.language_code)
    await message.answer(
        lang["anon-purchase-ok"],
        reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type),
    )


# ── Language ──────────────────────────────────────────────────────────────────

@router.message(Command("lang"))
async def cmd_lang_command(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["lang-ask"], reply_markup=language_keyboard(lang, chat_type=message.chat.type))


@router.callback_query(F.data == "profile:lang")
async def callback_profile_lang(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(
        callback.message,
        lang["lang-ask"],
        reply_markup=language_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang:"))
async def callback_language_choice(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    lang_code, lang_name = callback.data.split(":")[1], callback.data.split(":")[2]
    await upsert_user(callback.from_user)
    user = await update_user_language(callback.from_user.id, lang_code)
    lang = get_language_pack(lang_code)
    await safe_edit(callback.message, _user_identity_line(user), reply_markup=profile_keyboard(lang))
    await callback.answer(f"✅ {lang_name}")


# ── Timezone ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile:tz")
async def callback_profile_tz(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    current_tz = (user.settings or {}).get("timezone", "UTC")
    text = f"{lang['profile-tz-region']}\n\n🌍 {current_tz}"
    await safe_edit(callback.message, text, reply_markup=timezone_regions_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("profile:tz:region:"))
async def callback_profile_tz_region(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    region = callback.data[len("profile:tz:region:"):]
    if region not in TIMEZONE_REGIONS:
        await callback.answer()
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, lang["profile-tz-city"], reply_markup=timezone_cities_keyboard(region, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("profile:tz:set:"))
async def callback_profile_tz_set(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        return
    tz = callback.data[len("profile:tz:set:"):]
    all_tz = [t for tzs in TIMEZONE_REGIONS.values() for t in tzs]
    if tz not in all_tz:
        await callback.answer()
        return
    user = await upsert_user(callback.from_user)
    user = await update_user_settings(user.id, {"timezone": tz})
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, _user_identity_line(user), reply_markup=profile_keyboard(lang))
    await callback.answer(f"✅ {tz}")
