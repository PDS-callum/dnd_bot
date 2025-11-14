"""Validation system for stats and actions"""

from typing import Dict, Tuple, Optional, List
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised for validation errors"""
    pass


class StatValidator:
    """Validate character stat allocation"""

    @staticmethod
    def validate_stat_allocation(stats: Dict[str, int]) -> Tuple[bool, Optional[str]]:
        """
        Validate stat point allocation using D&D 5e point buy system

        Args:
            stats: Dictionary with stat names (STR, DEX, CON, INT, WIS, CHA) and values

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if all required stats are present
        required_stats = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        for stat in required_stats:
            if stat not in stats:
                return False, f"Missing stat: {stat}"

        # Check individual stat limits
        for stat_name, value in stats.items():
            if value > settings.STAT_MAX:
                return False, f"{stat_name} exceeds maximum: {value} (max: {settings.STAT_MAX})"
            if value < settings.STAT_MIN:
                return False, f"{stat_name} below minimum: {value} (min: {settings.STAT_MIN})"

        # Calculate total points used
        total_points = 0
        for stat_name, value in stats.items():
            if value in settings.STAT_POINT_COSTS:
                total_points += settings.STAT_POINT_COSTS[value]
            else:
                # Value outside valid range
                return False, f"{stat_name} has invalid value: {value} (valid range: 8-15)"

        # Check if total exceeds limit
        if total_points > settings.STAT_POINT_BUY_MAX:
            return False, (
                f"Total points exceeded: {total_points}/{settings.STAT_POINT_BUY_MAX}. "
                f"Please redistribute your stat points."
            )

        return True, None

    @staticmethod
    def get_stat_modifier(stat_value: int) -> int:
        """Calculate ability modifier from stat value"""
        return (stat_value - 10) // 2


class ActionValidator:
    """Validate player actions"""

    @staticmethod
    def validate_action(
        player,
        action_text: str,
        game_state: Dict,
        turn_order: Optional[List[int]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a player action is allowed

        Args:
            player: Player model object
            action_text: Action description
            game_state: Current game state dictionary
            turn_order: Optional list of player IDs in turn order

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation - check if player has HP
        if player.hp <= 0:
            return False, "You are unconscious and cannot act!"

        # Check if it's player's turn (if turn order is enforced)
        if turn_order:
            current_player_id = game_state.get("current_turn")
            if current_player_id and player.id != current_player_id:
                return False, "It's not your turn!"

        # Action-specific validation could go here
        # For now, we allow most actions and let the AI handle restrictions

        return True, None

    @staticmethod
    def validate_movement(player, distance: int, game_state: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate movement distance

        Args:
            player: Player model object
            distance: Distance to move in feet
            game_state: Current game state dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get player's movement speed (default 30ft)
        movement_speed = settings.DEFAULT_MOVEMENT_SPEED

        # Could factor in player stats (e.g., encumbrance, class abilities)
        if distance > movement_speed:
            return False, (
                f"Movement exceeds your speed: {distance}ft (max: {movement_speed}ft). "
                f"Use dash action to move {movement_speed * 2}ft total."
            )

        return True, None

    @staticmethod
    def validate_inventory_weight(player, new_item_weight: float = 0) -> Tuple[bool, Optional[str]]:
        """
        Validate inventory weight capacity

        Args:
            player: Player model object
            new_item_weight: Weight of item being added (default 0 for check only)

        Returns:
            Tuple of (is_valid, error_message, current_weight, max_weight)
        """
        # Calculate carrying capacity (15 * STR)
        str_value = player.stats.get("STR", 10)
        max_weight = settings.BASE_CARRYING_CAPACITY * str_value

        # Calculate current weight from inventory
        inventory = player.inventory if isinstance(player.inventory, dict) else {}
        items = inventory.get("items", [])
        
        current_weight = sum(item.get("weight", 0) for item in items)
        new_total = current_weight + new_item_weight

        if new_total > max_weight:
            return False, (
                f"Inventory full: {new_total:.1f}/{max_weight:.1f} lbs. "
                f"Drop items first to add this item."
            )

        if new_total > max_weight * settings.ENCUMBRANCE_THRESHOLD:
            return False, (
                f"Warning: Adding this item would exceed {settings.ENCUMBRANCE_THRESHOLD * 100}% "
                f"capacity ({new_total:.1f}/{max_weight:.1f} lbs). Consider dropping items."
            )

        return True, None

    @staticmethod
    def validate_hp_change(player, change: int, is_healing: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validate HP changes

        Args:
            player: Player model object
            change: Amount of HP to change (positive for healing, negative for damage)
            is_healing: Whether this is healing

        Returns:
            Tuple of (is_valid, error_message)
        """
        if is_healing:
            # Can't heal above max HP
            if player.hp + change > player.max_hp:
                return False, f"Healing exceeds max HP: {player.hp + change}/{player.max_hp}"
        else:
            # Damage - check if it would kill player (go below -CON score)
            con_value = player.stats.get("CON", 10)
            death_threshold = -con_value
            new_hp = player.hp - change

            if new_hp < death_threshold:
                return False, f"Damage would cause death: HP would go to {new_hp} (death at {death_threshold})"

        return True, None


class ValidationSystem:
    """Main validation system"""

    def __init__(self):
        self.stat_validator = StatValidator()
        self.action_validator = ActionValidator()

    def validate_character_creation(self, stats: Dict[str, int]) -> Tuple[bool, Optional[str]]:
        """Validate character creation stats"""
        return self.stat_validator.validate_stat_allocation(stats)

    def validate_player_action(self, player, action_text: str, game_state: Dict) -> Tuple[bool, Optional[str]]:
        """Validate a player action"""
        return self.action_validator.validate_action(player, action_text, game_state)

    def validate_movement(self, player, distance: int, game_state: Dict) -> Tuple[bool, Optional[str]]:
        """Validate movement"""
        return self.action_validator.validate_movement(player, distance, game_state)

    def validate_inventory(self, player, new_item_weight: float = 0) -> Tuple[bool, Optional[str]]:
        """Validate inventory"""
        return self.action_validator.validate_inventory_weight(player, new_item_weight)

    def validate_hp(self, player, change: int, is_healing: bool = False) -> Tuple[bool, Optional[str]]:
        """Validate HP change"""
        return self.action_validator.validate_hp_change(player, change, is_healing)


# Global validation system instance
validation_system = ValidationSystem()

