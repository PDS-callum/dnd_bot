"""CLI testing script for D&D bot commands"""

import asyncio
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

from bot.commands.parser import command_parser
from bot.commands.player import get_player_handler
from bot.commands.admin import get_admin_handler
from bot.game.models import Base, GameStatus
from bot.game.engine import get_game_engine
from bot.game.state import get_state_manager
from bot.game.validation import validation_system
from bot.ai.ollama_client import ollama_client
from bot.utils.dice import roll_dice
from config.settings import settings
import os

# Ensure data directory exists for SQLite database
if "sqlite" in settings.DATABASE_URL:
    # Extract database path from URL (sqlite:///data/game.db -> data/game.db)
    db_path = settings.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    if "/" in db_path or "\\" in db_path:
        # Extract directory path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    else:
        # Default to data directory
        os.makedirs("data", exist_ok=True)

# Database setup
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in settings.DATABASE_URL else None,
    echo=False
)
Base.metadata.create_all(engine)
SessionLocal = scoped_session(sessionmaker(bind=engine))


class CLITester:
    """CLI testing interface"""

    def __init__(self):
        self.db_session = SessionLocal()
        self.player_handler = get_player_handler(self.db_session)
        self.admin_handler = get_admin_handler(self.db_session)
        self.state_manager = get_state_manager(self.db_session)
        self.test_user_id = "test_user_123"
        self.test_channel_id = "test_channel_456"
        self.test_guild_id = "test_guild_789"

    async def ai_story_callback(self, game_state, player_actions):
        """AI callback for testing"""
        try:
            print(f"  [AI] Game: {game_state.get('campaign_name')} at {game_state.get('current_location')}")
            print(f"  [AI] Processing {len(player_actions)} action(s)...")
            narrative = await ollama_client.generate_story(game_state, player_actions)
            if narrative and len(narrative) > 10:
                return narrative
            else:
                print(f"  [AI] Warning: Received empty or very short narrative")
                return None
        except Exception as e:
            print(f"  [AI] Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def print_response(self, response):
        """Print formatted response"""
        if not response:
            print("(No response)")
            return

        message = response.get("message")
        embed = response.get("embed")

        if message:
            print(f"📝 Message: {message}")

        if embed:
            print(f"\n📋 Embed:")
            print(f"  Title: {embed.get('title', 'N/A')}")
            if embed.get('description'):
                print(f"  Description: {embed.get('description')}")
            if embed.get('fields'):
                print(f"  Fields:")
                for field in embed['fields']:
                    print(f"    - {field.get('name')}: {field.get('value')}")

    async def test_command_parsing(self, command_text):
        """Test command parsing"""
        print(f"\n🔍 Parsing command: {command_text}")
        parsed = command_parser.parse_command(command_text)
        if parsed:
            print(f"  Command: {parsed['command']}")
            print(f"  Args: {parsed['args']}")
            print(f"  Is Admin: {parsed['is_admin']}")
            return parsed
        else:
            print("  ❌ Not a valid command")
            return None

    async def test_dice_roll(self, dice_string):
        """Test dice rolling"""
        print(f"\n🎲 Rolling dice: {dice_string}")
        try:
            result, explanation = roll_dice(dice_string)
            print(f"  Result: {result}")
            print(f"  {explanation}")
        except ValueError as e:
            print(f"  ❌ Error: {e}")

    async def test_stat_validation(self, stats):
        """Test stat validation"""
        print(f"\n✅ Testing stat validation:")
        print(f"  Stats: {stats}")
        is_valid, error_msg = validation_system.validate_character_creation(stats)
        if is_valid:
            total_points = sum(settings.STAT_POINT_COSTS.get(v, 0) for v in stats.values())
            print(f"  ✓ Valid! Total points: {total_points}/{settings.STAT_POINT_BUY_MAX}")
        else:
            print(f"  ❌ Invalid: {error_msg}")

    async def test_create_character(self, args):
        """Test character creation"""
        print(f"\n👤 Creating character...")
        parsed_args = command_parser._parse_key_value_args(args) if isinstance(args, str) else args
        response = await self.player_handler.handle_create(self.test_user_id, parsed_args)
        self.print_response(response)
        return response

    async def test_start_game(self, campaign_name="Test Campaign", force_new=False):
        """Test starting a game"""
        if force_new:
            # End existing game first
            print(f"\n🛑 Ending existing game...")
            await self.admin_handler.handle_dm_end(self.test_user_id, self.test_channel_id)
        
        print(f"\n🎮 Starting game: {campaign_name}")
        args = {"description": campaign_name}
        response = await self.admin_handler.handle_dm_start(
            self.test_user_id,
            self.test_channel_id,
            self.test_guild_id,
            args
        )
        self.print_response(response)
        return response

    async def test_action(self, action_text):
        """Test player action"""
        print(f"\n⚔️ Player action: {action_text}")
        args = {"description": action_text}
        response = await self.player_handler.handle_action(
            self.test_user_id,
            self.test_channel_id,
            args
        )
        self.print_response(response)
        return response

    async def test_stats(self):
        """Test viewing stats"""
        print(f"\n📊 Viewing stats...")
        response = await self.player_handler.handle_stats(self.test_user_id)
        self.print_response(response)

    async def test_process_round(self):
        """Test processing a round"""
        print(f"\n🔄 Processing round...")
        game = self.state_manager.get_game_by_channel(self.test_channel_id)
        if not game:
            print("  ❌ No active game found. Start a game first.")
            return

        # Check game state first
        game_state = self.state_manager.get_game_state(game.id)
        pending_actions = game_state.get("pending_actions", [])
        
        if pending_actions:
            print(f"  📋 Found {len(pending_actions)} pending action(s):")
            for action in pending_actions:
                player = next((p for p in game_state["players"] if p["id"] == action["player_id"]), None)
                player_name = player["name"] if player else f"Player {action['player_id']}"
                print(f"    - {player_name}: {action['action_text']}")
        else:
            print("  ⚠️ No pending actions found. Queue an action first with !action")

        game_engine = get_game_engine(self.db_session, self.ai_story_callback)
        
        print(f"\n  🤖 Generating narrative with Ollama...")
        try:
            narrative = await game_engine.process_round(game.id, force=True)
            
            if narrative:
                print(f"\n  ✨ AI Narrative:")
                print(f"  {narrative}")
            else:
                print("\n  ⚠️ No narrative generated - check if Ollama is running and model is available")
                if pending_actions:
                    print(f"  💡 Ollama might not be responding. Try: !ai-test")
        except Exception as e:
            print(f"\n  ❌ Error processing round: {e}")
            import traceback
            traceback.print_exc()

    async def test_ollama_connection(self):
        """Test Ollama connection"""
        print(f"\n🤖 Testing Ollama connection...")
        is_connected = await ollama_client.test_connection()
        if is_connected:
            print(f"  ✓ Connected to {settings.OLLAMA_URL}")
            print(f"  Model: {settings.OLLAMA_MODEL}")
        else:
            print(f"  ❌ Cannot connect to {settings.OLLAMA_URL}")
            print(f"  Make sure Ollama is running: ollama serve")

    async def run_interactive(self):
        """Run interactive CLI"""
        print("=" * 60)
        print("D&D Bot CLI Tester")
        print("=" * 60)
        print("\nAvailable commands:")
        print("  1. create <args>  - Create character")
        print("      Example: !create name:Thorne class:Paladin str:15 dex:12 con:14 int:10 wis:13 cha:13")
        print("  2. start [name]   - Start game")
        print("      Example: !start Test Campaign")
        print("  3. action <text>  - Player action")
        print("  4. stats          - View character stats")
        print("  5. round          - Process round")
        print("  6. roll <dice>    - Roll dice")
        print("      Example: roll 2d6+3")
        print("  7. validate       - Test stat validation")
        print("  8. ai-test        - Test Ollama connection")
        print("  9. help [topic]   - Show help (general or for specific command)")
        print("  10. end           - End current game")
        print("  11. reset         - End and start new game")
        print("  12. exit          - Exit")
        print("\nType commands as you would in Discord:")
        print("  Example: !create name:Test class:Wizard str:8 dex:14 con:13 int:15 wis:12 cha:10")
        print("  Example: !action attack the goblin")
        print("=" * 60)

        while True:
            try:
                user_input = input("\n> ").strip()
                if not user_input:
                    continue

                if user_input.lower() == "exit" or user_input.lower() == "quit":
                    print("Goodbye!")
                    break

                if user_input.lower() == "help":
                    print("\nCommands:")
                    print("  !create name:<name> class:<class> str:<n> dex:<n> con:<n> int:<n> wis:<n> cha:<n>")
                    print("  !start [campaign name]")
                    print("  !action <action description>")
                    print("  !stats")
                    print("  !round")
                    print("  !roll <dice notation>")
                    print("  !validate")
                    print("  !ai-test")
                    print("\nExample:")
                    print("  !create name:TestWizard class:Wizard str:8 dex:14 con:13 int:15 wis:12 cha:10")
                    print("  !start My Campaign")
                    print("  !action cast fireball at the goblins")
                    continue

                # Parse command
                parsed = await self.test_command_parsing(user_input)
                if not parsed:
                    continue

                command = parsed["command"]
                args = parsed["args"]

                # Handle commands
                if command == "create":
                    await self.test_create_character(parsed["raw_args"])

                elif command == "start" or command == "dm start":
                    if args and isinstance(args, dict) and "description" in args:
                        campaign_name = args["description"]
                    elif parsed["raw_args"]:
                        campaign_name = parsed["raw_args"]
                    else:
                        campaign_name = "Test Campaign"
                    await self.test_start_game(campaign_name)

                elif command == "action":
                    action_text = args.get("description", "") if args else parsed["raw_args"]
                    await self.test_action(action_text)

                elif command == "stats":
                    await self.test_stats()

                elif command == "round":
                    await self.test_process_round()

                elif command == "end":
                    print(f"\n🛑 Ending game...")
                    response = await self.admin_handler.handle_dm_end(self.test_user_id, self.test_channel_id)
                    self.print_response(response)

                elif command == "reset":
                    print(f"\n🔄 Resetting game...")
                    await self.admin_handler.handle_dm_end(self.test_user_id, self.test_channel_id)
                    await asyncio.sleep(0.5)  # Brief pause
                    await self.test_start_game("Reset Campaign", force_new=False)

                elif command == "roll":
                    dice_string = args.get("dice", "1d20")
                    await self.test_dice_roll(dice_string)

                elif command == "help":
                    topic = args.get("description", "").strip() if args.get("description") else None
                    response = await self.player_handler.handle_help(self.test_user_id, topic)
                    self.print_response(response)

                elif command == "validate":
                    # Use example stats
                    test_stats = {"STR": 15, "DEX": 12, "CON": 14, "INT": 10, "WIS": 13, "CHA": 13}
                    await self.test_stat_validation(test_stats)

                elif command == "ai-test":
                    await self.test_ollama_connection()

                else:
                    print(f"❌ Unknown command: {command}")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()

    async def run_quick_tests(self):
        """Run a quick test suite"""
        print("=" * 60)
        print("Running Quick Tests")
        print("=" * 60)

        # Test 1: Command parsing
        print("\n[Test 1] Command Parsing")
        await self.test_command_parsing("!create name:Test class:Wizard")
        await self.test_command_parsing("!action attack goblin")
        await self.test_command_parsing("!stats")

        # Test 2: Dice rolling
        print("\n[Test 2] Dice Rolling")
        await self.test_dice_roll("1d20")
        await self.test_dice_roll("2d6+3")
        await self.test_dice_roll("d4-1")

        # Test 3: Stat validation
        print("\n[Test 3] Stat Validation")
        valid_stats = {"STR": 15, "DEX": 12, "CON": 14, "INT": 10, "WIS": 13, "CHA": 13}
        await self.test_stat_validation(valid_stats)
        
        invalid_stats = {"STR": 20, "DEX": 18, "CON": 18, "INT": 18, "WIS": 18, "CHA": 18}
        await self.test_stat_validation(invalid_stats)

        # Test 4: Character creation
        print("\n[Test 4] Character Creation")
        await self.test_create_character("name:TestWizard class:Wizard str:8 dex:14 con:13 int:15 wis:12 cha:10")

        # Test 5: Start game
        print("\n[Test 5] Start Game")
        await self.test_start_game("Quick Test Campaign")

        # Test 6: View stats
        print("\n[Test 6] View Stats")
        await self.test_stats()

        # Test 7: Player action
        print("\n[Test 7] Player Action")
        await self.test_action("cast magic missile at the goblin")

        # Test 8: Process round
        print("\n[Test 8] Process Round")
        await self.test_process_round()

        # Test 9: Ollama connection
        print("\n[Test 9] Ollama Connection")
        await self.test_ollama_connection()

        print("\n" + "=" * 60)
        print("Quick Tests Complete!")
        print("=" * 60)


async def main():
    """Main entry point"""
    tester = CLITester()

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        await tester.run_quick_tests()
    else:
        await tester.run_interactive()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")

