"""Discord platform implementation"""

import discord
from discord.ext import commands
from typing import Dict, Any, Callable, Optional
import logging

from bot.platforms.base import PlatformBot
from config.settings import settings

logger = logging.getLogger(__name__)


class DiscordBot(PlatformBot):
    """Discord bot implementation"""

    def __init__(self):
        """Initialize Discord bot"""
        intents = discord.Intents.default()
        intents.message_content = True  # Required for reading message content
        intents.members = True  # Required for checking roles

        self.bot = commands.Bot(command_prefix=settings.COMMAND_PREFIX, intents=intents)
        self.message_callback: Optional[Callable] = None

        # Register event handlers
        self.bot.event(self.on_ready)
        self.bot.event(self.on_message)

    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"{self.bot.user} has connected to Discord!")
        if settings.DISCORD_GUILD_ID:
            guild = discord.utils.get(self.bot.guilds, id=int(settings.DISCORD_GUILD_ID))
            if guild:
                logger.info(f"Connected to guild: {guild.name}")

    async def on_message(self, message: discord.Message):
        """Called when a message is received"""
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return

        # Only process commands and messages in text channels
        if not isinstance(message.channel, discord.TextChannel):
            return

        # Check if it's a command
        is_command = message.content.startswith(settings.COMMAND_PREFIX) or (
            message.content.startswith('/') and len(message.content) > 1 and message.content[1].isalpha()
        )

        # Call the registered callback if it exists
        if self.message_callback:
            try:
                await self.message_callback(
                    str(message.author.id),
                    str(message.channel.id),
                    message.content,
                    is_command,
                    message
                )
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        # Process commands normally
        await self.bot.process_commands(message)

    async def send_message(self, channel_id: str, message: str, embed: Optional[Dict[str, Any]] = None) -> None:
        """Send a message to a Discord channel"""
        try:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                # Create Discord embed if provided
                discord_embed = None
                if embed:
                    discord_embed = discord.Embed(
                        title=embed.get("title"),
                        description=embed.get("description"),
                        color=embed.get("color", 0x3498db)
                    )
                    if embed.get("fields"):
                        for field in embed["fields"]:
                            discord_embed.add_field(
                                name=field.get("name", ""),
                                value=field.get("value", ""),
                                inline=field.get("inline", False)
                            )
                    if embed.get("footer"):
                        discord_embed.set_footer(text=embed.get("footer"))

                await channel.send(content=message, embed=discord_embed)
            else:
                logger.warning(f"Channel {channel_id} not found")
        except Exception as e:
            logger.error(f"Error sending message to {channel_id}: {e}")

    async def listen_for_messages(self, callback: Callable) -> None:
        """Register callback for incoming messages"""
        self.message_callback = callback

    def parse_user_info(self, message: Any) -> Dict[str, Any]:
        """Extract user information from Discord message"""
        if isinstance(message, discord.Message):
            return {
                "user_id": str(message.author.id),
                "username": message.author.name,
                "channel_id": str(message.channel.id),
                "guild_id": str(message.guild.id) if message.guild else None,
                "message_text": message.content,
                "is_command": message.content.startswith(settings.COMMAND_PREFIX) or (
                    message.content.startswith('/') and len(message.content) > 1
                )
            }
        return {}

    def format_response(self, message: str, **kwargs) -> str:
        """Format response message (Discord supports markdown natively)"""
        # Discord supports markdown, so we can return as-is
        return message

    def get_user_id(self, message: Any) -> str:
        """Get Discord user ID from message"""
        if isinstance(message, discord.Message):
            return str(message.author.id)
        return ""

    async def is_admin(self, user_id: str, channel_id: str) -> bool:
        """Check if user is admin/DM"""
        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                return False

            guild = channel.guild
            member = guild.get_member(int(user_id))
            if not member:
                return False

            # Check if user has admin role
            admin_role = discord.utils.get(guild.roles, name=settings.ADMIN_ROLE_NAME)
            if admin_role and admin_role in member.roles:
                return True

            # Check if user is guild owner or administrator
            if member.guild_permissions.administrator:
                return True

            return False
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    async def start(self) -> None:
        """Start the Discord bot"""
        if not settings.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN not set in configuration")
        await self.bot.start(settings.DISCORD_TOKEN)

    async def close(self) -> None:
        """Close the Discord bot connection"""
        await self.bot.close()

    def get_bot(self) -> commands.Bot:
        """Get the underlying discord.py bot instance"""
        return self.bot

