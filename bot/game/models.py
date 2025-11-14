"""Database models for the D&D game bot"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Enum as SQLEnum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class GameStatus(enum.Enum):
    """Game status enumeration"""
    WAITING = "waiting"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class LogType(enum.Enum):
    """Game log message type"""
    NARRATIVE = "narrative"
    COMBAT = "combat"
    SYSTEM = "system"


class Player(Base):
    """Player character model"""
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_user_id = Column(String(255), nullable=False, index=True)  # Discord user ID
    name = Column(String(255), nullable=False)
    class_name = Column(String(100), nullable=False)  # 'class' is reserved in Python
    backstory = Column(Text, nullable=True)
    stats = Column(JSON, nullable=False)  # {"STR": 15, "DEX": 12, ...}
    hp = Column(Integer, nullable=False, default=20)
    max_hp = Column(Integer, nullable=False, default=20)
    inventory = Column(JSON, nullable=False, default=dict)  # List of items or dict
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    actions = relationship("Action", back_populates="player")
    games = relationship("GamePlayer", back_populates="player")

    def __repr__(self):
        return f"<Player(id={self.id}, name='{self.name}', class='{self.class_name}')>"


class Game(Base):
    """Game/campaign model"""
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(String(255), nullable=False, index=True)  # Discord server ID
    channel_id = Column(String(255), nullable=False, index=True)  # Discord channel ID
    name = Column(String(255), nullable=True)
    status = Column(SQLEnum(GameStatus), nullable=False, default=GameStatus.WAITING)
    current_location = Column(String(255), nullable=True)
    campaign_name = Column(String(255), nullable=True)
    created_by = Column(String(255), nullable=False)  # Admin platform user ID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    sessions = relationship("GameSession", back_populates="game", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="game", cascade="all, delete-orphan")
    logs = relationship("GameLog", back_populates="game", cascade="all, delete-orphan")
    players = relationship("GamePlayer", back_populates="game", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Game(id={self.id}, name='{self.name}', status={self.status.value})>"


class GamePlayer(Base):
    """Many-to-many relationship between games and players"""
    __tablename__ = "game_players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)

    # Relationships
    game = relationship("Game", back_populates="players")
    player = relationship("Player", back_populates="games")

    def __repr__(self):
        return f"<GamePlayer(game_id={self.game_id}, player_id={self.player_id})>"


class GameSession(Base):
    """Game session state model"""
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, unique=True)
    round_number = Column(Integer, nullable=False, default=1)
    current_turn = Column(Integer, nullable=True)  # Player ID whose turn it is
    active_encounters = Column(JSON, nullable=False, default=list)  # List of encounters/NPCs
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    game = relationship("Game", back_populates="sessions")

    def __repr__(self):
        return f"<GameSession(game_id={self.game_id}, round={self.round_number})>"


class Action(Base):
    """Player action model"""
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    action_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed = Column(Boolean, nullable=False, default=False)
    result = Column(JSON, nullable=True)  # Store processed action results

    # Relationships
    game = relationship("Game", back_populates="actions")
    player = relationship("Player", back_populates="actions")

    def __repr__(self):
        return f"<Action(id={self.id}, player_id={self.player_id}, processed={self.processed})>"


class GameLog(Base):
    """Game log entry model"""
    __tablename__ = "game_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    log_type = Column(SQLEnum(LogType), nullable=False, default=LogType.NARRATIVE)

    # Relationships
    game = relationship("Game", back_populates="logs")

    def __repr__(self):
        return f"<GameLog(id={self.id}, type={self.log_type.value})>"

