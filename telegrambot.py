from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import requests
import json
import openai
import os
import logging
import traceback
from PIL import Image
import io
import tempfile

TELEGRAM_BOT_TOKEN = "6639560122:AAHepSehnbi_ZWLzFMtEliy33zDBsm7nFjc"

# Set logging level for debugging
logging.basicConfig(level=logging.INFO)


def create_temp_directory(temp_dir_name="tempdir"):
    # Get the absolute path to the current directory
    current_directory = os.getcwd()

    # Combine the current directory with your temp directory name
    temp_directory = os.path.join(current_directory, temp_dir_name)

    # Ensure the temporary directory exists
    if not os.path.exists(temp_directory):
        os.makedirs(temp_directory)
    return temp_directory


temp_directory = create_temp_directory()

FLASK_APP_URL = "http://127.0.0.1:5000/api/chatbot"  # URL to your Flask app

logging.basicConfig(level=logging.INFO)

temp_directory = tempfile.mkdtemp()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hello! I am your assistant, how can I help you?")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    try:
        response = requests.post(FLASK_APP_URL, json={"message": user_message})
        if response.status_code == 200:
            response_data = response.json()
            if isinstance(response_data, dict) and "response" in response_data:
                bot_response = response_data["response"]
                await update.message.reply_text(bot_response)
            elif isinstance(response_data, list):
                for message in response_data:
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, list) and len(content) > 0:
                            text = content[0].get("text", {}).get("value", "")
                            await update.message.reply_text(text)
            else:
                await update.message.reply_text("Sorry, I couldn't process your request.")
        else:
            logging.error(f"API Error: {response.status_code}")
            await update.message.reply_text("Error processing your request.")
    except Exception as e:
        logging.error(f"Exception: {e}")
        await update.message.reply_text("An error occurred.")
# Async function to process an image
async def process_image(update, context):
    # Check if there's a photo in the update
    if update.message.photo:
        # Get the highest resolution photo
        photo = update.message.photo[-1]

        photo_file = await context.bot.getFile(photo.file_id)

        # Downloading the file as bytes
        photo_bytes = await photo_file.download_as_bytearray()
        image_stream = io.BytesIO(photo_bytes)
        image_stream.seek(0)

        # Open the image and determine its format
        with Image.open(image_stream) as image:
            format = image.format.lower()  # e.g., 'jpeg', 'png', etc.
        try:
            # Save the file with the appropriate extension
            temp = tempfile.NamedTemporaryFile(dir=temp_directory)
            temp_file = temp.name + f".{format}"
            # filename = tempdir + "/" + f"{photo.file_id}.{format}"
            with open(temp_file, "wb") as file:
                file.write(photo_bytes)

            # description = requests.post(
            #     "http://localhost:8690/read_image", files={"file": filename}
            # )
            with open(temp_file, "rb") as file:
                description = requests.post(
                    "http://localhost:8690/read_image",
                    files={"file": (temp_file, file, "image/jpeg")},
                ).json()
            print("description :", description)

            # Reply to the user after processing
            await update.message.reply_text(description["response"])
        except Exception as e:
            await update.message.reply_text("ERROR:", str(e))

        finally:
            try:
                os.unlink(temp_file)  # Delete the file
            except Exception as e:
                # Handle or log the error of file deletion
                pass


if __name__ == "__main__":
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.PHOTO, process_image))
    application.run_polling()