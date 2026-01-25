"""Main entry point for the Discord Geoguessr bot."""

import discord
from discord.ext import commands
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from db.database import Database
from bot.services.game_service import GameService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GeoguessrBot(commands.Bot):
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

        # Set activity
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name="/geoguessr start",
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

    bot = GeoguessrBot()

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
