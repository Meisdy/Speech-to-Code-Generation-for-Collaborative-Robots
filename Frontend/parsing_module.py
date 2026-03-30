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

    def __init__(self):
        self.api_base: str = config_frontend.LLM_API_BASE
        self.model_name: str = config_frontend.LLM_MODEL_NAME
        self.temperature: float = config_frontend.LLM_TEMPERATURE
        self.max_tokens: int = config_frontend.LLM_MAX_TOKENS
        self.timeout: int = config_frontend.LLM_TIMEOUT
        self.mode: str = config_frontend.FRAMEWORK_MODE
        self.log_parsing: bool = config_frontend.LOGGING_SAVE_PARSE
        self.log_path: str = config_frontend.DATA_DIR

        # Errors here propagate to Controller.__init__ and are caught in main.py
        self.ruleset: dict = self._load_json("ruleset.json")
        self.command_schema: dict = self._load_json("command_schema.json")
        self.system_prompt: str = self._build_system_prompt()

    def parse(self, text: str, robot_key: str) -> dict[str, Any]:
        """Parse natural language to structured robot command JSON.

        Returns {"command": {...}, "status": "success"} or
                {"command": {...}, "status": "error", "error": "..."}
        """
        if not text or len(text.strip()) < 8:
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
            parsed["commands"] = self._remove_redundant_moves(parsed["commands"]) # This is the bug fix for double move commands when using offset keyword
            logger.debug("Parsed JSON after cleanup: %s", json.dumps(parsed)[:500])

            is_valid, error_msg = self._validate_answer(parsed)
            if not is_valid:
                logger.error("Validation failed - %s", error_msg)
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

    def _build_system_prompt(self) -> str:
        """Build LLM system prompt with ruleset and schema definitions."""
        return f"""You are a robot command parser. Convert natural language to structured JSON commands.

AVAILABLE PRIMITIVES:
{json.dumps(self.ruleset, indent=2)}

REQUIRED OUTPUT FORMAT:
{json.dumps(self.command_schema, indent=2)}

GENERAL RULES:
- Return ONLY valid JSON (no markdown, no explanations)
- Use only actions from AVAILABLE PRIMITIVES
- Commands array can contain multiple sequential commands
- Use defaults from ruleset when parameters not specified
- Always include "mode", "robot", and "commands" fields
- Add any feedback to the "message" field
- Always use the JSON format of the command schema exactly
- If the input does not contain a clear robot command, return an empty commands array and explain in the "message" field why the input was rejected
- Do not infer or guess commands from ambiguous or non-robot-related speech

NAMING RULES:
- Use snake_case for ALL pose names — always lowercase (e.g. "d1" not "D1", "p1" not "P1", "home" not "Home")
- Always convert number words to digits in pose names (e.g. "test_1" not "test_one", "position_2" not "position_two")

UNIT AND DIRECTION RULES:
- Map spatial directions to axes: up/down = Z, forward/back = X, left/right = Y
- Always convert measurements to millimetres (e.g. 5cm → 50.0, 1 inch → 25.4)
- If no unit is given for a distance, assume millimetres
- Ignore speed qualifiers unless an explicit numeric value is given; omit the speed field to use defaults

TARGET RULES:
- Use offset_from_current when no reference pose is mentioned (e.g. "move 500mm in x")
- Use offset_from_pose when a reference pose is mentioned (e.g. "move 50mm above home")
- When the user asks to 'reconnect', execute disconnect then connect
- Never add intermediate approach or retract moves unless explicitly stated. Named poses already encode the final target position.

MOTION TYPE AND GRIPPER RULES:
Each utterance maps to exactly one of these patterns. Apply the first matching pattern and produce no other motion type or gripper action:

- "move to" / "go to" / "drive to" / "reach" / "send to":
    motion: moveJ, gripper: none

- "linear" / "straight" / "cartesian" (without pick/place vocabulary):
    motion: moveL, gripper: none

- "pick" / "grab":
    motion: moveL to target, then close_gripper
    close_gripper is MANDATORY — NEVER substitute open_gripper
    NEVER use moveJ for pick — always moveL
    Example: "pick at p4" → moveL to p4, close_gripper

- "place" / "put" / "release":
    motion: moveL to target, then open_gripper
    open_gripper is MANDATORY — NEVER substitute close_gripper

- If none of the above pick/place words appear in the utterance:
    NO gripper command is generated under any circumstance
    Every move in the output uses moveJ unless "linear"/"straight"/"cartesian" is present

- The motion type and gripper state of one command NEVER influence the next command in a sequence
- For pick-and-place like "pick at p1 and place 50mm in x": the place target uses offset_from_pose with the pick pose as reference, not offset_from_current
- Each comma-separated or "then"-separated sub-command is parsed INDEPENDENTLY
- The pattern matched for sub-command N has zero effect on sub-command N+1
- "Move to P2, then pick at P1" produces exactly:
    1. moveJ to p2    (no gripper)
    2. moveL to p1
    3. close_gripper
    
PICK-AND-PLACE SEQUENCE RULE:
For any command containing both pick and place vocabulary,
the output sequence is ALWAYS and EXACTLY:
  1. moveL to pick target
  2. close_gripper
  3. moveL to place target  ← ALWAYS moveL, regardless of target type
  4. open_gripper
No intermediate lift, retract, or approach moves are added.
The gripper action for place (open_gripper) ALWAYS follows the
place move — it is NEVER inserted before it.
The place move is ALWAYS moveL — NEVER moveJ — even when the
place target is an offset or offset_from_pose.
Example: "pick at p1 and place at p2" →
  1. moveL to p1
  2. close_gripper
  3. moveL to p2
  4. open_gripper
Example: "pick at p1 and place at offset x=50, y=500" →
  1. moveL to p1
  2. close_gripper
  3. moveL to offset_from_pose p1 (x=50, y=500, z=0)
  4. open_gripper
  
POSE RULES:
- When teaching a pose, always set "overwrite": true regardless of whether 
  the user explicitly mentions overwriting.

SCRIPT RULES:
- A script action always produces exactly one command in the commands array
- "start" / "begin" / "record" / "new script" → command: "start"
- "end script" / "finish script" / "save" / "save as" / "call it" → command: "save"
- "play" / "run" / "execute" / "start script" → command: "run"
- "stop" / "halt" / "cancel script" → command: "stop"
- Always extract the script name from the utterance and apply snake_case (e.g. "call it pick routine" → "pick_routine")
- If no script name is given for "start" or "stop", use "unnamed_script"
- loop values for "run": 1 = once (default), -1 = infinite, n = exactly n times
- "once" / "one time" / "single" → loop: 1
- "infinite" / "forever" / "loop" / "continuously" / "non-stop" → loop: -1
- Any explicit count like "three times" / "5 times" → loop: that integer
- "loop" field is always required
- Do not generate any move, gripper, wait, or pose commands alongside a script command
- "delete" / "remove" / "erase" script → command: "delete"
- script_name is required for delete — if not provided, ask in the message field
"""

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

    def _validate_answer(self, parsed: dict) -> tuple[bool, str]:
        """Validate parsed command structure. Returns (is_valid, error_message)."""
        for field in ["mode", "robot", "commands"]:
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
        return {"command": {"robot": robot_key, "mode": self.mode}, "status": "error", "error": error_msg}

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