"""Command parsing logic"""

import re
import logging
from typing import Dict, Optional, Tuple
from config.settings import settings

logger = logging.getLogger(__name__)


class CommandParser:
    """Parse and extract command information from messages"""

    def __init__(self):
        """Initialize command parser"""
        self.command_prefix = settings.COMMAND_PREFIX

    def parse_command(self, message_text: str) -> Optional[Dict[str, any]]:
        """
        Parse a command from message text

        Args:
            message_text: Raw message text

        Returns:
            Dictionary with command info or None if not a valid command
            Format: {
                "command": "create",
                "args": {...},  # Parsed arguments
                "raw_args": "...",  # Raw argument string
                "is_admin": False  # Whether it's an admin command
            }
        """
        message_text = message_text.strip()

        # Check for prefix command (!command) or slash command (/command)
        if not (message_text.startswith(self.command_prefix) or message_text.startswith('/')):
            return None

        # Remove prefix or slash
        if message_text.startswith(self.command_prefix):
            command_text = message_text[len(self.command_prefix):].strip()
        else:
            command_text = message_text[1:].strip()

        if not command_text:
            return None

        # Split command and arguments
        parts = command_text.split(None, 1)
        command_name = parts[0].lower()
        raw_args = parts[1] if len(parts) > 1 else ""

        # Check if it's an admin command
        is_admin = command_name.startswith("dm")

        # Parse arguments based on command type
        args = self._parse_args(command_name, raw_args)

        return {
            "command": command_name,
            "args": args,
            "raw_args": raw_args,
            "is_admin": is_admin
        }

    def _parse_args(self, command: str, raw_args: str) -> Dict[str, any]:
        """Parse arguments based on command type"""
        args = {}

        if command == "create":
            # Parse character creation: name:Thorne class:Paladin str:15 dex:12 ...
            args = self._parse_key_value_args(raw_args)
        elif command in ["action", "dm", "dm start", "dm add encounter", "dm set location"]:
            # These commands take a description/text argument
            args["description"] = raw_args
        elif command == "dm validate":
            # Can have optional player mention
            args["player"] = raw_args.strip() if raw_args else None
        elif command == "roll":
            # Parse dice notation
            args["dice"] = raw_args.strip() if raw_args else "1d20"
        elif command in ["stats", "inventory"]:
            # No arguments needed
            pass
        elif command == "help":
            # Can have optional topic argument
            if raw_args:
                args["description"] = raw_args.strip()

        return args

    def _parse_key_value_args(self, text: str) -> Dict[str, str]:
        """
        Parse key:value arguments from text

        Example: "name:Thorne class:Paladin backstory:\"Former knight\" str:15"
        """
        args = {}
        # Pattern to match key:value pairs, handling quoted values
        pattern = r'(\w+):(?:(".*?")|([^\s]+))'
        matches = re.findall(pattern, text)

        for match in matches:
            key = match[0].lower()
            value = match[1] or match[2]
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            args[key] = value

        return args

    def extract_stats_from_args(self, args: Dict[str, str]) -> Optional[Dict[str, int]]:
        """
        Extract stat values from parsed arguments

        Args:
            args: Parsed arguments dictionary

        Returns:
            Dictionary with stat names and values, or None if missing
        """
        stat_names = ["str", "dex", "con", "int", "wis", "cha"]
        stats = {}

        for stat in stat_names:
            if stat in args:
                try:
                    stats[stat.upper()] = int(args[stat])
                except ValueError:
                    return None

        # Return None if no stats found
        return stats if stats else None


# Global parser instance
command_parser = CommandParser()

