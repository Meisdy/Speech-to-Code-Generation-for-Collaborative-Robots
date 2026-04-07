# Evaluation Report
## Speech-to-Code Generation for Collaborative Robots

**Date:** 03 April 2026
**Session window:** 11:24 – 11:58
**Platforms tested:** Franka Panda · UR10e
**Microphone:** Røde Wireless GO 2
**Source logs:** [cobot_frontend.log](./Logs/cobot_frontend.log), [cobot_backend_Franka.log](./Logs/cobot_backend_Franka.log), [cobot_backend_UR.log](./Logs/cobot_backend_UR.log)
**Source data:** [Evaluation/Data/](./Data/) — 129 audio recordings + 125 parse-result JSONs (timestamp-named pairs)

---

## Summary

All eight tests passed. The framework achieved a 100% end-to-end success rate across both robot platforms (60/60 benchmark trials). The invalid-input rejection test produced five correct rejections. The backend swap was completed in approximately 2 minutes with no changes to code or any upstream module. Six ASR garbles were observed across the session; five were recovered correctly by the LLM parser, and one produced an incorrect IR in test 2.2 — the only parsing failure in the session, which did not affect execution safety and did not cause the test to fail.

| Research question                     | Tests     | Outcome  |
|---------------------------------------|-----------|----------|
| RQ1 — End-to-end success              | 1.1, 1.2  | **PASS** |
| RQ2 — Input variability and stability | 2.1 – 2.5 | **PASS** |
| RQ3 — Modularity and switch cost      | 3.1       | **PASS** |

---

## RQ1 — End-to-End Task Success

### Test 1.1 — Franka Panda (criterion: ≥ 24/30)

**Result: 30/30 · PASS**

All six benchmark tasks completed on all five trials. No failed or rejected trials. Every command reached the backend and returned a success response. The Franka MoveIt stack initialised once at 11:25:26 and remained active throughout all 30 trials without requiring a restart.

| Task | Command                                   | Trials | Outcome |
|------|-------------------------------------------|--------|---------|
| 1    | Go to P1                                  | 5/5    | Success |
| 2    | Go linear to P2                           | 5/5    | Success |
| 3    | Open gripper                              | 5/5    | Success |
| 4    | Teach current position as P3              | 5/5    | Success |
| 5    | Pick at P1 and place at P2                | 5/5    | Success |
| 6    | Pick at P1 and place at offset x=80, y=50 | 5/5    | Success |

*Task 3 note: the protocol requires closing the gripper before each trial to ensure the open command produces a visible state change. The frontend log therefore shows ten gripper commands during this block — five close resets followed by five open trials. Only the five open commands count as benchmark trials; the close commands are pre-trial resets and are not included in the trial count or timing analysis.*

### Test 1.2 — UR10e (criterion: ≥ 24/30)

**Result: 30/30 · PASS**

The identical task set produced identical outcomes after backend swap. The UR backend registered only the UR and mock controllers at startup; the Franka controller was not loaded because the backend detected it was not running on a Linux system with the required Franka MoveIt stack. First-connection activation took 22 seconds (hardware activation phase only, measured from robot activation signal at 11:45:28 to ready state at 11:45:50); the full end-to-end trial time including ASR, parsing, and execution was 37 seconds. This one-time cold-start trial is excluded from the timing table in the End-to-End Timing section; all subsequent UR trials reflect steady-state performance.

---

## RQ2 — Input Variability and Stability

### Test 2.1 — Repeatability (criterion: identical IR on all 5 trials, all classified as `Success`)

**Result: 5/5 · PASS**

The command `"Go to P1, then go to home"` produced an identical intermediate representation on all five trials:

```
moveJ to p1 → moveJ to home
```

All five trials were classified as `Success`. ASR confidence ranged from 0.92 to 0.95 across the five recordings.

### Test 2.2 — Paraphrase Robustness (criterion: ≥ 8/10 correct IR)

**Result: 9/10 · PASS**

Five paraphrases of the linear-motion command and five paraphrases of the teach-pose command were issued by voice. Nine of ten produced the correct IR.

| Task | Paraphrase                    | ASR output                       | IR correct                                    |
|------|-------------------------------|----------------------------------|-----------------------------------------------|
| A    | Move to P2 in a straight line | "Move to P2 in a straight line." | Yes                                           |
| A    | Go to P2 using linear motion  | "Go to P2 using linear motion."  | Yes                                           |
| A    | Linear move to P2             | "Linear Move 2P2"                | **No** — LLM appended incorrect gripper close |
| A    | Drive linearly to P2          | "Drive linearly to P2."          | Yes                                           |
| A    | Reach P2 via a straight path  | "Reach P2 via a straight path."  | Yes                                           |
| B    | Save this position as P3      | "Save this position as P3."      | Yes                                           |
| B    | Store current pose as P3      | "Store current pose as P3."      | Yes                                           |
| B    | Remember this position as P3  | "Remember this position as P3."  | Yes                                           |
| B    | Set P3 to current position    | "Set P3 to current position."    | Yes                                           |
| B    | Name this position P3         | "Name this position P3."         | Yes                                           |

