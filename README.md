# D&D Discord Bot Game

A Discord bot that runs D&D-style games using AI-generated story progression. Players create characters, send action commands, and the bot uses Ollama (local LLM) to generate narrative responses based on player actions.

## Features

- **Character Creation**: Players create characters with stats, classes, and backstories
- **Stat Validation**: Validates stat point allocation using D&D 5e point buy system
- **Action-Based Gameplay**: Players send actions, which are queued and processed in rounds
- **AI Story Generation**: Uses Ollama to generate narrative responses based on game state and player actions
- **Admin/DM Controls**: Admins can start, pause, resume, and manage campaigns
- **Game State Management**: Persistent game state with SQLite database
- **Validation System**: Comprehensive validation for stats, actions, inventory, and more

## Requirements

- Python 3.10+
- Ollama installed and running (see [Ollama Installation](https://ollama.ai))
- Discord Bot Token (see setup below)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd whatsapp_game
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up Ollama:
```bash
# Install Ollama (see https://ollama.ai)
ollama pull llama2  # or another model of your choice
```

5. Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your Discord bot token and settings
```

## Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create a New Application
3. Go to the "Bot" section
4. Create a bot and copy the token
5. Enable the following intents:
   - Message Content Intent
   - Server Members Intent (for role checking)
6. Invite the bot to your server with these permissions:
   - Send Messages
   - Read Message History
   - Use Slash Commands
   - Embed Links

7. (Optional) Create a role named "DM" for users who should have admin access

## Configuration

Edit `.env` file:

```env
DISCORD_TOKEN=your_bot_token_here
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama2
ADMIN_ROLE_NAME=DM
```

## Usage

### Testing via CLI (Before Discord Setup)

You can test all commands via CLI before setting up the Discord bot:

```bash
python test_cli.py
```

This will start an interactive CLI where you can:
- Test character creation
- Test command parsing
- Test stat validation
- Test dice rolling
- Test game flow
- Test AI integration (if Ollama is running)

**Quick test mode** (runs all tests automatically):
```bash
python test_cli.py --quick
```

**Example CLI commands:**
```
> !create name:TestWizard class:Wizard str:8 dex:14 con:13 int:15 wis:12 cha:10
> !start Test Campaign
> !action cast magic missile at the goblin
> !stats
> !round
> !roll 2d6+3
```

### Starting the Bot

```bash
python main.py
```

### Player Commands

- `/create name:Thorne class:Paladin str:15 dex:12 con:14 int:10 wis:13 cha:13` - Create a character
- `/action attack the goblin with my sword` - Perform an action
- `/stats` - View your character stats
- `/inventory` - View your inventory
- `/roll 2d6+3` - Roll dice (supports D&D dice notation)

### Admin/DM Commands

- `/dm start Campaign Name` - Start a new game in this channel
- `/dm pause` - Pause the active game
- `/dm resume` - Resume a paused game
- `/dm end` - End the game
- `/dm add encounter 3 goblins appear` - Add an encounter
- `/dm set location Deep Forest` - Set the current location
- `/dm validate @player` - Validate a player's stats

## Character Creation

When creating a character, you must allocate stat points using the D&D 5e point buy system:
- **Total points available**: 27
- **Stat range**: 8-15 (before racial bonuses)
- **Point costs**:
  - 8 = 0 points
  - 9 = 1 point
  - 10 = 2 points
  - 11 = 3 points
  - 12 = 4 points
  - 13 = 5 points
  - 14 = 7 points
  - 15 = 9 points

Example:
```
/create name:Thorne class:Paladin backstory:"Former knight seeking redemption" str:15 dex:12 con:14 int:10 wis:13 cha:13
```

## Game Flow

1. **DM starts game**: `/dm start Campaign Name`
2. **Players create characters**: `/create ...`
3. **Players send actions**: `/action ...`
4. **Bot processes round**: After all players act (or timeout), the bot uses AI to generate narrative
5. **Game continues**: Players can send more actions for the next round

## Architecture

The bot uses a modular architecture:

- **Platform Layer**: Abstracted Discord/WhatsApp support (Discord implemented)
- **Command Parser**: Parses player/admin commands
- **Game Engine**: Manages rounds, turns, and action processing
- **Validation System**: Validates stats, actions, inventory, etc.
- **AI Integration**: Ollama client for story generation
- **Database**: SQLite for persistent game state

## Project Structure

```
whatsapp_game/
├── bot/
│   ├── platforms/      # Discord/WhatsApp implementations
│   ├── commands/       # Command handlers
│   ├── game/          # Game engine and models
│   ├── ai/            # AI integration
│   └── utils/         # Utilities (dice rolling, etc.)
├── config/            # Configuration settings
├── data/              # Database files
├── main.py            # Entry point
└── requirements.txt   # Dependencies
```

## Troubleshooting

### Bot not responding
- Check that `DISCORD_TOKEN` is set correctly in `.env`
- Verify the bot has the required permissions in your server
- Check bot logs for errors

### Ollama connection failed
- Ensure Ollama is running: `ollama serve`
- Check `OLLAMA_URL` in `.env` matches your Ollama instance
- Verify the model exists: `ollama list`

### Database errors
- Ensure the `data/` directory exists
- Check file permissions
- Delete `data/game.db` to reset (will lose all game data)

## Future Enhancements

- WhatsApp bot support
- Visual state rendering
- Combat mechanics with HP tracking
- Item database with D&D standard items
- Skill checks and ability saves
- Level progression
- Discord slash commands

## License

[Your License Here]

## Contributing

[Contributing Guidelines Here]

