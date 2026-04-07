# Evaluation Protocol
## Speech-to-Code Generation for Collaborative Robots

This protocol defines the test procedures used to evaluate the speech-to-code framework for the thesis. Tests are grouped by research question. Each entry states the objective, procedure, and pass criterion.

Every trial is documented through three sources. The parser logging option captures the raw LLM output as a JSON file. The audio recording option saves the microphone input for that trial as a `.wav` file. The frontend and backend logs capture the full system activity across the session, including command dispatch, validation results, execution status, and timing. All logs are written to the `logs/` folders.

Each trial receives one of three outcome classifications:
- `Success` — the robot reached the expected final state
- `Failed` — the framework interpreted the command correctly but execution did not complete
- `Rejected` — the framework refused the command before any robot motion began

All tests are conducted on physical robots in the laboratory setup described in the thesis (section 3.5).

---

## Setup

Before any test is executed, the following preconditions must be satisfied:

- Connect the frontend to the target robot backend and confirm the connection is active.
- Define and store three reference poses on the robot: `HOME`, `P1`, and `P2`, each as a full 6D pose comprising position and orientation.
  - `HOME` serves as the default start and return position.
  - `P1` and `P2` define the primary task targets used across the benchmark.
- Verify that all three poses are reachable and free of collision within the workspace before proceeding.
- Enable parser logging and audio recording for all trials.

Before starting each new test, return the robot to `HOME` to ensure a defined starting state. This can be done by issuing `"Go to HOME"` via the interface.

---

## RQ1 — End-to-End Task Success

### Test 1.1 — Baseline Success Rate (Franka Panda)

**Objective:** Measure end-to-end task success rate across the full benchmark task set on the Franka Panda.

**Procedure:** Execute each benchmark task five times before moving to the next. Complete all five trials of task 1, then all five trials of task 2, and so on through task 6, for a total of 30 trials. Issue each command by voice via the push-to-talk interface. Do not intervene between trials. For tasks 1 and 2, return the robot to HOME before each trial to ensure movement is observable. For task 3, close the gripper before each trial to ensure the open command produces a visible state change. For tasks 4, 5, and 6, no reset is required between trials. Note that task 4 will overwrite any previously stored `P3` automatically. Record the outcome of every execution.

1. `"Go to P1"`
2. `"Go linear to P2"`
3. `"Open gripper"`
4. `"Teach current position as P3"`
5. `"Pick at P1 and place at P2"`
6. `"Pick at P1 and place at offset x=80, y=50"`

**Pass criterion:** At least 24 of 30 trials classified as `Success` (≥80%). A framework that succeeds 4 out of 5 times on average demonstrates sufficient reliability for a controlled laboratory setting.

---

### Test 1.2 — Baseline Success Rate (UR10e)

**Objective:** Confirm that the framework achieves equivalent task success on the UR10e after backend swap.

**Procedure:** Swap the execution backend to the UR adapter. Repeat the identical procedure from Test 1.1 on the UR10e.

**Pass criterion:** At least 24 of 30 trials classified as `Success` (≥80%), consistent with the threshold applied in Test 1.1.

---

## RQ2 — Input Variability and Stability

### Test 2.1 — Repeatability

**Objective:** Verify that the framework produces consistent output for identical input across repeated trials.

**Procedure:** Issue the command `"Go to P1, then go to HOME"` five times consecutively without modifying any system parameter between trials.

**Pass criterion:** Identical IR generated on all five trials. All five trials classified as `Success`.

---

### Test 2.2 — Paraphrase Robustness

**Objective:** Assess whether the framework correctly interprets natural rephrasings of benchmark commands.

**Procedure:** Apply five distinct natural language rephrasings to each of the following two tasks, yielding ten trials in total. Issue all variants by voice and record the generated IR for each.

**Task A** — Benchmark task 2, linear motion to P2. Example rephrasings:
- `"Move to P2 in a straight line"`
- `"Go to P2 using linear motion"`
- `"Linear move to P2"`
- `"Drive linearly to P2"`
- `"Reach P2 via a straight path"`

**Task B** — Benchmark task 4, teaching the current pose. Note that issuing this command during the test will overwrite any previously stored `P3` — this is expected and does not constitute a failure. Example rephrasings:
- `"Save this position as P3"`
- `"Store current pose as P3"`
- `"Remember this position as P3"`
- `"Set P3 to current position"`
- `"Name this position P3"`

**Pass criterion:** At least 8 of 10 trials produce the correct IR (≥80%). A framework that interprets natural rephrasings correctly 8 out of 10 times demonstrates sufficient robustness for practical use.

---

### Test 2.3 — Invalid Input Rejection

**Objective:** Confirm that the framework safely rejects commands it cannot execute.

**Procedure:** Issue the following five commands in sequence. Do not intervene between inputs.

1. `"Move to P99"` — nonexistent pose
2. `"Pick at somewhere"` — ambiguous target
3. `"Hello robot"` — nonsense utterance
4. `"Go to"` — incomplete command
5. `"Move P1 and P2 simultaneously"` — unsafe request

**Pass criterion:** All five inputs classified as `Rejected` before any robot motion begins.

---

### Test 2.4 — Sequential Session Stability

**Objective:** Verify that the framework maintains correct state across a full uninterrupted session.

**Procedure:** Note: the standard between-test HOME reset defined in the Setup section is suspended for this test only. Execute all six benchmark tasks from Test 1.1 back-to-back in a single run without manual intervention or system restart between tasks. Do not return to `HOME` manually between tasks — the framework is expected to manage state transitions itself.

**Pass criterion:** No crashes, no state errors, and correct robot state maintained throughout the entire session.

---

### Test 2.5 — Multi-Step Command Parsing

**Objective:** Assess whether the parser correctly handles compound instructions issued in a single utterance.

**Procedure:** Issue the following command three times: `"Go to P1, wait 2 seconds, go to P2 linear, close gripper, go to HOME"`. Record the generated IR for each trial.

**Pass criterion:** Correct IR generated for every step in the sequence on all three trials.

---

## RQ3 — Modularity and Switch Cost

### Test 3.1 — Switch Cost Documentation

**Objective:** Quantify the effort required to switch between vendor backends.

**Procedure:** Perform the full backend swap from Franka to UR. Log all implementation activity in real time. Record the following metrics:
- Total implementation time
- Number of modified files
- Lines of code changed
- Configuration steps required

**Pass criterion:** All four metrics recorded and reported. Upstream modules confirmed unchanged. This test produces descriptive data only — no threshold is defined for acceptable switch cost, as the research question asks to quantify rather than evaluate against a target.