**Failure analysis — trial A3:** The ASR garbled "Linear move to P2" into `"Linear Move 2P2"`. The LLM correctly extracted a `moveL to p2` command but also generated an incorrect `gripper close` step, producing a two-command sequence rather than a one-command sequence. The robot moved to P2 but executed an unrequested gripper close. No motion safety issue occurred. This represents a parser-level failure triggered by an abnormal ASR output.

### Test 2.3 — Invalid Input Rejection (criterion: 5/5 rejected before motion)

**Result: 5/5 · PASS**

| Input                           | Rejection site       | Reason logged                                                              |
|---------------------------------|----------------------|----------------------------------------------------------------------------|
| "Move to P99"                   | Backend validator    | `Unknown pose: 'p99'`                                                      |
| "Pick at somewhere"             | Parser               | `Vague or non-resolvable words such as 'somewhere' are NOT valid targets.` |
| "Hello robot"                   | Parser               | `No valid command detected. Please provide a specific robot command.`      |
| "Go to"                         | Pre-parser (dropped) | Transcript length below the 7-character minimum threshold; no LLM call dispatched and no backend request sent |
| "Move P1 and P2 simultaneously" | Parser               | `Impossible command: cannot move to two poses at the same time.`           |

No robot motion occurred for any of the five inputs. One observation: the incomplete command `"Go to"` (6 characters) was discarded by a hardcoded minimum-length check in the parser module before any LLM call was made. No rejection log entry was written for this input. The pass criterion is met, but a logged rejection message would provide clearer evidence of intentional handling.

### Test 2.4 — Sequential Session Stability (criterion: no crashes, correct state throughout)

**Result: 6/6 tasks completed · PASS**

All six benchmark tasks executed back-to-back in a single uninterrupted session without manual HOME resets between tasks. No crash, no timeout, no state error was recorded. The backend maintained connection and state throughout. The pipeline log shows no gap between task completions.

### Test 2.5 — Multi-Step Command Parsing (criterion: correct IR on all 3 trials)

**Result: 5/5 · PASS**

The five-step compound command `"Go to P1, wait 2 seconds, go to P2 linear, close gripper, go to home"` was issued five times. The protocol specifies three trials; five were conducted in practice. All five produced the following IR without error:

```
moveJ to p1 → wait 2.0 s → moveL to p2 → close gripper → moveJ to home
```

All five trials were classified as `Success`. Backend logs confirm the wait was handled by the message handler layer (logged as `Waiting for 2s`), not delegated to the robot controller. The pass criterion is met against the three-trial requirement; the two additional trials provide further confirmatory evidence.

---

## RQ3 — Modularity and Switch Cost

### Test 3.1 — Switch Cost Documentation

**Result: documented · PASS** *(descriptive — no threshold)*

| Metric                                | Value                                                                           |
|---------------------------------------|---------------------------------------------------------------------------------|
| Physical swap time                    | < 2 minutes                                                                     |
| Total inter-session gap (log-derived) | 2 min 11 s (11:42:54 → 11:45:05)                                                |
| Modified files                        | 0 (backend swap only — no code edited)                                          |
| Lines of code changed                 | 0                                                                               |
| Configuration steps                   | 5 (unplug Franka → move laptop → plug UR → start backend → switch robot in GUI) |

The upstream modules — `pipeline.py`, `ASR_module.py`, `parsing_module.py` — are identical across both vendor sessions, confirmed by the continuous frontend log. The IR format is identical across both backends. The Franka backend registered all three controllers (mock, franka, ur) at startup, as the UR controller can initialise on any platform regardless of whether the robot is connected. The UR backend registered only mock and ur — the Franka controller was not loaded because the backend detected the absence of the Linux-based Franka MoveIt stack on the host machine.

---
## End-to-End Timing
 
From the logging files, timing estimates can be extracted. Timing was measured from trial start ("New trial start") to execution complete ("Execution: Backend executed command successfully"). Three trials are excluded from these figures: the Franka MoveIt stack initialisation on the first trial (18 s, one-time), the UR cold-start activation on the first UR command (37 s, one-time), and the backend-rejected "Move to P99" trial (exec = 0 s; no motion executed). All 122 remaining trials are included. Timestamps are taken from the frontend log at one-second resolution.
 
The pipeline portion — ASR transcription plus LLM parsing — took an average of 1.0 s and 3.7 s respectively, totalling approximately 4.6 s regardless of command type. Robot execution time is the main source of variation and depends on the number of motion steps and the platform.
 
