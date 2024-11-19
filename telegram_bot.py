import asyncio
import pprint
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
from src.config.settings import Config
import requests

from src.utils.logger import LOGGER

telegramApp = ApplicationBuilder().token(Config.TELEGRAM_TOKEN).build()

async def start(update: Update, context: CallbackContext):
    # Get the argument passed to the bot 
    args = context.args
    user = update.effective_user
    bot: Bot = context.bot
    keyboard = [
        [
            InlineKeyboardButton(
                text="Launch Mini-App", 
                url=Config.WEBAPP_URL
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if args:
        startapp_param = args[0]


        # Define the endpoint URL
        url = f"{Config.DOMAIN}/v2/auth/start?referrer={startapp_param}&start=yes" if len(startapp_param) > 0 else f"{Config.DOMAIN}/v2/auth/start"

        # Define the request headers
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        
        bot_profile_photos = await bot.get_user_profile_photos(bot.id, limit=1)
        image = await bot_profile_photos.photos[0][0].get_file() if bot_profile_photos else None

        # Define the request body (data)
        data = {
            "telegram_init_data": "user=%7B%22id%22%3A7156514044%2C%22first_name%22%3A%22%7E%7E%22%2C%22last_name%22%3A%22%22%2C%22language_code%22%3A%22en%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FoFY2iAKaQPureEYt_UcsSdtVtFCPtechdt88ebqNbTXiKy4iZNHvkFmIJb5rPox1.svg%22%7D&chat_instance=-7283749404892336505&chat_type=sender&auth_date=1731437259&hash=375db54d45589a2fbd642d8735f9a8d94d778e72c17e0182049d1413a08532c1",
            "userId": "7156514044",
            "firstName": user.first_name if user.first_name else None,
            "lastName": user.last_name if user.last_name else None,
            "image": image.file_path
        }

        # Make the POST request
        response = requests.post(url, headers=headers, json=data)
        LOGGER.debug(response)
        await update.message.reply_text(f"Hello  {startapp_param}, \nYou can always return to relaunch the app from the button above or use the launch icon on the bottom left to launch the app and get authenticated", reply_markup=reply_markup)
    else:
        url = f"{Config.DOMAIN}/v2/auth/start"

        # Define the request headers
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        
        bot_profile_photos = await bot.get_user_profile_photos(bot.id, limit=1)
        image = await bot_profile_photos.photos[0][0].get_file() if bot_profile_photos else None

        # Define the request body (data)
        data = {
            "telegram_init_data": "user=%7B%22id%22%3A7156514044%2C%22first_name%22%3A%22%7E%7E%22%2C%22last_name%22%3A%22%22%2C%22language_code%22%3A%22en%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FoFY2iAKaQPureEYt_UcsSdtVtFCPtechdt88ebqNbTXiKy4iZNHvkFmIJb5rPox1.svg%22%7D&chat_instance=-7283749404892336505&chat_type=sender&auth_date=1731437259&hash=375db54d45589a2fbd642d8735f9a8d94d778e72c17e0182049d1413a08532c1",
            "userId": "7156514044",
            "firstName": user.first_name if user.first_name else None,
            "lastName": user.last_name if user.last_name else None,
            "image": image.file_path
        }

        # Make the POST request
        response = requests.post(url, headers=headers, json=data)
        LOGGER.debug(response)
        await update.message.reply_text("Launch MiniApp.", reply_markup=reply_markup)

# Register the handler
telegramApp.add_handler(CommandHandler("start", start))

if __name__ == "__main__":
    telegramApp.run_polling()