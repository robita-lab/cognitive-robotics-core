# llm_dialog_manager

Local-first dialog manager for UDITO. Subscribes to `stt_topic`, classifies the
intent, sends the turn to either the on-robot local LLM tier or the GPU server
tier, and forwards the reply to the `com_act_server` service.

This package is the **Tier-1 (on-robot)** half of the two-tier architecture
described in `udito/server-side/ARCHITECTURE.md`. It replaces
`watson_dialog_manager` for new work; Watson stays in tree as legacy.

## Components

| Module | Role | ROS? |
|---|---|---|
| `router.py` | Pure-Python intent classifier (regex/keyword). Decides `local` vs `server`. | no |
| `llm_client.py` | Sync `httpx` client for the FastAPI server's `/v1/chat`. | no |
| `node.py` | rclpy node: STT → router → HTTP (worker thread) → ComAct service. | yes |
| `cli.py` | CLI harness — exercises router + client **without** ROS or the robot. | no |
| `mock_comact.py` | Stub `com_act_server` that logs each request and replies ACK. | yes |

## Dependencies

- `rclpy`, `body_interfaces` (from this repo)
- `httpx` — install with `pip install httpx` or via rosdep (`python3-httpx`).

## Running

### Build

```bash
cd udito/ros2_ws
colcon build --packages-select llm_dialog_manager
source install/setup.bash
```

### Production(-ish) — real robot

Assumes the server-side Docker stack is up on a LAN host at `http://gpu.local:8080`
and the existing `base.py` launch is running (ReSpeaker + ComAct).

```bash
ros2 launch llm_dialog_manager llm_dialog.launch.py \
    server_url:=http://gpu.local:8080 \
    local_url:=http://localhost:8080
```

### Robot-free ROS integration test

Uses a mock ComAct service so no head / TTS hardware is needed:

```bash
# terminal 1 — FastAPI server
cd udito/server-side && docker compose up

# terminal 2 — dialog manager + mock ComAct
ros2 launch llm_dialog_manager llm_dialog_test.launch.py \
    server_url:=http://localhost:8080

# terminal 3 — inject a turn
ros2 topic pub --once /stt_topic body_interfaces/msg/Speech2Text \
    '{text: "hola", confidence: 0.9}'

ros2 topic pub --once /stt_topic body_interfaces/msg/Speech2Text \
    '{text: "¿qué es un robot social?", confidence: 0.9}'
```

Watch the mock ComAct logs in terminal 2 — each turn logs the routed tier,
LLM latency, and the ACK request that would drive head+TTS on the real robot.

### Robot-free **non-ROS** CLI

The fastest inner loop when iterating on the router or the server. No ROS,
no robot, no hardware.

```bash
cd udito/ros2_ws/src/llm_dialog_manager
pip install httpx
python -m llm_dialog_manager.cli \
    --server-url http://localhost:8080 \
    --local-url  http://localhost:8080
```

Interactive:

```
> Hola
[intent=greeting tier=local latency=180ms model=qwen2.5:3b-instruct]
Hola, ¿qué tal estás?

> ¿Quién fundó ROBITA-LAB?
[intent=factual_query tier=server latency=410ms model=qwen2.5:3b-instruct]
No tengo esa información concreta...

> exit
```

One-shot (useful in scripts):

```bash
python -m llm_dialog_manager.cli --once "Hola UDITO"
```

### Unit tests (router only — no ROS, no server required)

```bash
cd udito/ros2_ws/src/llm_dialog_manager
pytest test/test_router.py
```

## ROS parameters

| Parameter | Default | Purpose |
|---|---|---|
| `server_url` | `http://localhost:8080` | Server tier base URL. |
| `local_url` | `http://localhost:8080` | Local tier base URL. |
| `conversation_id` | `udito-session-default` | Keys server-side memory. |
| `stt_confidence_threshold` | `0.6` | Below this, the node asks the user to repeat. |
| `default_gesture` | `NEUTRAL` | Gesture label sent with every reply. |
| `default_duration` | `7` | `data` field of `ComActMsg`. |
| `response_max_tokens` | `80` | Per-turn generation cap. |

## Routing rules (v1)

First-match-wins, implemented in `router.py`:

| Rule | Tier | Intent |
|---|---|---|
| Empty | local | `empty` |
| Exact greeting (`hola`, `buenos días`, …) | local | `greeting` |
| Exact ack (`sí`, `vale`, `gracias`, …) | local | `acknowledgement` |
| Backchannel (`mm`, `ya`, …) | local | `backchannel` |
| Starts with emotion prefix (`estoy`, `me siento`, …) | local | `emotion_expression` |
| Starts with factual prefix (`qué`, `quién`, `cómo`, `dime`, …) | server | `factual_query` |
| > 8 words | server | `long_utterance` |
| Previous turn went to server | server | `multi_turn_continuation` |
| Default | server | `unknown` |

v2 will replace this with a small classifier once there are transcripts worth
training on.
