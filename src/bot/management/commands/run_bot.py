import asyncio
from django.core.management.base import BaseCommand
from django.conf import settings
from aiogram import Bot, Dispatcher
from bot.handlers import register_all_handlers


class Command(BaseCommand):
    help = "Запуск Telegram-бота DropPrice UA (aiogram 3) у режимі розробки"

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN не вказано в settings.py / .env!"))
            return

        async def main():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            dp = Dispatcher()

            # Підключаємо наші обробники
            register_all_handlers(dp)

            self.stdout.write(self.style.SUCCESS("🤖 Telegram-бот DropPrice UA успішно запущений (Long Polling)..."))
            
            # Видаляємо старі вебхуки перед запуском polling
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)

        try:
            asyncio.run(main())
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write(self.style.WARNING("Бот зупинений."))