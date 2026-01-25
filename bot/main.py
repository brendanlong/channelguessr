"""Main entry point for the Channelguessr bot."""

import asyncio
import logging
import sys
from pathlib import Path

import discord
from discord.ext import commands

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.services.game_service import GameService
from config import Config
from db.database import Database

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ChannelguessrBot(commands.Bot):
    """Custom bot class with database and game service."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True

        super().__init__(
            command_prefix="!",  # Fallback prefix, using slash commands primarily
            intents=intents,
            help_command=None,
        )

        self.db: Database = None
        self.game_service: GameService = None

    async def setup_hook(self):
        """Called when the bot is starting up."""
        # Initialize database
        self.db = Database(Config.DATABASE_PATH)
        await self.db.connect()
        logger.info(f"Connected to database: {Config.DATABASE_PATH}")

        # Initialize game service
        self.game_service = GameService(self, self.db)

        # Load cogs
        cogs = [
            "bot.commands.game",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

        # Sync slash commands
        logger.info("Syncing slash commands...")
        await self.tree.sync()
        logger.info("Slash commands synced!")

    async def on_ready(self):
        """Called when the bot is fully ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Clean up data for guilds the bot is no longer in
        await self._cleanup_orphaned_guild_data()

    async def _cleanup_orphaned_guild_data(self):
        """Delete data for guilds the bot is no longer a member of."""
        if not self.db:
            return

        current_guild_ids = {str(guild.id) for guild in self.guilds}
        stored_guild_ids = await self.db.get_all_guild_ids()
        orphaned_guild_ids = stored_guild_ids - current_guild_ids

        for guild_id in orphaned_guild_ids:
            logger.info(f"Cleaning up orphaned data for guild {guild_id}")
            await self.db.delete_guild_data(guild_id)

        if orphaned_guild_ids:
            logger.info(f"Cleaned up data for {len(orphaned_guild_ids)} orphaned guild(s)")

    async def on_guild_remove(self, guild: discord.Guild):
        """Called when the bot is removed from a guild. Deletes all guild data."""
        logger.info(f"Removed from guild: {guild.name} (ID: {guild.id})")
        if self.db:
            await self.db.delete_guild_data(str(guild.id))

        # Set activity
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name="/channelguessr start",
        )
        await self.change_presence(activity=activity)

    async def close(self):
        """Clean up resources."""
        if self.db:
            await self.db.close()
        await super().close()


async def main():
    """Main entry point."""
    if not Config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set! Please set it in your .env file.")
        sys.exit(1)

    bot = ChannelguessrBot()

    try:
        await bot.start(Config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord token! Please check your .env file.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
