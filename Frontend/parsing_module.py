"""
LLM-based parser for converting natural language to robot commands.

Uses LM Studio API to transform speech-to-text transcriptions into structured
JSON commands according to defined rulesets and schemas.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

import Frontend.config_frontend as config_frontend

logger = logging.getLogger("cobot")


class CodeParser:
    """Converts natural language commands to structured robot control JSON via LLM."""

    # Keys whose string values must always be lowercase identifiers.
    # "motion_type" is intentionally excluded — moveJ/moveL are camelCase by spec.
    _NAME_KEYS: frozenset[str] = frozenset({"name", "robot", "pose_name", "script_name"})

    def __init__(self) -> None:
        self.api_base: str = config_frontend.LLM_API_BASE
        self.model_name: str = config_frontend.LLM_MODEL_NAME
        self.temperature: float = config_frontend.LLM_TEMPERATURE
        self.max_tokens: int = config_frontend.LLM_MAX_TOKENS
        self.timeout: int = config_frontend.LLM_TIMEOUT
        self.log_parsing: bool = config_frontend.LOGGING_SAVE_PARSE
        self.log_path: str = config_frontend.DATA_DIR

        # Errors here propagate to Controller.__init__ and are caught in main.py
        self.ruleset: dict = self._load_json("ruleset.json")
        self.command_schema: dict = self._load_json("command_schema.json")
        self.system_prompt: str = self._load_prompt("system_prompt.txt")

    def parse(self, text: str, robot_key: str) -> dict[str, Any]:
        """Parse natural language to structured robot command JSON.

        Returns {"command": {...}, "status": "success"} or
                {"command": {...}, "status": "error", "error": "..."}
        """
        if not text or len(text.strip()) < 7:  # Arbitrary minimum length to filter out non-commands
            return self._error_response(robot_key, "Command empty or too short")

        user_prompt = f"Robot type: {robot_key}\nCommand: {text}\n\nGenerate JSON output:"

        try:
            result = self._call_llm(user_prompt)

            if result['choices'][0].get('finish_reason') == 'length':
                return self._error_response(
                    robot_key,
                    f"Response truncated, used {result['usage']['total_tokens']} / {self.max_tokens} tokens"
                )

            response = result['choices'][0]['message']['content'].strip()
            logger.debug("LLM raw response preview: %s", response[:500])

            cleaned = self._clean_response(response)
            parsed = json.loads(cleaned)
            logger.debug(f'Before calling remove redundant {parsed}')
            parsed["commands"] = self._remove_redundant_moves(parsed["commands"]) # This is the bug fix for double move commands when using offset keyword
            logger.debug(f'Before calling remove redundant {parsed}')
            parsed = self._normalize_name_fields(parsed)  # Force lowercase on all name/identifier fields to fix occasional LLM name hallucination
            logger.debug("Parsed JSON after cleanup: %s", json.dumps(parsed)[:500])

            is_valid, error_msg = self._validate_answer(parsed)
            if not is_valid:
                logger.warning("Validation failed - %s", error_msg)
                return self._error_response(robot_key, f"Invalid command structure: {error_msg}")

            logger.info("Parsing successful")

            if self.log_parsing:
                self._save_parsed_command(parsed)

            return {"command": parsed, "status": "success"}

        except requests.exceptions.ConnectionError:
            logger.error("LM Studio connection error")
            return self._error_response(robot_key, f"LM Studio not running at {self.api_base}")

        except requests.exceptions.Timeout:
            logger.error("LLM request timed out")
            return self._error_response(robot_key, f"LLM request timed out after {self.timeout}s")

        except requests.exceptions.HTTPError as e:
            logger.exception("HTTP error from LLM")
            return self._error_response(robot_key, f"HTTP error: {e}")

        except KeyError as e:
            logger.exception("Unexpected API structure missing key")
            return self._error_response(robot_key, f"Unexpected API structure: missing {e}")

        except json.JSONDecodeError as e:
            logger.error("JSON decode error")
            return self._error_response(robot_key, f"Invalid JSON from LLM: {e}")

        except RuntimeError as e:
            logger.exception("Runtime error during parsing")
            return self._error_response(robot_key, str(e))

        except Exception as e:  # Intentionally broad — LLM libraries don't document all exceptions
            logger.exception("Unexpected exception")
            return self._error_response(robot_key, f"Unexpected error: {e}")

    def _load_json(self, filename: str) -> dict:
        """Load JSON file from module directory."""
        file_path = Path(__file__).parent / filename
        with open(file_path, "r") as f:
            return json.load(f)

    def _load_prompt(self, filename: str) -> str:
        """Load and interpolate a prompt template from the prompts directory."""
        file_path = Path(__file__).parent / "prompts" / filename
        content = file_path.read_text(encoding="utf-8")
        return content.replace("{{ruleset}}", json.dumps(self.ruleset, indent=2)) \
                      .replace("{{command_schema}}", json.dumps(self.command_schema, indent=2))

    def _call_llm(self, user_prompt: str) -> dict[str, Any]:
        """Send prompt to LM Studio and return the full API response."""
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
        """Strip markdown code fences that the LLM adds despite instructions."""
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        return response.strip()

    def _normalize_name_fields(self, data: Any) -> Any:
        """Recursively lowercase string values for name and identifier keys.

        Enforces lowercase on fields in _NAME_KEYS regardless of LLM output casing.
        Recurses into dicts and lists; all other values pass through unchanged.
        """
        if isinstance(data, dict):
            return {
                k: v.lower() if isinstance(v, str) and k in self._NAME_KEYS else self._normalize_name_fields(v)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self._normalize_name_fields(item) for item in data]
        return data

    def _validate_answer(self, parsed: dict) -> tuple[bool, str]:
        """Validate parsed command structure. Returns (is_valid, error_message)."""
        for field in ["robot", "commands"]:
            if field not in parsed:
                return False, f'Missing required field: "{field}"'

        if len(parsed["commands"]) == 0:
            message = parsed.get("message", "Input was not a valid robot command.")
            logger.info("Parser: Input rejected — %s", message)
            # surface the message to the user and stop here
            return False, f'No accepted command found'

        if not isinstance(parsed["commands"], list) or not parsed["commands"]:
            return False, "Commands must be a non-empty array"

        valid_actions = set(self.ruleset["primitives"].keys())

        for cmd in parsed["commands"]:
            if "action" not in cmd:
                return False, "Missing action field in command"

            action = cmd["action"]

            if action not in valid_actions:
                return False, f'Invalid action type: "{action}"'

            if action == "move":
                if "target" not in cmd or not isinstance(cmd["target"], dict):
                    return False, "Move command missing target"
                target = cmd["target"]
                if "name" not in target and target.get("type") != "offset_from_current":
                    return False, "Move target missing name"
                if "motion_type" in cmd and cmd["motion_type"] not in ["moveJ", "moveL"]:
                    return False, "Invalid motion type"
                valid_target_types = ["named_pose", "offset_from_pose", "offset_from_current"]
                if target.get("type") not in valid_target_types:
                    return False, f"Invalid target type: \"{target.get('type')}\""

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

            elif action == "pose":
                if "command" not in cmd:
                    return False, "Pose command missing command field"
                if cmd["command"] not in ["teach", "delete"]:
                    return False, f'Invalid pose command: "{cmd["command"]}"'
                if "pose_name" not in cmd:
                    return False, "Pose command missing pose_name"

            elif action == "script":
                if "command" not in cmd:
                    return False, "Script command missing command field"
                if cmd["command"] not in ["start", "stop", "run", "save", "delete"]:
                    return False, f"Invalid script command: {cmd['command']}"
                if "script_name" not in cmd:
                    return False, "Script command missing script_name"
                if cmd["command"] == "run":
                    if "loop" not in cmd:
                        return False, "Script run command missing loop"
                    if not isinstance(cmd["loop"], int):
                        return False, "Script loop must be an integer"

        return True, ""

    def _remove_redundant_moves(self, commands: list) -> list:
        """Drop a named_pose move immediately before an offset_from_pose to the same pose.

        The LLM habitually inserts a redundant named_pose move before offset moves —
        the offset move already encodes the base pose so the prior move is never needed.
        """
        cleaned = []
        for i, cmd in enumerate(commands):
            if cmd.get("action") == "move" and cmd.get("target", {}).get("type") == "named_pose":
                next_cmd = commands[i + 1] if i + 1 < len(commands) else None
                if (
                    next_cmd
                    and next_cmd.get("action") == "move"
                    and next_cmd.get("target", {}).get("type") == "offset_from_pose"
                    and next_cmd.get("target", {}).get("name") == cmd["target"]["name"]
                ):
                    logger.debug("Stripped redundant named_pose move before offset_from_pose")
                    continue
            cleaned.append(cmd)
        return cleaned

    def _error_response(self, robot_key: str, error_msg: str) -> dict[str, Any]:
        """Build standardised error response."""
        return {"command": {"robot": robot_key}, "status": "error", "error": error_msg}

    def _save_parsed_command(self, parsed: dict[str, Any]) -> None:
        """Save parsed command to the data folder for debugging."""
        try:
            timestamp = time.strftime("%y%m%d_%H%M%S")
            filepath = Path(self.log_path) / f"{timestamp}_parse_result.json"
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w") as f:
                json.dump(parsed, f, indent=4)
            logger.info("Saved parsed command to %s", filepath)
        except OSError as e:
            logger.error("Failed to save parsed command: %s", e)


def main() -> None:
    """Test parser with sample commands."""
    parser = CodeParser()
    robot_keys = list(config_frontend.ROBOT_TYPE_KEYS.keys())

    test_commands = [
        ("Open the gripper", robot_keys[0]),
        ("Teach a new pose called new_home", robot_keys[0]),
        ("Move to home position and close gripper", robot_keys[1]),
        ("Move to home, then pick, open gripper, move to place, close gripper", robot_keys[1]),
    ]

    for text, robot_type in test_commands:
        print(f"\n{'=' * 60}")
        print(f"Input: {text} | Robot: {robot_type}")
        result = parser.parse(text, robot_type)
        print(json.dumps(result, indent=3))


if __name__ == "__main__":
    main()