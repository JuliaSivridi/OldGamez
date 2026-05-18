from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_settings
from app.handlers.utils import safe_edit
from app.i18n.translator import get_language_pack
from app.keyboards.menus import main_menu_keyboard
from app.services.feedback import save_feedback
from app.services.users import upsert_user

router = Router()


class FeedbackStates(StatesGroup):
    waiting_for_text = State()


def _cancel_keyboard(lang: dict):
    builder = InlineKeyboardBuilder()
    builder.button(text=lang["main-back"], callback_data="feedback:cancel")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "menu:feedback")
async def callback_feedback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    if callback.message.chat.type in ("group", "supergroup"):
        await callback.answer(lang["feedback-group-only"], show_alert=True)
        return
    await state.set_state(FeedbackStates.waiting_for_text)
    await safe_edit(callback.message, lang["feedback-prompt"], reply_markup=_cancel_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "feedback:cancel")
async def callback_feedback_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.message is None:
        return
    await state.clear()
    user = await upsert_user(callback.from_user)
    lang = get_language_pack(user.language_code)
    await safe_edit(
        callback.message,
        lang["main-ttl"],
        reply_markup=main_menu_keyboard(lang, chat_type=callback.message.chat.type),
    )
    await callback.answer()


@router.message(FeedbackStates.waiting_for_text)
async def handle_feedback_text(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    if not message.text:
        user = await upsert_user(message.from_user)
        lang = get_language_pack(user.language_code)
        await message.answer(lang["feedback-text-only"], reply_markup=_cancel_keyboard(lang))
        return
    await state.clear()
    user = await upsert_user(message.from_user)
    lang = get_language_pack(user.language_code)

    try:
        await save_feedback(user.id, message.text)
    except Exception:
        pass

    settings = get_settings()
    if settings.feedback_chat_id:
        tg = message.from_user
        name = " ".join(filter(None, [tg.first_name, tg.last_name]))
        mention = f"@{tg.username}" if tg.username else f"id={tg.id}"
        try:
            await message.bot.send_message(
                settings.feedback_chat_id,
                f"📨 *Feedback* от {name} ({mention}) · `{user.language_code}`",
            )
            await message.forward(settings.feedback_chat_id)
        except Exception:
            pass

    await message.answer(
        lang["feedback-thanks"],
        reply_markup=main_menu_keyboard(lang, chat_type=message.chat.type),
    )
