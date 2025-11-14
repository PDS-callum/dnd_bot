"""Game state management"""

import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime

from bot.game.models import Game, GameSession, Player, GamePlayer, GameLog, LogType, Action, GameStatus

logger = logging.getLogger(__name__)


class GameStateManager:
    """Manage game state operations"""

    def __init__(self, db_session: Session):
        """Initialize with database session"""
        self.db = db_session

    def get_game_state(self, game_id: int) -> Dict[str, Any]:
        """
        Get current game state

        Args:
            game_id: Game ID

        Returns:
            Dictionary with game state information
        """
        game = self.db.query(Game).filter_by(id=game_id).first()
        if not game:
            return {}

        session = self.db.query(GameSession).filter_by(game_id=game_id).first()
        if not session:
            session = GameSession(game_id=game_id, round_number=1, active_encounters=[])
            self.db.add(session)
            self.db.commit()

        # Get all players in this game
        game_players = self.db.query(GamePlayer).filter_by(game_id=game_id).all()
        player_ids = [gp.player_id for gp in game_players]
        players = self.db.query(Player).filter(Player.id.in_(player_ids)).all() if player_ids else []

        # Get recent game logs (for AI context)
        recent_logs = self.db.query(GameLog).filter_by(game_id=game_id)\
            .order_by(GameLog.timestamp.desc()).limit(10).all()

        # Get pending actions
        pending_actions_db = self.db.query(Action).filter_by(
            game_id=game_id,
            processed=False
        ).order_by(Action.timestamp.asc()).all()

        # Serialize pending actions
        pending_actions = [
            {
                "id": a.id,
                "player_id": a.player_id,
                "action_text": a.action_text,
                "timestamp": a.timestamp.isoformat()
            }
            for a in pending_actions_db
        ]

        return {
            "game_id": game.id,
            "name": game.name,
            "status": game.status.value,
            "current_location": game.current_location,
            "campaign_name": game.campaign_name,
            "round_number": session.round_number,
            "current_turn": session.current_turn,
            "active_encounters": session.active_encounters if isinstance(session.active_encounters, list) else [],
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "class": p.class_name,
                    "hp": p.hp,
                    "max_hp": p.max_hp,
                    "stats": p.stats,
                    "platform_user_id": p.platform_user_id
                }
                for p in players
            ],
            "pending_actions": pending_actions,
            "recent_logs": [
                {
                    "message": log.message,
                    "type": log.log_type.value,
                    "timestamp": log.timestamp.isoformat()
                }
                for log in recent_logs
            ]
        }

    def get_game_by_channel(self, channel_id: str) -> Optional[Game]:
        """Get active game in a channel"""
        return self.db.query(Game).filter_by(
            channel_id=channel_id,
            status=GameStatus.ACTIVE
        ).first()

    def add_player_to_game(self, game_id: int, player_id: int) -> bool:
        """Add a player to a game"""
        # Check if already in game
        existing = self.db.query(GamePlayer).filter_by(
            game_id=game_id,
            player_id=player_id
        ).first()

        if existing:
            return False

        game_player = GamePlayer(game_id=game_id, player_id=player_id)
        self.db.add(game_player)
        self.db.commit()
        return True

    def log_game_event(self, game_id: int, message: str, log_type: LogType = LogType.SYSTEM) -> None:
        """Add an entry to the game log"""
        log = GameLog(
            game_id=game_id,
            message=message,
            log_type=log_type
        )
        self.db.add(log)
        self.db.commit()

    def update_game_location(self, game_id: int, location: str) -> None:
        """Update game location"""
        game = self.db.query(Game).filter_by(id=game_id).first()
        if game:
            game.current_location = location
            self.db.commit()

    def update_game_session(self, game_id: int, round_number: Optional[int] = None, 
                           current_turn: Optional[int] = None,
                           active_encounters: Optional[List[Dict]] = None) -> None:
        """Update game session state"""
        session = self.db.query(GameSession).filter_by(game_id=game_id).first()
        if not session:
            session = GameSession(game_id=game_id, round_number=1, active_encounters=[])
            self.db.add(session)

        if round_number is not None:
            session.round_number = round_number
        if current_turn is not None:
            session.current_turn = current_turn
        if active_encounters is not None:
            session.active_encounters = active_encounters

        session.updated_at = datetime.utcnow()
        self.db.commit()

    def get_all_active_games(self) -> List[Game]:
        """Get all active games"""
        return self.db.query(Game).filter(
            Game.status == GameStatus.ACTIVE
        ).all()

    def mark_actions_processed(self, game_id: int, action_ids: List[int]) -> None:
        """Mark actions as processed"""
        self.db.query(Action).filter(
            Action.game_id == game_id,
            Action.id.in_(action_ids)
        ).update({"processed": True}, synchronize_session=False)
        self.db.commit()


# Helper function
def get_state_manager(db_session: Session) -> GameStateManager:
    """Get a game state manager instance"""
    return GameStateManager(db_session)