| Command type       | N  | ASR avg | LLM avg | Exec avg | Total avg | Total range |
|--------------------|----|---------|---------|----------|-----------|-------------|
| Move (joint)       | 36 | 1.0 s   | 3.2 s   | 1.6 s    | 7.3 s     | 6–8 s       |
| Move (linear)      | 16 | 1.0 s   | 3.3 s   | 1.8 s    | 8.7 s     | 7–11 s      |
| Gripper            | 21 | 1.0 s   | 3.1 s   | 2.1 s    | 7.8 s     | 6–9 s       |
| Teach pose         | 16 | 1.0 s   | 3.3 s   | 0.1 s    | 7.5 s     | 7–9 s       |
| Two-step sequence  | 5  | 1.0 s   | 4.0 s   | 3.2 s    | 11.2 s    | 11–12 s     |
| Pick & place       | 11 | 1.0 s   | 5.1 s   | 7.8 s    | 17.7 s    | 16–20 s     |
| Pick + offset      | 11 | 1.2 s   | 5.2 s   | 7.0 s    | 19.5 s    | 17–22 s     |
| Multi-step (5-cmd) | 5  | 1.4 s   | 5.0 s   | 7.4 s    | 21.2 s    | 21–22 s     |
 
Pick-and-place tasks split by platform: Franka averaged 16.5 s (range 16–17 s); UR10e averaged 19.2 s (range 19–20 s). The difference reflects robot motion speed rather than any pipeline difference — the pipeline contribution is identical across platforms. The UR Gripper commands may be slower than Franka due to the chosen adapter implementation using the On Robot RG6 gripper load script workaround. 

The LLM parsing time scales with command complexity: 3.1–3.3 s for single-step commands, rising to 4.0–5.2 s for two- to five-step sequences. ASR time remains stable across all command types at approximately 1.0 s. Note: ASR times are derived from frontend logs at one-second resolution; sub-second precision would require millisecond-level timestamping to capture the true transcription latency accurately.

---
## Cross-Session Observations

### ASR performance

ASR confidence ranged from 0.85 to 0.99 across all trials. Six inputs were garbled by the ASR. Five were recovered correctly by the LLM parser (examples: `"Close scraper"` → close gripper, `"Close Ripper"` → close gripper, `"and go to P1"` → moveJ p1, `"Teach the cover position as P3"` → teach p3, `"Picket P1 and place at offset…"` → correct pick-place). One garble was not recovered (test 2.2 trial A3, documented above).

### IR non-determinism on task 5

The command `"Pick at P1 and place at P2"` alternated between two structurally different but functionally equivalent IR forms across trials:

- `move to named_pose p2`
- `move to offset_from_pose p2 [x=0, y=0, z=0]`

Across all eleven executions of this command — five Franka benchmark trials, five UR10e benchmark trials, and one session-stability trial — nine used the offset form and two used the named form. The named form appeared once in the Franka benchmark (trial 2, at 11:31:19) and once in the session-stability run (at 11:40:22); all UR10e trials used the offset form. Execution outcomes were identical in all cases. The non-determinism originates in the LLM parser and does not affect success rate, but it means the IR was not fully stable for identical inputs of this specific command.

### Known bug — duplicate command on UR session initialisation

The UR backend log shows a second `close gripper` command received at 11:45:55, immediately after the first one completed at the same timestamp. This command has no corresponding frontend trial — the frontend log contains only one dispatch for this period. The duplicate is a known issue in the UR backend: on first connection, the initialisation sequence can cause the first command to be queued and executed twice. The behaviour has been observed in prior sessions. It does not affect any reported metric — no additional trial was recorded, no incorrect state resulted, and the gripper was already closed when the duplicate fired. The issue is confined to the first command of a new UR session.

### Protocol deviation — UR task 2, trial 2

No HOME reset was performed between trial 1 and trial 2 of task 2 on the UR10e. The backend log shows two consecutive `moveL to p2` commands with no intervening HOME movement. Trials 3–5 followed the reset protocol correctly. Both affected trials succeeded; visual confirmation was noted at the time.

---

## Verdict

The framework meets all criteria defined in the evaluation protocol. End-to-end success rate is 100% on both platforms, exceeding the 80% pass threshold. The single IR error in test 2.2 did not affect execution safety and the test still passes. Modularity is demonstrated by a sub-three-minute backend swap with zero code changes. No crashes or state errors were recorded across either vendor session. ASR and LLM Parser robustness is good, yet not perfect — ASR garbles occurred but were mostly recovered by the parser, and the one parsing failure did not cause a test failure. The framework is therefore deemed successful against the defined criteria, with some minor areas for improvement identified in ASR robustness and IR stability..