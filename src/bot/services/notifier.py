import asyncio
from aiogram import Bot
from aiogram.enums import ParseMode
from django.conf import settings


def send_price_drop_notification(chat_id: int, title: str, old_price: float, new_price: float, url: str, currency: str = "грн"):
    """
    Синхронна функція-обгортка для виклику з Celery-тасок.
    """
    async def _async_send():
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        text = (
            f"📉 **Ціна впала!**\n\n"
            f"🛍 **[{title}]({url})**\n\n"
            f"❌ Стара ціна: ~{old_price} {currency}~\n"
            f"🔥 **Нова ціна: {new_price} {currency}**\n"
        )
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
        finally:
            await bot.session.close()

    asyncio.run(_async_send())