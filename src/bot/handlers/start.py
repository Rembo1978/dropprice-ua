from aiogram import Router, types
from aiogram.filters import CommandObject, Command
from django.contrib.auth import get_user_model
from users.models import UserSession
from users.services import process_referral

User = get_user_model()
router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    args = command.args  # Отримуємо параметр після /start
    tg_user = message.from_user

    # 1. Отримуємо або створюємо користувача через Django 6 async ORM
    user, created = await User.objects.aget_or_create(
        telegram_id=tg_user.id,
        defaults={
            'username': f"tg_{tg_user.id}",
            'telegram_username': tg_user.username,
            'chat_id': message.chat.id,
            'is_bot_active': True
        }
    )

    # Якщо бот був заблокований, а юзер повернувся — оновлюємо прапорець
    if not user.is_bot_active:
        user.is_bot_active = True
        await user.asave(update_fields=['is_bot_active'])

    # 2. Обробка прив'язки сесії сайту (Deep Link: /start auth_UUID)
    if args and args.startswith("auth_"):
        session_token = args.replace("auth_", "")
        session_obj = await UserSession.objects.filter(token=session_token).afirst()
        
        if session_obj:
            session_obj.user = user
            await session_obj.asave(update_fields=['user'])
            
            await message.answer(
                "✅ **Ви успішно увійшли на сайт DropPrice UA!**\n\n"
                "Тепер ви можете повертатися в браузер — ваш акаунт підключено, а сповіщення про падіння цін надходитимуть сюди."
            )
            return

    # 3. Обробка реферального посилання (Deep Link: /start ref_UUID)
    if created and args and args.startswith("ref_"):
        ref_code = args.replace("ref_", "")
        await process_referral(user, ref_code)

    await message.answer(
        f"Вітаємо, {tg_user.first_name}! 👋\n\n"
        "Я бот **DropPrice UA** 🏷️\n"
        "Я допомагаю стежити за цінами в інтернет-магазинах України і надсилаю сповіщення, коли ціна знижується.\n\n"
        "Надішліть мені посилання на товар або скористайтеся сайтом!"
    )