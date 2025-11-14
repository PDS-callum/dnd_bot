"""Player commands handler"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from bot.game.models import Player, Game, GamePlayer, Action, Base, GameStatus
from bot.game.validation import validation_system, ValidationError
from bot.commands.parser import command_parser
from bot.utils.dice import roll_dice, parse_dice_command, roll_ability_check
from config.settings import settings

logger = logging.getLogger(__name__)


class PlayerCommandHandler:
    """Handle player commands"""

    def __init__(self, db_session: Session):
        """Initialize with database session"""
        self.db = db_session

    async def handle_create(self, user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle character creation command

        Args:
            user_id: Platform user ID
            args: Parsed command arguments

        Returns:
            Response dictionary with message and embed info
        """
        # Check if player already exists
        existing_player = self.db.query(Player).filter_by(platform_user_id=user_id).first()
        if existing_player:
            return {
                "message": f"❌ You already have a character: **{existing_player.name}**",
                "embed": None
            }

        # Extract character info
        name = args.get("name", "").strip()
        class_name = args.get("class", "").strip()
        backstory = args.get("backstory", "").strip()

        if not name:
            return {
                "message": "❌ Character name is required. Usage: `/create name:Thorne class:Paladin str:15 ...`",
                "embed": None
            }
        if not class_name:
            return {
                "message": "❌ Character class is required. Usage: `/create name:Thorne class:Paladin str:15 ...`",
                "embed": None
            }

        # Extract stats
        stats = command_parser.extract_stats_from_args(args)
        if not stats:
            return {
                "message": (
                    "❌ Stats are required. Usage: `/create name:Thorne class:Paladin "
                    "str:15 dex:12 con:14 int:10 wis:13 cha:13`"
                ),
                "embed": None
            }

        # Validate stats
        is_valid, error_msg = validation_system.validate_character_creation(stats)
        if not is_valid:
            return {
                "message": f"❌ {error_msg}",
                "embed": None
            }

        # Calculate HP (default for now, could be class-based)
        max_hp = settings.DEFAULT_HP

        # Create player
        player = Player(
            platform_user_id=user_id,
            name=name,
            class_name=class_name,
            backstory=backstory if backstory else None,
            stats=stats,
            hp=max_hp,
            max_hp=max_hp,
            inventory={"items": []}
        )

        self.db.add(player)
        self.db.commit()

        # Create response embed
        embed = self._create_character_sheet_embed(player)

        return {
            "message": f"✅ Character **{name}** created successfully!",
            "embed": embed
        }

    async def handle_action(self, user_id: str, channel_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle player action command

        Args:
            user_id: Platform user ID
            channel_id: Channel/group ID
            args: Parsed command arguments

        Returns:
            Response dictionary
        """
        # Find player
        player = self.db.query(Player).filter_by(platform_user_id=user_id).first()
        if not player:
            return {
                "message": "❌ You don't have a character yet. Use `/create` to create one.",
                "embed": None
            }

        # Find active game in this channel
        game = self.db.query(Game).filter_by(
            channel_id=channel_id,
            status=GameStatus.ACTIVE
        ).first()

        if not game:
            return {
                "message": "❌ No active game in this channel. Wait for a DM to start a game.",
                "embed": None
            }

        # Ensure player is added to the game
        game_player = self.db.query(GamePlayer).filter_by(
            game_id=game.id,
            player_id=player.id
        ).first()

        if not game_player:
            # Auto-add player to game when they take their first action
            game_player = GamePlayer(game_id=game.id, player_id=player.id)
            self.db.add(game_player)
            self.db.flush()  # Get the ID without committing yet

        # Get action text
        action_text = args.get("description", "").strip()
        if not action_text:
            return {
                "message": "❌ Action description required. Usage: `/action attack the goblin`",
                "embed": None
            }

        # Get game state (simplified for now)
        game_state = {
            "game_id": game.id,
            "current_location": game.current_location,
            "status": game.status.value
        }

        # Validate action
        is_valid, error_msg = validation_system.validate_player_action(player, action_text, game_state)
        if not is_valid:
            return {
                "message": f"❌ {error_msg}",
                "embed": None
            }

        # Queue action
        action = Action(
            game_id=game.id,
            player_id=player.id,
            action_text=action_text,
            processed=False
        )
        self.db.add(action)
        self.db.commit()

        return {
            "message": f"✅ Action queued: **{action_text}**\nWaiting for other players or round resolution...",
            "embed": None
        }

    async def handle_stats(self, user_id: str) -> Dict[str, Any]:
        """Handle stats display command"""
        player = self.db.query(Player).filter_by(platform_user_id=user_id).first()
        if not player:
            return {
                "message": "❌ You don't have a character yet. Use `/create` to create one.",
                "embed": None
            }

        embed = self._create_character_sheet_embed(player)
        return {
            "message": None,
            "embed": embed
        }

    async def handle_inventory(self, user_id: str) -> Dict[str, Any]:
        """Handle inventory display command"""
        player = self.db.query(Player).filter_by(platform_user_id=user_id).first()
        if not player:
            return {
                "message": "❌ You don't have a character yet. Use `/create` to create one.",
                "embed": None
            }

        inventory = player.inventory if isinstance(player.inventory, dict) else {}
        items = inventory.get("items", [])

        if not items:
            return {
                "message": f"**{player.name}'s Inventory:**\n*Empty*",
                "embed": None
            }

        # Calculate weight
        str_value = player.stats.get("STR", 10)
        max_weight = settings.BASE_CARRYING_CAPACITY * str_value
        current_weight = sum(item.get("weight", 0) for item in items)

        items_text = "\n".join([f"• {item.get('name', 'Unknown')} ({item.get('weight', 0)} lbs)" for item in items])
        message = f"**{player.name}'s Inventory:**\n{items_text}\n\n**Weight:** {current_weight:.1f}/{max_weight:.1f} lbs"

        return {
            "message": message,
            "embed": None
        }

    async def handle_roll(self, user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dice roll command"""
        dice_string = args.get("dice", "1d20")
        
        try:
            result, explanation = roll_dice(dice_string)
            return {
                "message": f"🎲 Rolling {dice_string}:\n{explanation}",
                "embed": None
            }
        except ValueError as e:
            return {
                "message": f"❌ {str(e)}",
                "embed": None
            }

    async def handle_help(self, user_id: str, topic: Optional[str] = None) -> Dict[str, Any]:
        """Handle help command"""
        if not topic:
            # General help
            embed = {
                "title": "📚 Player Commands Help",
                "description": "Available commands for players",
                "color": 0x3498db,
                "fields": [
                    {
                        "name": "Character Commands",
                        "value": (
                            "`!create` - Create your character\n"
                            "`!stats` - View your character stats\n"
                            "`!inventory` - View your inventory"
                        ),
                        "inline": False
                    },
                    {
                        "name": "Gameplay Commands",
                        "value": (
                            "`!action <description>` - Perform an action in the game\n"
                            "`!roll <dice>` - Roll dice (e.g., !roll 2d6+3)\n"
                            "`!help <command>` - Get detailed help for a command"
                        ),
                        "inline": False
                    },
                    {
                        "name": "Examples",
                        "value": (
                            "`!create name:Thorne class:Paladin str:15 dex:12 con:14 int:10 wis:13 cha:10`\n"
                            "`!action attack the goblin with my sword`\n"
                            "`!roll 1d20+3`\n"
                            "`!help create` - Detailed character creation help"
                        ),
                        "inline": False
                    }
                ],
                "footer": "Type !help <command> for more details on a specific command"
            }
            return {
                "message": None,
                "embed": embed
            }
        else:
            # Specific command help
            topic_lower = topic.lower().strip()
            help_text = self._get_command_help(topic_lower)
            if help_text:
                return {
                    "message": help_text,
                    "embed": None
                }
            else:
                return {
                    "message": f"❌ Unknown command: `{topic}`. Type `!help` to see all available commands.",
                    "embed": None
                }

    def _get_command_help(self, command: str) -> Optional[str]:
        """Get detailed help for a specific command"""
        help_texts = {
            "create": """**Character Creation Help**

Create your D&D character with the following command:
`!create name:<name> class:<class> str:<n> dex:<n> con:<n> int:<n> wis:<n> cha:<n> [backstory:<text>]`

**Required:**
- `name` - Your character's name
- `class` - Character class (Paladin, Wizard, Rogue, etc.)
- `str`, `dex`, `con`, `int`, `wis`, `cha` - Ability scores (8-15)

**Optional:**
- `backstory` - Your character's backstory (use quotes for multi-word)

**Stat Points:**
- You have 27 points to allocate using D&D 5e point buy system
- Stat costs: 8=0, 9=1, 10=2, 11=3, 12=4, 13=5, 14=7, 15=9 points
- Minimum: 8, Maximum: 15 (before racial bonuses)

**Example:**
`!create name:Thorne class:Paladin str:15 dex:12 con:14 int:10 wis:13 cha:10 backstory:"Former knight seeking redemption"`""",

            "action": """**Action Command Help**

Perform actions in the game world:
`!action <description>`

**Description:**
Describe what your character wants to do. Be specific!

**Examples:**
- `!action attack the goblin with my sword`
- `!action move to the door and listen`
- `!action cast magic missile at the nearest enemy`
- `!action search the chest for treasure`
- `!action talk to the merchant about rumors`

**Tips:**
- Actions are queued and processed at the end of each round
- Be descriptive - the DM (AI) will interpret your action
- You can combine multiple actions: "move north and investigate the door"

**After queuing an action, wait for the round to process or use `!round` (if DM).**""",

            "stats": """**Stats Command Help**

View your character's statistics:
`!stats`

Shows:
- Your character's class and level
- Current and maximum HP
- All ability scores with modifiers
- Your backstory (if set)

**Example Output:**
Shows an embed with your character sheet including all stats and modifiers.""",

            "inventory": """**Inventory Command Help**

View your character's inventory:
`!inventory`

Shows:
- All items you're carrying
- Item weights
- Current weight vs. carrying capacity (based on STR)

**Carrying Capacity:**
- Maximum weight = 15 × STR score (in pounds)
- Warning at 90% capacity
- Cannot exceed maximum weight""",

            "roll": """**Dice Rolling Help**

Roll dice using D&D notation:
`!roll <dice notation>`

**Dice Notation:**
- `NdS` - Roll N dice with S sides
- `+M` or `-M` - Add or subtract a modifier

**Examples:**
- `!roll 1d20` - Roll a d20
- `!roll 2d6+3` - Roll 2d6 and add 3
- `!roll 1d4-1` - Roll 1d4 and subtract 1
- `!roll 4d6` - Roll 4 six-sided dice

**Common Rolls:**
- `!roll 1d20` - Ability check/attack roll
- `!roll 1d20+3` - Skill check with +3 modifier
- `!roll 2d6+3` - Greatsword damage with +3 STR
- `!roll 1d8+1` - Longsword damage with +1 STR

**Limits:**
- Maximum 100 dice per roll
- Die size between 2 and 100""",

            "help": """**Help Command Help**

Get information about available commands:
`!help` - Show all available commands
`!help <command>` - Get detailed help for a specific command

**Examples:**
- `!help` - See all commands
- `!help create` - Character creation details
- `!help action` - How to perform actions
- `!help roll` - Dice rolling guide"""
        }
        return help_texts.get(command)

    def _create_character_sheet_embed(self, player: Player) -> Dict[str, Any]:
        """Create Discord embed for character sheet"""
        stats = player.stats
        stat_modifiers = {stat: validation_system.stat_validator.get_stat_modifier(value) 
                         for stat, value in stats.items()}

        # Format stats with modifiers
        stats_text = "\n".join([
            f"**{stat}:** {value} ({stat_modifiers[stat]:+d})"
            for stat, value in stats.items()
        ])

        fields = [
            {"name": "Class", "value": player.class_name, "inline": True},
            {"name": "HP", "value": f"{player.hp}/{player.max_hp}", "inline": True},
            {"name": "Stats", "value": stats_text, "inline": False}
        ]

        if player.backstory:
            fields.append({"name": "Backstory", "value": player.backstory[:500], "inline": False})

        return {
            "title": f"Character Sheet: {player.name}",
            "description": f"Level 1 {player.class_name}",
            "color": 0x3498db,
            "fields": fields,
            "footer": f"Player ID: {player.id}"
        }


# Helper function to get handler
def get_player_handler(db_session: Session) -> PlayerCommandHandler:
    """Get a player command handler instance"""
    return PlayerCommandHandler(db_session)

