"""Main application entry point for D&D Discord Bot"""

import asyncio
import logging
import os
from typing import Dict, List, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

from bot.platforms.discord import DiscordBot
from bot.commands.parser import command_parser
from bot.commands.player import get_player_handler
from bot.commands.admin import get_admin_handler
from bot.game.models import Base
from bot.game.engine import get_game_engine
from bot.game.state import get_state_manager
from bot.ai.ollama_client import ollama_client
from config.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure data directory exists for SQLite database
if "sqlite" in settings.DATABASE_URL:
    # Extract database path from URL (sqlite:///data/game.db -> data/game.db)
    db_path = settings.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    if "/" in db_path or "\\" in db_path:
        # Extract directory path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    else:
        # Default to data directory
        os.makedirs("data", exist_ok=True)

# Database setup
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in settings.DATABASE_URL else None,
    echo=False
)
Base.metadata.create_all(engine)
SessionLocal = scoped_session(sessionmaker(bind=engine))


class DnDBot:
    """Main bot class"""

    def __init__(self):
        """Initialize the bot"""
        self.db_session = SessionLocal()
        self.platform_bot = DiscordBot()
        self.game_engine = None
        self.round_processor_task = None

    async def ai_story_callback(self, game_state: Dict, player_actions: List[Dict]) -> str:
        """Callback for AI story generation"""
        return await ollama_client.generate_story(game_state, player_actions)

    async def message_handler(self, user_id: str, channel_id: str, message_text: str, is_command: bool, message_obj: Any):
        """Handle incoming messages"""
        try:
            # Only process commands
            if not is_command:
                return

            # Parse command
            parsed = command_parser.parse_command(message_text)
            if not parsed:
                return

            command = parsed["command"]
            args = parsed["args"]
            is_admin_cmd = parsed["is_admin"]

            # Get guild ID from message
            guild_id = None
            if hasattr(message_obj, 'guild') and message_obj.guild:
                guild_id = str(message_obj.guild.id)

            # Route to appropriate handler
            if is_admin_cmd:
                # Check if user is admin
                is_admin = await self.platform_bot.is_admin(user_id, channel_id)
                if not is_admin:
                    await self.platform_bot.send_message(
                        channel_id,
                        "❌ You don't have permission to use DM commands. You need the DM role or administrator permissions."
                    )
                    return

                # Handle admin command
                admin_handler = get_admin_handler(self.db_session)

                if command == "dm" or command == "dm start":
                    response = await admin_handler.handle_dm_start(user_id, channel_id, guild_id or "", args)
                elif command == "dm pause":
                    response = await admin_handler.handle_dm_pause(user_id, channel_id)
                elif command == "dm resume":
                    response = await admin_handler.handle_dm_resume(user_id, channel_id)
                elif command == "dm end":
                    response = await admin_handler.handle_dm_end(user_id, channel_id)
                elif command == "dm add encounter" or command == "dm add":
                    response = await admin_handler.handle_dm_add_encounter(user_id, channel_id, args)
                elif command == "dm set location" or command == "dm location":
                    response = await admin_handler.handle_dm_set_location(user_id, channel_id, args)
                elif command == "dm validate":
                    response = await admin_handler.handle_dm_validate(user_id, args)
                else:
                    response = {"message": f"❌ Unknown admin command: {command}", "embed": None}

            else:
                # Handle player command
                player_handler = get_player_handler(self.db_session)

                if command == "create":
                    response = await player_handler.handle_create(user_id, args)
                elif command == "action":
                    response = await player_handler.handle_action(user_id, channel_id, args)
                elif command == "stats":
                    response = await player_handler.handle_stats(user_id)
                elif command == "inventory":
                    response = await player_handler.handle_inventory(user_id)
                elif command == "roll":
                    response = await player_handler.handle_roll(user_id, args)
                elif command == "help":
                    # Get topic from args if provided
                    topic = args.get("description", "").strip() if args.get("description") else None
                    response = await player_handler.handle_help(user_id, topic)
                else:
                    response = {"message": f"❌ Unknown command: {command}. Type `!help` for available commands.", "embed": None}

            # Send response
            if response:
                message = response.get("message")
                embed = response.get("embed")
                if message or embed:
                    await self.platform_bot.send_message(channel_id, message or "", embed)

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            try:
                await self.platform_bot.send_message(
                    channel_id,
                    f"❌ An error occurred processing your command: {str(e)}"
                )
            except:
                pass

    async def start(self):
        """Start the bot"""
        try:
            # Validate settings
            settings.validate()

            # Test Ollama connection
            logger.info("Testing Ollama connection...")
            if await ollama_client.test_connection():
                logger.info(f"✓ Ollama connected at {settings.OLLAMA_URL}")
            else:
                logger.warning(f"⚠ Ollama not available at {settings.OLLAMA_URL}. Story generation may fail.")

            # Initialize game engine with AI callback
            self.game_engine = get_game_engine(self.db_session, self.ai_story_callback)

            # Register message handler
            await self.platform_bot.listen_for_messages(self.message_handler)

            # Register Discord slash commands (if needed)
            # For now, using prefix commands

            # Start round processor task
            self.round_processor_task = asyncio.create_task(
                self.game_engine.start_round_processor(interval=30)
            )

            # Start the bot
            logger.info("Starting Discord bot...")
            await self.platform_bot.start()

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error starting bot: {e}", exc_info=True)
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources"""
        if self.round_processor_task:
            self.round_processor_task.cancel()
            try:
                await self.round_processor_task
            except asyncio.CancelledError:
                pass

        await self.platform_bot.close()
        self.db_session.close()


async def main():
    """Main entry point"""
    bot = DnDBot()
    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

