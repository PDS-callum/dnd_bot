"""Base platform interface for abstracting Discord and WhatsApp"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional


class PlatformBot(ABC):
    """Abstract base class for platform-specific bot implementations"""

    @abstractmethod
    async def send_message(self, channel_id: str, message: str, embed: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a message to a channel/group

        Args:
            channel_id: Platform-specific channel/group identifier
            message: Text message to send
            embed: Optional rich embed/dictionary for formatted messages
        """
        pass

    @abstractmethod
    async def listen_for_messages(self, callback: Callable) -> None:
        """
        Start listening for incoming messages and call callback

        Args:
            callback: Async function to call when message received
                     Should receive (user_id, channel_id, message_text, is_command)
        """
        pass

    @abstractmethod
    def parse_user_info(self, message: Any) -> Dict[str, Any]:
        """
        Extract user information from a message object

        Args:
            message: Platform-specific message object

        Returns:
            Dictionary with keys: user_id, username, channel_id, message_text
        """
        pass

    @abstractmethod
    def format_response(self, message: str, **kwargs) -> Any:
        """
        Format a response message for the platform

        Args:
            message: Text message to format
            **kwargs: Platform-specific formatting options

        Returns:
            Platform-specific formatted message object
        """
        pass

    @abstractmethod
    def get_user_id(self, message: Any) -> str:
        """
        Get platform-specific user ID from message

        Args:
            message: Platform-specific message object

        Returns:
            User ID string
        """
        pass

    @abstractmethod
    async def is_admin(self, user_id: str, channel_id: str) -> bool:
        """
        Check if a user is an admin/DM

        Args:
            user_id: Platform-specific user ID
            channel_id: Platform-specific channel/group ID

        Returns:
            True if user is admin
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start the bot connection"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the bot connection"""
        pass

