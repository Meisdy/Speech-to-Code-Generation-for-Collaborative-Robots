# parser_module.py
import json
import requests
from typing import Dict, Any
from pathlib import Path
import config

"""
To do:
    check other errors that should get catched if possible
    cleanup code more? 
    test with more commands and edge cases
    test implmenetation in pipeline
    check if code is sound in terms of best practices, error handling, etc.
    
Notes: 
    Consider adding logging of all interactions for debugging (with timestamps, input, output, errors) - can be toggled in config

"""




class CodeParser:
    """LLM-based parser for converting natural language to robot commands."""

    def __init__(self):
        self.api_base: str = config.LLM_API_BASE
        self.model_name: str = config.LLM_MODEL_NAME
        self.temperature: float = config.LLM_TEMPERATURE
        self.max_tokens: int = config.LLM_MAX_TOKENS
        self.timeout: int = config.LLM_TIMEOUT

        self.ruleset: Dict = self._load_json("ruleset.json")
        self.command_schema: Dict = self._load_json("command_schema.json")
        self.system_prompt: str = self._build_system_prompt()


    def _load_json(self, filename: str) -> Dict:
        """Load JSON file from project root."""
        file_path = Path(__file__).parent / filename
        with open(file_path, 'r') as f:
            return json.load(f)

    def _build_system_prompt(self) -> str:
        """Construct system prompt with ruleset and schema."""
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
                - If you want to add feedback, add it to the "message" field
                """

    def parse(self, text: str, robot_type: str) -> Dict[str, Any]:
        """Parse natural language command to structured JSON."""
        user_prompt = f"Robot type: {robot_type}\nCommand: {text}\n\nGenerate JSON output:"

        try:
            result = self._call_llm(user_prompt)

            # Check for token limit truncation
            if result['choices'][0].get('finish_reason') == 'length':
                return self._error_response(robot_type, f"Response truncated, used {result['usage']['total_tokens']} / {self.max_tokens} tokens)")

            # Extract and clean response
            response = result['choices'][0]['message']['content'].strip()
            cleaned = self._clean_response(response) # Remove markdown fences if present
            parsed = json.loads(cleaned)

            return {"command": parsed, "status": "success"}

        # Handle various exceptions and return standardized error responses
        except requests.exceptions.ConnectionError:
            return self._error_response(robot_type, f"LM Studio not running at {self.api_base}")

        except requests.exceptions.Timeout:
            return self._error_response(robot_type, f"LLM request timed out after {self.timeout}s")

        except json.JSONDecodeError as e:
            return self._error_response(robot_type, f"Invalid JSON from LLM: {e}")

        except RuntimeError as e:
            return self._error_response(robot_type, str(e))

        except Exception as e:
            return self._error_response(robot_type, f"Unexpected error: {e}")

    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Call LM Studio API and return full result dict."""
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

        return response.json()

    def _clean_response(self, response: str) -> str:
        """Remove markdown code fences if present."""
        if response.startswith("```"):
            print("Warning: LLM returned markdown-wrapped JSON")  # or proper logging
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        return response.strip()

    def _error_response(self, robot_type: str, error_msg: str) -> Dict[str, Any]:
        """Build standardized error response."""
        return {
            "command": {"robot": robot_type, "mode": "live"},
            "status": "error",
            "error": error_msg
        }


def main():
    parser = CodeParser()

    test_commands = [
        ("Open the gripper", "Franka Emika"),
        ("Teach a new pose called NewHomePos", "Franka Emika"),
        ("Move to Home position and close gripper", "Universal Robots"),
    ]

    for text, robot_type in test_commands:
        print(f"\n{'=' * 60}")
        print(f"Input: {text} | Robot: {robot_type}")

        result = parser.parse(text, robot_type)

        print("Parsed Command:")
        print(json.dumps(result, indent=3))


if __name__ == "__main__":
    main()
