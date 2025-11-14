"""Ollama AI integration for story generation"""

import logging
import aiohttp
from typing import Dict, List, Any, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API"""

    def __init__(self, base_url: str = None, model: str = None):
        """
        Initialize Ollama client

        Args:
            base_url: Ollama API base URL
            model: Model name to use
        """
        self.base_url = base_url or settings.OLLAMA_URL
        self.model = model or settings.OLLAMA_MODEL
        self.generate_endpoint = f"{self.base_url}/api/generate"

    async def generate_story(
        self,
        game_state: Dict[str, Any],
        player_actions: List[Dict[str, str]]
    ) -> str:
        """
        Generate story narrative from game state and player actions

        Args:
            game_state: Current game state dictionary
            player_actions: List of player actions for this round

        Returns:
            Generated narrative text
        """
        prompt = self._build_prompt(game_state, player_actions)

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,  # Creative but coherent
                        "top_p": 0.9,
                        "max_tokens": 500
                    }
                }

                async with session.post(self.generate_endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        data = await response.json()
                        generated_text = data.get("response", "")
                        
                        # Clean up the response
                        generated_text = generated_text.strip()
                        
                        # Remove any markdown code blocks if present
                        if generated_text.startswith("```"):
                            lines = generated_text.split("\n")
                            generated_text = "\n".join(lines[1:-1])
                        
                        return generated_text
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama API error {response.status}: {error_text}")
                        return self._fallback_narrative(player_actions)

        except aiohttp.ClientError as e:
            logger.error(f"Error connecting to Ollama: {e}")
            return self._fallback_narrative(player_actions)
        except Exception as e:
            logger.error(f"Unexpected error generating story: {e}")
            return self._fallback_narrative(player_actions)

    def _build_prompt(self, game_state: Dict[str, Any], player_actions: List[Dict[str, str]]) -> str:
        """Build the prompt for the AI"""
        
        # Extract key information
        campaign_name = game_state.get("campaign_name", "Campaign")
        location = game_state.get("current_location", "Unknown Location")
        round_number = game_state.get("round_number", 1)
        players = game_state.get("players", [])
        active_encounters = game_state.get("active_encounters", [])
        recent_logs = game_state.get("recent_logs", [])[:5]  # Last 5 logs

        # Build character descriptions
        character_descriptions = []
        for player in players:
            stats = player.get("stats", {})
            stats_str = ", ".join([f"{k}:{v}" for k, v in stats.items()])
            character_descriptions.append(
                f"- {player['name']} ({player['class']}): HP {player['hp']}/{player['max_hp']}, Stats: {stats_str}"
            )

        # Build recent events
        recent_events = []
        for log in recent_logs:
            recent_events.append(f"- {log['message']}")

        # Build active encounters
        encounter_descriptions = []
        for enc in active_encounters:
            if isinstance(enc, dict):
                encounter_descriptions.append(enc.get("description", "Unknown encounter"))
            else:
                encounter_descriptions.append(str(enc))

        # Build action descriptions
        action_descriptions = []
        for action in player_actions:
            action_descriptions.append(f"- {action['player_name']}: {action['action_text']}")

        # Construct prompt
        prompt = f"""You are a Dungeon Master running a D&D campaign. Generate a narrative response based on the current game state and player actions.

**Campaign:** {campaign_name}
**Current Location:** {location}
**Round:** {round_number}

**Party Members:**
{chr(10).join(character_descriptions) if character_descriptions else "- No active players"}

**Active Encounters:**
{chr(10).join(encounter_descriptions) if encounter_descriptions else "- None"}

**Recent Events:**
{chr(10).join(recent_events) if recent_events else "- The adventure begins..."}

**Player Actions This Round:**
{chr(10).join(action_descriptions) if action_descriptions else "- No actions taken"}

**Instructions:**
- Write a narrative response that describes what happens based on the player actions
- Use D&D terminology and style
- Be creative but respect the game rules (don't make impossible things happen)
- Keep the response to 2-4 sentences
- Focus on the outcome of the actions and the world's response
- Maintain consistency with the campaign setting and recent events

**Narrative Response:**"""

        return prompt

    def _fallback_narrative(self, player_actions: List[Dict[str, str]]) -> str:
        """Generate a fallback narrative when AI fails"""
        if not player_actions:
            return "*The party waits, watching the world around them...*"

        action_summary = ", ".join([f"{a['player_name']} {a['action_text']}" for a in player_actions])
        return f"*The party acts: {action_summary}. The world responds...*"

    async def test_connection(self) -> bool:
        """Test connection to Ollama"""
        try:
            async with aiohttp.ClientSession() as session:
                # Try to list models to test connection
                async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            return False


# Global Ollama client instance
ollama_client = OllamaClient()

