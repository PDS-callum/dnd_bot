"""Admin/DM commands handler"""

import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from bot.game.models import Game, GameSession, GameStatus, GameLog, LogType, Player, GamePlayer
from bot.game.validation import validation_system
from config.settings import settings

logger = logging.getLogger(__name__)


class AdminCommandHandler:
    """Handle admin/DM commands"""

    def __init__(self, db_session: Session):
        """Initialize with database session"""
        self.db = db_session

    async def handle_dm_start(self, user_id: str, channel_id: str, guild_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle DM start command - start a new game

        Args:
            user_id: Admin user ID
            channel_id: Channel ID
            guild_id: Guild/Server ID
            args: Parsed command arguments

        Returns:
            Response dictionary
        """
        # Check if game already exists in this channel
        existing_game = self.db.query(Game).filter_by(channel_id=channel_id).filter(
            Game.status.in_([GameStatus.WAITING, GameStatus.ACTIVE, GameStatus.PAUSED])
        ).first()

        if existing_game:
            return {
                "message": f"❌ A game is already running in this channel: **{existing_game.name or 'Unnamed'}**",
                "embed": None
            }

        # Get campaign name
        campaign_name = args.get("description", "").strip() or "Campaign"

        # Create game
        game = Game(
            guild_id=guild_id,
            channel_id=channel_id,
            name=f"Game in #{channel_id}",
            status=GameStatus.ACTIVE,
            campaign_name=campaign_name,
            created_by=user_id,
            current_location="Starting Location"
        )
        self.db.add(game)
        self.db.flush()  # Get game.id

        # Create game session
        session = GameSession(
            game_id=game.id,
            round_number=1,
            active_encounters=[]
        )
        self.db.add(session)

        # Create initial game log
        log = GameLog(
            game_id=game.id,
            message=f"Game started by DM. Campaign: {campaign_name}",
            log_type=LogType.SYSTEM
        )
        self.db.add(log)

        self.db.commit()

        # Generate opening narrative
        opening_narrative = await self._generate_opening_narrative(campaign_name, game)

        # Log the opening narrative
        narrative_log = GameLog(
            game_id=game.id,
            message=opening_narrative,
            log_type=LogType.NARRATIVE
        )
        self.db.add(narrative_log)
        self.db.commit()

        return {
            "message": (
                f"✅ Game started!\n"
                f"**Campaign:** {campaign_name}\n"
                f"**Location:** {game.current_location}\n\n"
                f"📖 **Opening Scene:**\n{opening_narrative}\n\n"
                f"Players can now use `/action` to participate."
            ),
            "embed": None
        }

    async def handle_dm_pause(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """Handle DM pause command"""
        game = self.db.query(Game).filter_by(channel_id=channel_id, status=GameStatus.ACTIVE).first()

        if not game:
            return {
                "message": "❌ No active game found in this channel.",
                "embed": None
            }

        game.status = GameStatus.PAUSED
        self.db.commit()

        return {
            "message": "⏸️ Game paused. Use `/dm resume` to continue.",
            "embed": None
        }

    async def handle_dm_resume(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """Handle DM resume command"""
        game = self.db.query(Game).filter_by(channel_id=channel_id, status=GameStatus.PAUSED).first()

        if not game:
            return {
                "message": "❌ No paused game found in this channel.",
                "embed": None
            }

        game.status = GameStatus.ACTIVE
        self.db.commit()

        return {
            "message": "▶️ Game resumed! Players can continue their actions.",
            "embed": None
        }

    async def handle_dm_end(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """Handle DM end command"""
        game = self.db.query(Game).filter_by(channel_id=channel_id).filter(
            Game.status.in_([GameStatus.ACTIVE, GameStatus.PAUSED])
        ).first()

        if not game:
            return {
                "message": "❌ No active game found in this channel.",
                "embed": None
            }

        game.status = GameStatus.ENDED

        # Create game log
        log = GameLog(
            game_id=game.id,
            message="Game ended by DM.",
            log_type=LogType.SYSTEM
        )
        self.db.add(log)
        self.db.commit()

        return {
            "message": "🏁 Game ended. Thank you for playing!",
            "embed": None
        }

    async def handle_dm_add_encounter(self, user_id: str, channel_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle DM add encounter command"""
        game = self.db.query(Game).filter_by(channel_id=channel_id, status=GameStatus.ACTIVE).first()

        if not game:
            return {
                "message": "❌ No active game found in this channel.",
                "embed": None
            }

        encounter_description = args.get("description", "").strip()
        if not encounter_description:
            return {
                "message": "❌ Encounter description required. Usage: `/dm add encounter 3 goblins appear`",
                "embed": None
            }

        # Get or create game session
        session = self.db.query(GameSession).filter_by(game_id=game.id).first()
        if not session:
            session = GameSession(game_id=game.id, round_number=1, active_encounters=[])
            self.db.add(session)

        # Add encounter to active encounters
        encounters = session.active_encounters if isinstance(session.active_encounters, list) else []
        encounters.append({
            "description": encounter_description,
            "added_by": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        session.active_encounters = encounters

        # Create game log
        log = GameLog(
            game_id=game.id,
            message=f"**Encounter added:** {encounter_description}",
            log_type=LogType.COMBAT
        )
        self.db.add(log)
        self.db.commit()

        return {
            "message": f"✅ Encounter added: **{encounter_description}**",
            "embed": None
        }

    async def handle_dm_set_location(self, user_id: str, channel_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle DM set location command"""
        game = self.db.query(Game).filter_by(channel_id=channel_id, status=GameStatus.ACTIVE).first()

        if not game:
            return {
                "message": "❌ No active game found in this channel.",
                "embed": None
            }

        location = args.get("description", "").strip()
        if not location:
            return {
                "message": "❌ Location required. Usage: `/dm set location Deep Forest`",
                "embed": None
            }

        game.current_location = location
        self.db.commit()

        return {
            "message": f"📍 Location updated: **{location}**",
            "embed": None
        }

    async def handle_dm_validate(self, user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle DM validate command - check player stats"""
        player_mention = args.get("player", "").strip()

        if not player_mention:
            return {
                "message": "❌ Player mention required. Usage: `/dm validate @player`",
                "embed": None
            }

        # Extract user ID from mention (format: <@USER_ID>)
        import re
        match = re.search(r'<@!?(\d+)>', player_mention)
        if not match:
            # Try to find by name
            platform_user_id = player_mention
        else:
            platform_user_id = match.group(1)

        player = self.db.query(Player).filter_by(platform_user_id=platform_user_id).first()
        if not player:
            return {
                "message": f"❌ Player not found: {player_mention}",
                "embed": None
            }

        # Validate stats
        is_valid, error_msg = validation_system.validate_character_creation(player.stats)
        
        if is_valid:
            # Calculate points used
            total_points = sum(
                settings.STAT_POINT_COSTS.get(value, 0)
                for value in player.stats.values()
            )
            message = (
                f"✅ **{player.name}** stats are valid!\n"
                f"**Points used:** {total_points}/{settings.STAT_POINT_BUY_MAX}\n"
                f"**Stats:** {', '.join([f'{k}:{v}' for k, v in player.stats.items()])}"
            )
        else:
            message = f"❌ **{player.name}** stats are invalid: {error_msg}"

        return {
            "message": message,
            "embed": None
        }


    async def _generate_opening_narrative(self, campaign_name: str, game: Game) -> str:
        """
        Generate an opening narrative for the campaign
        
        Args:
            campaign_name: Name of the campaign
            game: Game object
            
        Returns:
            Opening narrative text
        """
        try:
            # Build a custom prompt for the opening scene
            location = game.current_location or "a mysterious location"
            
            # Try to generate with Ollama directly
            narrative = None
            
            try:
                prompt = f"""You are a Dungeon Master starting a D&D campaign. Generate an opening narrative that sets the scene for the adventure.

**Campaign Name:** {campaign_name}
**Starting Location:** {location}

**Instructions:**
- Write a compelling opening scene (2-3 sentences)
- Set the mood and atmosphere
- Describe the immediate surroundings
- Hint at adventure or mystery ahead
- Use D&D narrative style
- End with something that invites player interaction

**Opening Scene:**"""

                async with aiohttp.ClientSession() as http_session:
                    payload = {
                        "model": settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.8,
                            "top_p": 0.9,
                            "num_predict": 200
                        }
                    }
                    url = f"{settings.OLLAMA_URL}/api/generate"
                    logger.info(f"Calling Ollama at {url} with model {settings.OLLAMA_MODEL}")
                    
                    async with http_session.post(
                        url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            generated = data.get("response", "").strip()
                            logger.info(f"Ollama response length: {len(generated)} characters")
                            
                            # Remove markdown code blocks if present
                            if generated.startswith("```"):
                                lines = generated.split("\n")
                                if len(lines) > 2:
                                    generated = "\n".join(lines[1:-1])
                            
                            # Clean up common prefixes
                            if generated.startswith("**Opening Scene:**"):
                                generated = generated.replace("**Opening Scene:**", "").strip()
                            if generated.startswith("Opening Scene:"):
                                generated = generated.replace("Opening Scene:", "").strip()
                            
                            if generated and len(generated) > 15:
                                narrative = generated
                                logger.info("Successfully generated opening narrative")
                            else:
                                logger.warning(f"Generated narrative too short: {generated}")
                        else:
                            error_text = await response.text()
                            logger.error(f"Ollama API returned status {response.status}: {error_text}")
            except aiohttp.ClientError as e:
                logger.warning(f"Failed to connect to Ollama at {settings.OLLAMA_URL}: {e}")
            except asyncio.TimeoutError:
                logger.warning(f"Ollama request timed out after 60 seconds")
            except Exception as e:
                logger.warning(f"Failed to generate opening with Ollama: {e}", exc_info=True)
            
            # Fallback to default if Ollama fails
            if not narrative:
                narrative = (
                    f"The sun sets on the horizon as you arrive at {location}. "
                    f"Your adventure in **{campaign_name}** begins. The air is thick with possibility and mystery. "
                    f"What would you like to do?"
                )
            
            return narrative

        except Exception as e:
            logger.error(f"Error generating opening narrative: {e}")
            return (
                f"You find yourselves at {game.current_location or 'a mysterious location'}. "
                f"The adventure in **{campaign_name}** begins. What would you like to do?"
            )


# Helper function to get handler
def get_admin_handler(db_session: Session) -> AdminCommandHandler:
    """Get an admin command handler instance"""
    return AdminCommandHandler(db_session)

