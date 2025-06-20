import os
import logging
import asyncio
from io import BytesIO
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from huggingface_hub import InferenceClient

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ImageGeneratorBot:
    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.hf_token = os.environ.get("HF_TOKEN")

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set!")
        if not self.hf_token:
            raise ValueError("HF_TOKEN environment variable is not set!")

        # Initialize Hugging Face client correctly
        self.client = InferenceClient(token=self.hf_token)

        self.application = Application.builder().token(self.bot_token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup bot command and message handlers."""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.generate_image
        ))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message when /start is issued."""
        welcome_message = (
            "🎨 **AI Image Generator Bot**\n\n"
            "Send me any text description and I'll generate an image for you!\n\n"
            "**Examples:**\n"
            "• `Astronaut riding a horse`\n"
            "• `Beautiful sunset over mountains`\n"
            "• `Cute cat wearing sunglasses`\n"
            "• `Cyberpunk city at night`\n\n"
            "**Commands:**\n"
            "• `/start` - Show this welcome message\n"
            "• `/help` - Get detailed help\n"
            "• `/status` - Check bot status\n\n"
            "Just type your description and wait for the magic! ✨"
        )
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        logger.info(f"User {update.effective_user.id} started the bot")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send help message when /help is issued."""
        help_text = (
            "🤖 **How to use this bot:**\n\n"
            "1. Send me a text description of what you want to see\n"
            "2. Wait while I generate your image (this may take 10-30 seconds)\n"
            "3. Receive your AI-generated image!\n\n"
            "**Tips for better results:**\n"
            "• Be specific and descriptive\n"
            "• Include style keywords (e.g., 'photorealistic', 'cartoon', 'oil painting')\n"
            "• Mention colors, lighting, and mood\n"
            "• Be patient - high-quality AI art takes time! 🎨\n\n"
            "**Model:** Stable Diffusion\n"
            "**Mode:** Background Worker (Polling)"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send bot status information."""
        status_text = (
            "🟢 **Bot Status: Online**\n\n"
            "• **Mode:** Background Worker (Polling)\n"
            "• **Provider:** Hugging Face Inference API\n"
            "• **Status:** Ready to generate images\n\n"
            f"• **Your ID:** `{update.effective_user.id}`\n"
            f"• **Chat ID:** `{update.effective_chat.id}`"
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')

    async def generate_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Generate image from user's text description."""
        user_prompt = update.message.text.strip()
        user_id = update.effective_user.id

        if not user_prompt:
            await update.message.reply_text("Please provide a description for the image!")
            return

        if len(user_prompt) > 500:
            await update.message.reply_text("Please keep your description under 500 characters!")
            return

        logger.info(f"User {user_id} requested image: {user_prompt}")

        # Send generating message
        status_message = await update.message.reply_text(
            "🎨 **Generating your image...**\n\n"
            f"**Prompt:** `{user_prompt}`\n"
            "⏳ This may take 10-30 seconds...",
            parse_mode='Markdown'
        )

        try:
            # Generate image using Hugging Face Inference API
            logger.info(f"Starting image generation for user {user_id}")

            # Try different models in order of preference
            models_to_try = [
                "black-forest-labs/FLUX.1-dev",
                "stabilityai/stable-diffusion-xl-base-1.0", 
                "runwayml/stable-diffusion-v1-5"
            ]

            image = None
            used_model = None

            for model in models_to_try:
                try:
                    logger.info(f"Trying model: {model}")
                    image = self.client.text_to_image(user_prompt, model=model)
                    used_model = model
                    break
                except Exception as model_error:
                    logger.warning(f"Model {model} failed: {str(model_error)}")
                    continue

            if image is None:
                raise Exception("All models failed to generate image")

            # Convert PIL image to bytes
            img_buffer = BytesIO()
            image.save(img_buffer, format='PNG', quality=95)
            img_buffer.seek(0)

            # Send the image
            await update.message.reply_photo(
                photo=img_buffer,
                caption=f"🎨 **Generated Image**\n\n**Prompt:** `{user_prompt}`\n**Model:** `{used_model.split('/')[-1]}`",
                parse_mode='Markdown'
            )

            # Delete status message
            await status_message.delete()
            logger.info(f"Successfully generated image for user {user_id} using {used_model}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error generating image for user {user_id}: {error_msg}")

            await status_message.edit_text(
                f"❌ **Generation Failed**\n\n"
                f"Sorry, I couldn't generate an image for that prompt.\n"
                f"Please try again with a different description.\n\n"
                f"**Error:** `{error_msg[:100]}{'...' if len(error_msg) > 100 else ''}`",
                parse_mode='Markdown'
            )

    async def run_polling(self):
        """Run the bot with polling (background worker mode)."""
        logger.info("Starting Telegram bot in background worker mode...")

        try:
            # Initialize the bot
            await self.application.initialize()
            await self.application.start()

            # Start polling
            await self.application.updater.start_polling(
                poll_interval=1.0,
                timeout=30,
                bootstrap_retries=-1,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30,
            )

            logger.info("Bot is running and polling for updates...")

            # Keep the application running
            while True:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error in polling: {e}")
            raise
        finally:
            await self.application.stop()
            await self.application.shutdown()

async def main():
    """Main function to run the bot."""
    try:
        bot = ImageGeneratorBot()
        await bot.run_polling()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
