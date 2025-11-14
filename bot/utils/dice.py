"""Dice rolling utilities"""

import re
import random
from typing import Tuple, Optional


def roll_dice(dice_string: str) -> Tuple[int, str]:
    """
    Parse and roll dice notation (e.g., "2d6+3", "1d20", "d4-1")

    Args:
        dice_string: Dice notation string

    Returns:
        Tuple of (result, explanation_string)
    """
    # Remove whitespace
    dice_string = dice_string.strip().lower()

    # Pattern: [N]d[S][+/-M] or [N]d[S]
    pattern = r'(\d*)d(\d+)([+-]\d+)?'
    match = re.match(pattern, dice_string)

    if not match:
        raise ValueError(f"Invalid dice notation: {dice_string}")

    num_dice = int(match.group(1)) if match.group(1) else 1
    die_size = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0

    # Validate
    if num_dice < 1 or num_dice > 100:
        raise ValueError(f"Number of dice must be between 1 and 100, got: {num_dice}")
    if die_size < 2 or die_size > 100:
        raise ValueError(f"Die size must be between 2 and 100, got: {die_size}")

    # Roll dice
    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    # Build explanation
    rolls_str = ", ".join(map(str, rolls))
    explanation = f"[{rolls_str}]"
    if modifier != 0:
        explanation += f" {'+' if modifier >= 0 else ''}{modifier}"
    explanation += f" = **{total}**"

    return total, explanation


def parse_dice_command(command_text: str) -> Optional[str]:
    """
    Extract dice notation from a command string

    Args:
        command_text: Command text (e.g., "!roll 2d6+3" or "/roll d20")

    Returns:
        Dice notation string or None if not found
    """
    # Pattern: /roll or !roll followed by dice notation
    pattern = r'(?:/roll|!roll)\s+(.+)'
    match = re.search(pattern, command_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def roll_ability_check(modifier: int = 0) -> Tuple[int, str]:
    """
    Roll a d20 ability check

    Args:
        modifier: Ability modifier

    Returns:
        Tuple of (result, explanation_string)
    """
    roll = random.randint(1, 20)
    total = roll + modifier

    explanation = f"d20: **{roll}**"
    if modifier != 0:
        explanation += f" {'+' if modifier >= 0 else ''}{modifier}"
    explanation += f" = **{total}**"

    return total, explanation

