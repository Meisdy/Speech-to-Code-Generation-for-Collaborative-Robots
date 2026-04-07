#!/usr/bin/env python3
"""Timing analysis script for evaluation run."""

import json
import re
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "Data"
FRONTEND_LOG = Path(__file__).parent / "Logs" / "cobot_frontend.log"
BACKEND_FRANKA_LOG = Path(__file__).parent / "Logs" / "cobot_backend_Franka.log"
BACKEND_UR_LOG = Path(__file__).parent / "Logs" / "cobot_backend_UR.log"


def parse_timestamp(line):
    """Extract timestamp from log line."""
    match = re.match(r"(\d{2}):(\d{2}):(\d{2})", line)
    if match:
        h, m, s = map(int, match.groups())
        return datetime(2026, 4, 3, h, m, s)
    return None


def load_parse_results():
    """Load all parse result files and return dict mapping timestamp to data."""
    results = {}
    for json_file in DATA_DIR.glob("*_parse_result.json"):
        match = re.match(r"(\d{6})_(\d{6})_parse_result.json", json_file.name)
        if match:
            timestamp_str = match.group(2)
            with open(json_file, "r") as f:
                data = json.load(f)
            results[timestamp_str] = data
    return results


def categorize_command(parse_data):
    """Categorize command from parse result."""
    commands = parse_data.get("commands", [])
    cmd_count = len(commands)
    
    if cmd_count == 1:
        cmd = commands[0]
        action = cmd.get("action")
        if action == "move":
            motion = cmd.get("motion_type", "")
            if motion == "moveJ":
                return "Move J"
            elif motion == "moveL":
                return "Move L"
        elif action == "gripper":
            return "Gripper"
        elif action == "pose" and cmd.get("command") == "teach":
            return "Teach Pose"
    elif cmd_count == 2:
        motions = [c.get('motion_type') for c in commands]
        actions = [c.get('action') for c in commands]
        # Two-step sequence: exactly moveJ + moveJ (p1 then home pattern)
        if motions == ['moveJ', 'moveJ']:
            return "Two-step sequence"
        elif actions == ['move', 'gripper']:
            # 2-command with move + gripper - categorize as Unknown (edge case)
            return "Unknown"
    elif cmd_count == 4:
        actions = [c.get('action') for c in commands]
        gripper_actions = [c.get('command') for c in commands if c.get('action') == 'gripper']
        
        # Check if this is a pick operation (has both close and open gripper)
        if 'close' in gripper_actions and 'open' in gripper_actions:
            # Find the final move command to determine pick+place vs pick+offset
            for c in reversed(commands):
                if c.get('action') == 'move':
                    target = c.get('target', {})
                    target_type = target.get('type', '')
                    offset = target.get('offset', {})
                    x_mm = offset.get('x_mm', 0)
                    y_mm = offset.get('y_mm', 0)
                    
                    # Check if place target is p2 (no or zero offset) → Pick & place
                    if target_type == 'offset_from_pose' and target.get('name') == 'p2':
                        if x_mm == 0 and y_mm == 0:
                            return "Pick and place"
                    elif target_type == 'named_pose' and target.get('name') == 'p2':
                        return "Pick and place"
                    
                    # Check if place target is p1 with offset 80,50 → Pick + offset
                    if target_type == 'offset_from_pose' and target.get('name') == 'p1':
                        if x_mm == 80 and y_mm == 50:
                            return "Pick + offset"
                    elif target_type == 'named_pose' and target.get('name') == 'p1':
                        return "Pick + offset"
    elif cmd_count == 5:
        actions = [c.get('action') for c in commands]
        if 'wait' in actions:
            return "Multi-step"
    
    return "Unknown"


def parse_frontend_log():
    """Parse frontend log for timing data."""
    trials = []
    current_trial = None
    
    with open(FRONTEND_LOG, "r") as f:
        for line in f:
            if "--- New trial start ---" in line:
                if current_trial:
                    trials.append(current_trial)
                ts = parse_timestamp(line)
                current_trial = {
                    "start": ts,
                    "record_start": None,
                    "audio_saved": None,
                    "parse_done": None,
                    "exec_done": None,
                    "command_summary": None,
                }
            elif "Recording stopped" in line and current_trial:
                current_trial["recording_stopped"] = parse_timestamp(line)
            elif "Saved audio to" in line and current_trial:
                current_trial["audio_saved"] = parse_timestamp(line)
            elif "transcribed text" in line and current_trial:
                current_trial["asr_transcribed"] = parse_timestamp(line)
            elif "Parsing successful" in line and current_trial:
                current_trial["parse_done"] = parse_timestamp(line)
            elif "Execution: Backend executed command successfully" in line and current_trial:
                current_trial["exec_done"] = parse_timestamp(line)
            elif "Parser: Command summary" in line:
                match = re.search(r'"([^"]+)"', line)
                if match and current_trial:
                    current_trial["command_summary"] = match.group(1)
    
    if current_trial:
        trials.append(current_trial)
    
    return trials


