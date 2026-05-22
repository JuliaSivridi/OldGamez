from aiogram import F, Router
from aiogram.enums import ButtonStyle
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.services.users import upsert_user

router = Router()

DONATE_AMOUNTS = [50, 100, 200, 500]


def donate_keyboard(lang: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for amount in DONATE_AMOUNTS:
        builder.button(text=f"⭐ {amount}", callback_data=f"donate:{amount}", style=ButtonStyle.PRIMARY)
    builder.button(text=lang["main-back"], callback_data="main:back", style=ButtonStyle.SUCCESS)
    builder.adjust(2, 2, 1)
    return builder.as_markup()


@router.message(Command("donate"))
async def cmd_donate(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(_donate_text(lang), reply_markup=donate_keyboard(lang))


def _donate_text(lang: dict) -> str:
    return f"{lang['donate-info']}\n\n{lang['donate-ask']}"


@router.callback_query(F.data == "menu:donate")
async def callback_donate(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(callback.message, _donate_text(lang), reply_markup=donate_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("donate:"))
async def callback_donate_amount(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        return
    amount = int(callback.data.split(":")[1])
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await callback.answer()
    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=lang["donate-title"],
        description=lang["donate-desc"],
        payload=f"donate:{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="⭐", amount=amount)],
    )


@router.pre_checkout_query(lambda q: q.invoice_payload.startswith("donate:"))
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment.invoice_payload.startswith("donate:"))
async def payment_success(message: Message) -> None:
    if message.from_user is None:
        return
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)
    await message.answer(lang["donate-thanks"])
