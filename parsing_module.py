# parser_module.py
import json
import requests
from typing import Dict, Any
from pathlib import Path
import config


class CodeParser:
    """
    LLM-based parser for converting natural language to robot commands.

    Uses LM Studio API to parse speech transcriptions into structured JSON
    commands according to ruleset and command schema definitions.
    """

    def __init__(self):
        # LLM configuration from config
        self.api_base: str = config.LLM_API_BASE
        self.model_name: str = config.LLM_MODEL_NAME
        self.temperature: float = config.LLM_TEMPERATURE
        self.max_tokens: int = config.LLM_MAX_TOKENS
        self.timeout: int = config.LLM_TIMEOUT

        # Load ruleset and command schema
        self.ruleset: Dict = self._load_json("ruleset.json")
        self.command_schema: Dict = self._load_json("command_schema.json")

        # Build system prompt once
        self.system_prompt: str = self._build_system_prompt()

    def _load_json(self, filename: str) -> Dict:
        """Load JSON file from project root."""
        file_path = Path(__file__).parent / filename
        with open(file_path, 'r') as f:
            return json.load(f)

    def _build_system_prompt(self) -> str:
        """Construct system prompt with ruleset and schema information."""
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
                - If you want to add feedback, then add it to the "message" field in the output JSON, but do not include it if not needed
                """

    def parse(self, text: str, robot_type: str) -> Dict[str, Any]:
        """
        Parse natural language command to structured JSON.

        Args:
            text: Natural language command from ASR
            robot_type: "Franka Emika" | "Universal Robots" | "Mock Adapter"

        Returns:
            {"command": {...}, "status": "success"}
        """
        # Build user prompt
        user_prompt = f"Robot type: {robot_type}\nCommand: {text}\n\nGenerate JSON output:"

        # Call LLM
        response = self._call_llm(user_prompt)

        # Parse and validate JSON
        parsed_command = self._parse_and_validate(response, robot_type)

        return {
            "command": parsed_command,
            "status": "success",
            "raw_response": response
        }

    def _call_llm(self, user_prompt: str) -> str:
        """Call LM Studio API and return response text."""
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

        result = response.json()
        return result['choices'][0]['message']['content'].strip()

    def _parse_and_validate(self, response: str, robot_type: str) -> Dict[str, Any]:
        """Parse LLM response and validate against schema."""
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
            response = response.strip()

        # Parse JSON
        parsed = json.loads(response)

        # Ensure required fields
        if "robot" not in parsed:
            parsed["robot"] = robot_type

        if "mode" not in parsed:
            parsed["mode"] = "live"

        return parsed


# Testing stub
def main():
    parser = CodeParser()

    test_commands = [
        ("Open the gripper", "Franka Emika"),
        ("Move to Home position and close gripper", "Universal Robots"),
        ("Teach a new pose called PickPosition", "Franka Emika")
    ]

    for text, robot_type in test_commands:
        print(f"\n{'=' * 60}")
        print(f"Input: {text}")
        print(f"Robot: {robot_type}")

        result = parser.parse(text, robot_type)

        print(f"Status: {result['status']}")
        print(f"Command: {json.dumps(result['command'], indent=2)}")


if __name__ == "__main__":
    main()
