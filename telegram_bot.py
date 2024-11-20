import asyncio
import pprint
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
from telegram.constants import ParseMode

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
                text="LAUNCH", 
                url=Config.WEBAPP_URL
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if args is not None and len[args] > 0:
        LOGGER.debug(args)
        startapp_param = args[0]

        try:
            int(startapp_param)
        except Exception as e:
            await update.eessage.reply_text(f"This must be a valid user id or none")

        # Define the endpoint URL
        url = f"{Config.DOMAIN}/v2/auth/start?referrer={startapp_param}"
            
        LOGGER.debug(f"START URL: {url}")
        LOGGER.debug(f"STARTPARAM: {startapp_param}")
        
        # Define the request headers
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # get the user profiile photo
        bot_profile_photos = await bot.get_user_profile_photos(bot.id, limit=1)
        image = await bot_profile_photos.photos[0][0].get_file() if bot_profile_photos else None

        # Define the request body (data)
        data = {
            "userId": user.id,
            "firstName": user.first_name if user.first_name else None,
            "lastName": user.last_name if user.last_name else None,
            "image": image.file_path
        }

        # Make the POST request
        response = requests.post(url, headers=headers, json=data)
        LOGGER.debug(response)
        await update.message.reply_text(f"Hello {user.id}, \n<strong>LUNCH MINIAPP</strong>", parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        url = f"{Config.DOMAIN}/v2/auth/start"
        LOGGER.debug(f"START URL: {url}")

        # Define the request headers
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # get the user profiile photo
        bot_profile_photos = await bot.get_user_profile_photos(bot.id, limit=1)
        image = await bot_profile_photos.photos[0][0].get_file() if bot_profile_photos else None

        # Define the request body (data)
        data = {
            "userId": user.id,
            "firstName": user.first_name if user.first_name else None,
            "lastName": user.last_name if user.last_name else None,
            "image": image.file_path
        }

        # Make the POST request
        response = requests.post(url, headers=headers, json=data)
        LOGGER.debug(response)
        await update.message.reply_text(f"Hello {user.id}, \n<strong>LAUNCH MINIAPP</strong>.", parse_mode=ParseMode.HTML, reply_markup=reply_markup)

# Register the handler
telegramApp.add_handler(CommandHandler("start", start))

if __name__ == "__main__":
    telegramApp.run_polling()