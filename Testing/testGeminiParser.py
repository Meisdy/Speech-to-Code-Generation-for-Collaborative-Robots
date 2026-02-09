import json
from pathlib import Path
from google import genai

"""
maybe change this to the cloud LLM from the evaluation. Then, download lib. 
"""


# Load API key from file
API_KEY_GEMINI = Path("api_key_gemini.txt")


def load_api_key():
    with API_KEY_GEMINI.open("r", encoding="utf-8") as f:
        return f.read().strip()


def load_schema():
    with Path("commands.json").open("r", encoding="utf-8") as f:
        return f.read()


def call_gemini(user_text: str, schema_text: str):
    api_key = load_api_key()
    client = genai.Client(api_key=api_key)

    system_prompt = f"""
You are a robot command parser for a collaborative robot.
You receive natural language commands and must OUTPUT ONLY VALID JSON
that follows this schema:

{schema_text}

Rules:
- Only output a single JSON object.
- Do not include any explanations, comments, or extra text.
- If a field is not applicable, simply omit it.
- Pose names are simple strings like "HOME", "P1", "P2".
"""

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[system_prompt, f"Command: {user_text}\nReturn the JSON now."]
    )

    raw = response.text

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in response:\n{raw}")

    json_str = raw[start:end + 1]
    return json.loads(json_str)


if __name__ == "__main__":
    schema_text = load_schema()

    test_commands = [
        "Go to P1.",
        "Open the gripper.",
        "Pick at P1 and place at P2 using linear motion.",
        '"Move to Home pos."',
        'Go back to P2"'
    ]

    for cmd in test_commands:
        print(f"\n--- Command: {cmd}")
        try:
            result = call_gemini(cmd, schema_text)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print("Error:", e)
