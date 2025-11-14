"""Game engine for processing rounds and managing turns"""

import logging
import asyncio
from typing import Dict, List, Optional, Callable
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from bot.game.models import Game, Action, GameStatus, GameSession, LogType
from bot.game.state import GameStateManager
from config.settings import settings

logger = logging.getLogger(__name__)


class GameEngine:
    """Main game engine for processing rounds and turns"""

    def __init__(self, db_session: Session, ai_callback: Optional[Callable] = None):
        """
        Initialize game engine

        Args:
            db_session: Database session
            ai_callback: Optional callback function for AI story generation
                        Should be async and take (game_state, player_actions) -> str
        """
        self.db = db_session
        self.state_manager = GameStateManager(db_session)
        self.ai_callback = ai_callback
        self.active_rounds = {}  # Track active round processing

    async def process_round(self, game_id: int, force: bool = False) -> Optional[str]:
        """
        Process a round of actions for a game

        Args:
            game_id: Game ID
            force: Force processing even if not all players have acted

        Returns:
            AI-generated narrative response or None
        """
        # Prevent concurrent processing of the same game
        if game_id in self.active_rounds:
            logger.warning(f"Round already being processed for game {game_id}")
            return None

        self.active_rounds[game_id] = True

        try:
            # Get game state
            game_state = self.state_manager.get_game_state(game_id)
            
            if not game_state or game_state["status"] != "active":
                logger.warning(f"Game {game_id} is not active")
                return None

            # Get pending actions
            pending_actions = game_state["pending_actions"]

            if not pending_actions and not force:
                logger.info(f"No pending actions for game {game_id}")
                return None

            # Get players in game
            players = game_state["players"]
            player_ids = [p["id"] for p in players]

            # Check if we should process (time-based or action-based)
            should_process = self._should_process_round(game_state, pending_actions, force)

            if not should_process:
                return None

            # Prepare actions for AI
            player_actions = []
            action_ids = []

            for action_data in pending_actions:
                player_id = action_data["player_id"]
                player = next((p for p in players if p["id"] == player_id), None)
                
                if player:
                    player_actions.append({
                        "player_name": player["name"],
                        "action_text": action_data["action_text"]
                    })
                    action_ids.append(action_data["id"])
                else:
                    # Player might not be in game yet, but we still process the action
                    # Load player directly from database
                    from bot.game.models import Player as PlayerModel
                    player_obj = self.db.query(PlayerModel).filter_by(id=player_id).first()
                    if player_obj:
                        player_actions.append({
                            "player_name": player_obj.name,
                            "action_text": action_data["action_text"]
                        })
                        action_ids.append(action_data["id"])
                    else:
                        logger.warning(f"Player {player_id} not found for action {action_data['id']}")

            # If we have actions and AI callback, generate story
            narrative = None
            if player_actions and self.ai_callback:
                try:
                    logger.info(f"Generating narrative for {len(player_actions)} action(s)")
                    narrative = await self.ai_callback(game_state, player_actions)
                    if narrative:
                        logger.info(f"Generated narrative: {narrative[:100]}...")
                    else:
                        logger.warning("AI callback returned None or empty narrative")
                except Exception as e:
                    logger.error(f"Error generating story with AI: {e}", exc_info=True)
                    narrative = f"*The actions unfold: {', '.join([a['action_text'] for a in player_actions])}*"
            elif player_actions and not self.ai_callback:
                logger.warning("No AI callback available for story generation")
                narrative = f"*The actions unfold: {', '.join([a['action_text'] for a in player_actions])}*"

            # Mark actions as processed
            if action_ids:
                self.state_manager.mark_actions_processed(game_id, action_ids)

            # Update round number
            session = self.db.query(GameSession).filter_by(game_id=game_id).first()
            if session:
                session.round_number += 1
                session.current_turn = None  # Reset turn order
                session.updated_at = datetime.utcnow()
                self.db.commit()

            # Log the round
            if narrative:
                self.state_manager.log_game_event(
                    game_id,
                    f"**Round {game_state['round_number']}**\n{narrative}",
                    LogType.NARRATIVE
                )

            return narrative

        except Exception as e:
            logger.error(f"Error processing round for game {game_id}: {e}")
            return None
        finally:
            self.active_rounds.pop(game_id, None)

    def _should_process_round(self, game_state: Dict, pending_actions: List[Dict], force: bool) -> bool:
        """
        Determine if a round should be processed

        Args:
            game_state: Current game state
            pending_actions: List of pending actions
            force: Force processing flag

        Returns:
            True if round should be processed
        """
        if force:
            return True

        if not pending_actions:
            return False

        players = game_state["players"]
        num_players = len(players)
        num_actions = len(pending_actions)

        # Process if we have actions from at least MIN_PLAYERS_FOR_ROUND players
        if num_actions >= settings.MIN_PLAYERS_FOR_ROUND:
            # Check if all players have acted (or enough time has passed)
            unique_acting_players = len(set(a["player_id"] for a in pending_actions))
            
            # Process if all active players have acted
            if unique_acting_players >= num_players:
                return True

            # Process if timeout has passed (check oldest action)
            if pending_actions:
                oldest_action = min(pending_actions, key=lambda x: x["timestamp"])
                action_time = datetime.fromisoformat(oldest_action["timestamp"])
                time_since_oldest = datetime.utcnow() - action_time

                if time_since_oldest >= timedelta(seconds=settings.ROUND_TIMEOUT_SECONDS):
                    return True

        return False

    def queue_action(self, game_id: int, player_id: int, action_text: str) -> Action:
        """
        Queue a player action

        Args:
            game_id: Game ID
            player_id: Player ID
            action_text: Action description

        Returns:
            Created Action object
        """
        action = Action(
            game_id=game_id,
            player_id=player_id,
            action_text=action_text,
            processed=False
        )
        self.db.add(action)
        self.db.commit()
        return action

    async def process_all_active_games(self) -> None:
        """Process rounds for all active games"""
        active_games = self.state_manager.get_all_active_games()

        for game in active_games:
            try:
                await self.process_round(game.id)
            except Exception as e:
                logger.error(f"Error processing game {game.id}: {e}")

    async def start_round_processor(self, interval: int = 30) -> None:
        """
        Start a background task that processes rounds periodically

        Args:
            interval: Interval in seconds between processing checks
        """
        logger.info(f"Starting round processor with {interval}s interval")
        
        while True:
            try:
                await asyncio.sleep(interval)
                await self.process_all_active_games()
            except Exception as e:
                logger.error(f"Error in round processor: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying


# Helper function
def get_game_engine(db_session: Session, ai_callback: Optional[Callable] = None) -> GameEngine:
    """Get a game engine instance"""
    return GameEngine(db_session, ai_callback)

