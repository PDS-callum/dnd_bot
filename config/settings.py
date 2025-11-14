"""Configuration settings for the D&D bot"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings"""

    # Discord settings
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
    DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", None)  # Optional, for slash command testing
    ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "DM")  # Discord role name for admins
    COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")  # Command prefix (! or /)
    
    # Bot access control (optional - restrict to specific servers)
    ALLOWED_GUILD_IDS = os.getenv("ALLOWED_GUILD_IDS", "").split(",") if os.getenv("ALLOWED_GUILD_IDS") else []  # Comma-separated list of allowed server IDs
    RESTRICT_TO_ALLOWED_SERVERS = os.getenv("RESTRICT_TO_ALLOWED_SERVERS", "false").lower() == "true"  # Set to true to only allow specific servers

    # Ollama settings
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")  # Default to llama3.2 if available

    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/game.db")

    # Stat validation rules (D&D 5e point buy system)
    STAT_POINT_BUY_MAX = 27  # Total points available
    STAT_MAX = 15  # Maximum stat before racial bonuses
    STAT_MIN = 8  # Minimum stat
    STAT_POINT_COSTS = {
        8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5,
        14: 7, 15: 9, 16: 12, 17: 15, 18: 19
    }

    # Game rules
    DEFAULT_MOVEMENT_SPEED = 30  # feet per turn
    DEFAULT_HP = 20  # Starting HP
    ACTION_PER_TURN = 1  # Number of actions per turn
    BONUS_ACTION_PER_TURN = 1  # Number of bonus actions per turn
    REACTION_PER_ROUND = 1  # Number of reactions per round

    # Round/turn management
    ROUND_TIMEOUT_SECONDS = int(os.getenv("ROUND_TIMEOUT_SECONDS", "300"))  # 5 minutes default
    MIN_PLAYERS_FOR_ROUND = int(os.getenv("MIN_PLAYERS_FOR_ROUND", "1"))  # Minimum players needed

    # Inventory settings
    BASE_CARRYING_CAPACITY = 15  # STR multiplier for weight (15 * STR = max pounds)
    ENCUMBRANCE_THRESHOLD = 0.9  # 90% capacity warning

    def validate(self):
        """Validate required settings"""
        if not self.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required in .env file")
        return True


# Global settings instance
settings = Settings()

