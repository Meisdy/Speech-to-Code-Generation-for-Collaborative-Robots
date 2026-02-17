# test_parser.py
import pytest
from parsing_module import CodeParser


class TestCommandValidation:

    def test_valid_command(self):
        """Test that valid command passes validation"""
        valid_cmd = {
            "mode": "live",
            "robot": "franka",
            "commands": [{"action": "gripper", "command": "open"}]
        }
        parser = CodeParser()
        is_valid, error = parser._validate_answer(valid_cmd)
        assert is_valid
        assert error == ""

    def test_missing_mode(self):
        """Test rejection when mode field missing"""
        invalid_cmd = {"robot": "franka", "commands": []}
        parser = CodeParser()
        is_valid, error = parser._validate_answer(invalid_cmd)
        assert not is_valid
        assert "mode" in error

    @pytest.mark.parametrize("action,cmd_data,should_pass", [
        ("gripper", {"action": "gripper", "command": "open"}, True),
        ("gripper", {"action": "gripper", "command": "invalid"}, False),
        ("wait", {"action": "wait", "duration_s": 1.0}, True),
        ("wait", {"action": "wait", "duration_s": "bad"}, False),
    ])
    def test_action_validation(self, action, cmd_data, should_pass):
        """Test various action scenarios"""
        cmd = {"mode": "live", "robot": "franka", "commands": [cmd_data]}
        parser = CodeParser()
        is_valid, _ = parser._validate_answer(cmd)
        assert is_valid == should_pass
