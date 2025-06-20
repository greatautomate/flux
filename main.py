import os
import logging
import asyncio
import time
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
        # Basic commands (work in both private and groups)
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status))

        # Group command for image generation
        self.application.add_handler(CommandHandler("medusaXD", self.medusa_command))

        # Private message handler (only in private chats)
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
            self.generate_image_private
        ))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message when /start is issued."""
        chat_type = "group" if update.effective_chat.type in ['group', 'supergroup'] else "private"

        if chat_type == "group":
            welcome_message = (
                "🎨 **AI Image Generator Bot - Group Mode**\n\n"
                "Use `/medusaXD <description>` to generate images in groups!\n\n"
                "**Examples:**\n"
                "• `/medusaXD Astronaut riding a horse`\n"
                "• `/medusaXD Beautiful sunset over mountains`\n"
                "• `/medusaXD Cute cat wearing sunglasses`\n\n"
                "**Other Commands:**\n"
                "• `/help` - Get detailed help\n"
                "• `/status` - Check bot status\n\n"
                "Ready to create amazing AI art! ✨"
            )
        else:
            welcome_message = (
                "🎨 **AI Image Generator Bot**\n\n"
                "**Private Chat Mode:** Send me any text description and I'll generate an image!\n"
                "**Group Mode:** Use `/medusaXD <description>` in groups!\n\n"
                "**Examples:**\n"
                "• `Astronaut riding a horse`\n"
                "• `Beautiful sunset over mountains`\n"
                "• `Cute cat wearing sunglasses`\n"
                "• `Cyberpunk city at night`\n\n"
                "**Commands:**\n"
                "• `/start` - Show this welcome message\n"
                "• `/help` - Get detailed help\n"
                "• `/status` - Check bot status\n"
                "• `/medusaXD <prompt>` - Generate image (groups)\n\n"
                "Just type your description and wait for the magic! ✨"
            )

        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        logger.info(f"User {update.effective_user.id} started the bot in {chat_type}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send help message when /help is issued."""
        chat_type = "group" if update.effective_chat.type in ['group', 'supergroup'] else "private"

        if chat_type == "group":
            help_text = (
                "🤖 **Group Mode - How to use:**\n\n"
                "Use `/medusaXD <description>` to generate images!\n\n"
                "**Example:**\n"
                "`/medusaXD A majestic dragon flying over a castle`\n\n"
                "**Tips for better results:**\n"
                "• Be specific and descriptive\n"
                "• Include style keywords (e.g., 'photorealistic', 'cartoon', 'oil painting')\n"
                "• Mention colors, lighting, and mood\n"
                "• Be patient - high-quality AI art takes time! 🎨\n\n"
                "**Models:** FLUX.1-dev, Stable Diffusion XL, SD v1.5"
            )
        else:
            help_text = (
                "🤖 **How to use this bot:**\n\n"
                "**Private Chat:** Send any text description\n"
                "**Groups:** Use `/medusaXD <description>`\n\n"
                "1. Send me a text description of what you want to see\n"
                "2. Wait while I generate your image (10-30 seconds)\n"
                "3. Receive your AI-generated image with generation time!\n\n"
                "**Tips for better results:**\n"
                "• Be specific and descriptive\n"
                "• Include style keywords (e.g., 'photorealistic', 'cartoon', 'oil painting')\n"
                "• Mention colors, lighting, and mood\n"
                "• Be patient - high-quality AI art takes time! 🎨\n\n"
                "**Models:** FLUX.1-dev, Stable Diffusion XL, SD v1.5\n"
                "**Mode:** Background Worker (Polling)"
            )

        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send bot status information."""
        chat_type = "group" if update.effective_chat.type in ['group', 'supergroup'] else "private"

        status_text = (
            "🟢 **Bot Status: Online**\n\n"
            f"• **Chat Type:** {chat_type.title()}\n"
            "• **Mode:** Background Worker (Polling)\n"
            "• **Provider:** Hugging Face Inference API\n"
            "• **Status:** Ready to generate images\n"
            "• **Time Tracking:** Enabled ⏱️\n\n"
            f"• **Your ID:** `{update.effective_user.id}`\n"
            f"• **Chat ID:** `{update.effective_chat.id}`\n\n"
            f"**Usage:** {'Use /medusaXD <prompt>' if chat_type == 'group' else 'Send any text description'}"
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')

    async def medusa_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /medusaXD command for groups."""
        # Get the prompt from command arguments
        if not context.args:
            await update.message.reply_text(
                "❗ **Usage:** `/medusaXD <description>`\n\n"
                "**Example:** `/medusaXD Astronaut riding a horse`",
                parse_mode='Markdown'
            )
            return

        user_prompt = ' '.join(context.args).strip()
        await self.generate_image_logic(update, user_prompt, is_group=True)

    async def generate_image_private(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Generate image from private chat message."""
        user_prompt = update.message.text.strip()
        await self.generate_image_logic(update, user_prompt, is_group=False)

    async def generate_image_logic(self, update: Update, user_prompt: str, is_group: bool = False) -> None:
        """Core logic for image generation with time tracking."""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name or "Unknown"

        if not user_prompt:
            await update.message.reply_text("Please provide a description for the image!")
            return

        if len(user_prompt) > 500:
            await update.message.reply_text("Please keep your description under 500 characters!")
            return

        logger.info(f"User {user_id} ({username}) requested image: {user_prompt}")

        # Record start time
        start_time = time.time()

        # Send generating message
        command_text = f"/medusaXD {user_prompt}" if is_group else user_prompt
        status_message = await update.message.reply_text(
            "🎨 **Generating your image...**\n\n"
            f"**Prompt:** `{user_prompt}`\n"
            f"**Requested by:** @{username}\n"
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
            generation_start = time.time()

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

            generation_time = time.time() - generation_start
            total_time = time.time() - start_time

            # Convert PIL image to bytes
            img_buffer = BytesIO()
            image.save(img_buffer, format='PNG', quality=95)
            img_buffer.seek(0)

            # Format time display
            def format_time(seconds):
                if seconds < 1:
                    return f"{seconds:.2f}s"
                else:
                    return f"{seconds:.1f}s"

            # Send the image with time information
            caption = (
                f"🎨 **Generated Image**\n\n"
                f"**Prompt:** `{user_prompt}`\n"
                f"**Model:** `{used_model.split('/')[-1]}`\n"
                f"**Requested by:** @{username}\n"
                f"⏱️ **Generation Time:** {format_time(generation_time)}\n"
                f"🕐 **Total Time:** {format_time(total_time)}"
            )

            await update.message.reply_photo(
                photo=img_buffer,
                caption=caption,
                parse_mode='Markdown'
            )

            # Delete status message
            await status_message.delete()
            logger.info(f"Successfully generated image for user {user_id} using {used_model} in {generation_time:.2f}s")

        except Exception as e:
            error_msg = str(e)
            error_time = time.time() - start_time
            logger.error(f"Error generating image for user {user_id}: {error_msg}")

            await status_message.edit_text(
                f"❌ **Generation Failed**\n\n"
                f"Sorry, I couldn't generate an image for that prompt.\n"
                f"Please try again with a different description.\n\n"
                f"**Prompt:** `{user_prompt}`\n"
                f"**Requested by:** @{username}\n"
                f"⏱️ **Time elapsed:** {error_time:.1f}s\n"
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
            logger.info("Private chats: Send text descriptions directly")
            logger.info("Groups: Use /medusaXD <description>")

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