def parse_backend_log(log_path):
    """Parse backend log for execution timing."""
    exec_times = {}
    
    with open(log_path, "r") as f:
        receive_time = None
        robot = None
        commands = None
        
        for line in f:
            if "Received message:" in line:
                match = re.search(r"execute_sequence.*?'robot':\s*'(\w+)'", line)
                if match:
                    robot = match.group(1)
                match = re.search(r"'commands':\s*(\[.*\])", line)
                if match:
                    try:
                        commands = eval(match.group(1))
                    except:
                        commands = None
                receive_time = parse_timestamp(line)
                
            elif "Sent response:" in line and receive_time:
                response_time = parse_timestamp(line)
                duration = (response_time - receive_time).total_seconds() if receive_time and response_time else 0
                
                if robot and commands:
                    key = receive_time.strftime("%H%M%S")
                    exec_times[key] = {
                        "robot": robot,
                        "duration": duration,
                        "commands": commands,
                    }
                receive_time = None
                robot = None
                commands = None
    
    return exec_times


# Cold start trials to exclude (3 total - first Franka, first UR, and rejected P99)
EXCLUDE_PARSE = {"112525", "114528", "113842"}


def main():
    print("Loading data...")
    parse_results = load_parse_results()
    trials = parse_frontend_log()
    franka_times = parse_backend_log(BACKEND_FRANKA_LOG)
    ur_times = parse_backend_log(BACKEND_UR_LOG)
    
    print(f"Loaded {len(parse_results)} parse results")
    print(f"Loaded {len(trials)} trials from frontend log")
    
    categorized = []
    for trial in trials:
        start = trial["start"]
        parse_done = trial["parse_done"]
        exec_done = trial["exec_done"]
        summary = trial["command_summary"]
        
        if not all([start, parse_done, exec_done]):
            continue
        
        # ASR time: from recording stopped to ASR transcription complete
        recording_stopped = trial.get("recording_stopped")
        asr_transcribed = trial.get("asr_transcribed")
        if recording_stopped and asr_transcribed:
            asr_time = (asr_transcribed - recording_stopped).total_seconds()
            # Force minimum 1 second since transcription takes at least 1s
            if asr_time < 1.0:
                asr_time = 1.0
        else:
            # Fallback to audio saved to parse time if we don't have exact transcription time
            audio_saved = trial["audio_saved"]
            if audio_saved:
                asr_time = (parse_done - audio_saved).total_seconds()
            else:
                asr_time = 0
        
        total_exec = (exec_done - start).total_seconds()
        
        parse_ts = parse_done.strftime("%H%M%S")
        
        if parse_ts in parse_results:
            parse_data = parse_results[parse_ts]
            robot = parse_data.get("robot", "")
            command_type = categorize_command(parse_data)
            
            if robot == "franka" and parse_ts in franka_times:
                exec_time = franka_times[parse_ts]["duration"]
            elif robot == "ur" and parse_ts in ur_times:
                exec_time = ur_times[parse_ts]["duration"]
            else:
                exec_time = total_exec - asr_time
            
            categorized.append({
                "type": command_type,
                "robot": robot,
                "asr_time": asr_time,
                "exec_time": exec_time,
                "total_time": total_exec,
                "parse_done": parse_done,
                "parse_ts": parse_ts,
            })
    
    # Exclude cold start trials (first execution for each robot)
    categorized = [c for c in categorized if c['parse_ts'] not in EXCLUDE_PARSE]
    print(f"After excluding cold start: {len(categorized)} trials")
    
    # Group by command type
    groups = {}
    for c in categorized:
        if c["type"] not in groups:
            groups[c["type"]] = []
        groups[c["type"]].append(c)
    
    print(f"Command types found: {list(groups.keys())}")
    
    # Calculate and print stats
    print("\n" + "="*120)
    print(f"{'Command Type':<18} | {'N':>3} | {'ASR Avg (s)':>10} | {'Exec Avg (s)':>12} | {'Total Avg (s)':>12} | {'Total Range (s)':>15}")
    print("="*120)
    
    # Build complete list of categories to display
    # Note: Unknown exists for edge case (moveL + gripper close) but is not shown in table
    display_order = ["Move J", "Move L", "Gripper", "Teach Pose", "Two-step sequence", "Pick and place", "Pick + offset", "Multi-step"]
    
    for cmd_type in display_order:
        if cmd_type in groups:
            data = groups[cmd_type]
            n = len(data)
            asr_avg = sum(d["asr_time"] for d in data) / n
            exec_avg = sum(d["exec_time"] for d in data) / n
            total_avg = sum(d["total_time"] for d in data) / n
            total_min = min(d["total_time"] for d in data)
            total_max = max(d["total_time"] for d in data)
            
            print(f"{cmd_type:<18} | {n:>3} | {asr_avg:>10.2f} | {exec_avg:>12.2f} | {total_avg:>12.2f} | [{total_min:.1f}-{total_max:.1f}]")
    
    print("="*120)


if __name__ == "__main__":
    main()
