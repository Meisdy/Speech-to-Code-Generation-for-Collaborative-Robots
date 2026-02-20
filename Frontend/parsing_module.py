# parser_module.py
"""
LLM-based parser for converting natural language to robot commands.

This module uses LM Studio API to transform speech-to-text transcriptions
into structured JSON commands according to defined rulesets and schemas.
"""

import json
import time
import config
import requests
from typing import Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger("cobot")


class CodeParser:
    """
    Converts natural language commands to structured robot control JSON.

    Uses an LLM to parse user commands into validated JSON structures
    conforming to robot-specific command schemas and primitive rulesets.
    """

    def __init__(self):
        """Initialize parser with LLM config and load command definitions."""
        # LLM API configuration
        self.api_base: str = config.LLM_API_BASE
        self.model_name: str = config.LLM_MODEL_NAME
        self.temperature: float = config.LLM_TEMPERATURE
        self.max_tokens: int = config.LLM_MAX_TOKENS
        self.timeout: int = config.LLM_TIMEOUT
        self.mode: str = config.FRAMEWORK_MODE

        # Load command definitions
        self.ruleset: Dict = self._load_json("ruleset.json")
        self.command_schema: Dict = self._load_json("command_schema.json")
        self.system_prompt: str = self._build_system_prompt()

        # Logging configuration
        self.log_parsing: bool = config.LOGGING_SAVE_PARSE
        self.log_path: str = config.LOGGING_DIR

    def _load_json(self, filename: str) -> Any | None:
        """
        Load JSON file from module directory.

        Args:
            filename: Name of JSON file to load

        Returns:
            Parsed JSON as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        try:
            file_path = Path(__file__).parent / filename
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Parser: Failed to load {filename} - file not found")

    def _build_system_prompt(self) -> str:
        """Build LLM system prompt with ruleset and schema definitions."""
        return f"""You are a robot command parser. Convert natural language to structured JSON commands.

AVAILABLE PRIMITIVES:
{json.dumps(self.ruleset, indent=2)}

REQUIRED OUTPUT FORMAT:
{json.dumps(self.command_schema, indent=2)}

RULES:
- Return ONLY valid JSON (no markdown, no explanations)
- Use only actions from AVAILABLE PRIMITIVES
- Commands array can contain multiple sequential commands
- Use defaults from ruleset when parameters not specified
- Always include "mode", "robot", and "commands" fields
- Robot field allows for 'franka' XOR 'ur' XOR 'mock'
- use numbers whenever possible, not words (e.g. "move 10 cm", not "move ten centimeters)
- for names of positions, use snakecase notation
- If you want to add feedback, add it to the "message" field
"""

    def parse(self, text: str, robot_type: str) -> Dict[str, Any]:
        """
        Parse natural language to structured robot command JSON.

        Args:
            text: Natural language command from ASR
            robot_type: Target robot identifier (e.g., "Franka Emika")

        Returns:
            {
                "command": {...},           # Parsed command structure
                "status": "success|error",  # Parse result
                "error": "..."              # Error message (if status == "error")
            }
        """
        # Validate input
        if not text or not text.strip() or len(text.strip()) < 10:
            return self._error_response(robot_type, "Command empty or too short")

        user_prompt = f"Robot type: {robot_type}\nCommand: {text}\n\nGenerate JSON output:"

        try:
            result = self._call_llm(user_prompt)

            # Check for token limit truncation
            if result['choices'][0].get('finish_reason') == 'length':
                return self._error_response(
                    robot_type,
                    f"Response truncated, used {result['usage']['total_tokens']} / {self.max_tokens} tokens)"
                )

            # Extract response content
            response = result['choices'][0]['message']['content'].strip()
            logger.debug("Parser: LLM raw response preview: %s", response[:500])

            # Cleanup head of response if LLM ignored formatting instructions
            cleaned = self._clean_response(response)
            parsed = json.loads(cleaned)
            logger.debug("Parser: Parsed JSON after cleanup: %s", json.dumps(parsed)[:500])

            # Validate content
            is_valid, error_msg = self._validate_answer(parsed)
            if not is_valid:
                logger.error(f"Parser: Validation failed - {error_msg}")
                return self._error_response(robot_type, f"Invalid command structure: {error_msg}")

            logger.info("Parser: Parsing successful")

            # save the parsed command if logging is enabled
            if self.log_parsing:
                self._save_parsed_command(parsed)

            return {"command": parsed, "status": "success"}

        # Network and API errors
        except requests.exceptions.ConnectionError:
            logger.error("Parser: LM Studio connection error")
            return self._error_response(robot_type, f"LM Studio not running at {self.api_base}")

        except requests.exceptions.Timeout:
            logger.error("Parser: LLM request timed out")
            return self._error_response(robot_type, f"LLM request timed out after {self.timeout}s")

        except requests.exceptions.HTTPError as e:
            logger.exception("Parser: HTTP error from LLM")
            return self._error_response(robot_type, f"HTTP error: {e}")

        except KeyError as e:
            logger.exception("Parser: Unexpected API structure missing key")
            return self._error_response(robot_type, f"Unexpected API structure: missing {e}")

        # Parsing errors
        except json.JSONDecodeError as e:
            logger.error("Parser: JSON decode error")
            return self._error_response(robot_type, f"Invalid JSON from LLM: {e}")

        except RuntimeError as e:
            logger.exception("Parser: Runtime error during parsing")
            return self._error_response(robot_type, str(e))

        except Exception as e:
            logger.exception("Parser: Unexpected exception")
            return self._error_response(robot_type, f"Unexpected error: {e}")

    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """
        Send prompt to LM Studio API.

        Args:
            user_prompt: User message to send to LLM

        Returns:
            Full API response dictionary

        Raises:
            requests.HTTPError: On HTTP error status codes
            requests.ConnectionError: If LM Studio is not running
            requests.Timeout: On timeout
        """
        response = requests.post(
            f"{self.api_base}/chat/completions",
            json={
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            },
            timeout=self.timeout
        )

        response.raise_for_status()
        return response.json()

    def _clean_response(self, response: str) -> str:
        """
        Remove markdown code fences if LLM ignored formatting instructions.

        Handles responses like: ```json\n{...}\n```
        """
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        return response.strip()

    def _validate_answer(self, parsed: Dict) -> tuple[bool, str]:
        """
        Validate parsed command structure and action definitions.

        Args:
            parsed: Parsed JSON from LLM response

        Returns:
            (is_valid, error_message) - error_message empty string if valid
        """

        # Check for missing top-level fields
        for field in ["mode", "robot", "commands"]:
            if field not in parsed:
                return False, f'Missing required field: "{field}"'

        # Validate commands is array and not empty
        if not isinstance(parsed["commands"], list):
            return False, "Commands must be an array"

        if not parsed["commands"]:
            return False, "Commands array is empty"

        # Validate each command
        valid_actions = set(self.ruleset["primitives"].keys())

        for cmd in parsed["commands"]:
            # Check action exists
            if "action" not in cmd:
                return False, "Missing action field in command"

            action = cmd["action"]

            # Check action is valid
            if action not in valid_actions:
                return False, f'Invalid action type: "{action}"'

            # Action-specific validation
            if action == "move":
                if "target" not in cmd or not isinstance(cmd["target"], dict):
                    return False, "Move command missing target"
                if "name" not in cmd["target"]:
                    return False, "Move target missing name"
                if "motion_type" in cmd and cmd["motion_type"] not in ["moveJ", "moveL"]:
                    return False, "Invalid motion type"

            elif action == "gripper":
                if "command" not in cmd:
                    return False, "Gripper command missing command field"
                if cmd["command"] not in ["open", "close"]:
                    return False, "Invalid gripper command"

            elif action == "wait":
                if "duration_s" not in cmd:
                    return False, "Wait command missing duration"
                if not isinstance(cmd["duration_s"], (int, float)):
                    return False, "Wait duration must be a number"

            elif action == "teach_pose":
                if "pose_name" not in cmd:
                    return False, "Teach pose missing pose name"

            elif action == "delete_pose":
                if "pose_name" not in cmd:
                    return False, "Delete pose missing pose name"

        return True, ""

    def _error_response(self, robot_type: str, error_msg: str) -> Dict[str, Any]:
        """Build standardized error response structure."""
        return {
            "command": {"robot": robot_type, "mode": self.mode},
            "status": "error",
            "error": error_msg
        }

    def _save_parsed_command(self, parsed: Dict[str, Any]) -> None:
        timestamp = time.strftime("%y%m%d_%H%M%S")
        filename = f"{self.log_path}/{timestamp}_parse_result.json"
        with open(filename, "w") as f:
            json.dump(parsed, f, indent=4)
        logger.info(f"Parser: Saved parsed command to {filename}")


def main():
    """Test parser with sample commands."""
    parser = CodeParser()

    test_commands = [
        ("Open the gripper", "Franka Emika"),
        ("Teach a new pose called NewHomePos", "Franka Emika"),
        ("Move to Home position and close gripper", "Universal Robot"),
        ("Move to Home position, then to Pick position, open gripper, move to Place position, and close gripper", "Universal Robot"),
    ]

    for text, robot_type in test_commands:
        print(f"\n{'=' * 60}")
        print(f"Input: {text} | Robot: {robot_type}")

        result = parser.parse(text, robot_type)

        print("Parsed Command:")
        print(json.dumps(result, indent=3))

if __name__ == "__main__":
    main()
