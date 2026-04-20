# UDITO — Server-Side LLM Component

Standalone service that exposes UDITO's LLM capabilities as a local/remote API, so that the robot runtime (ROS nodes, standalone demos) consumes dialogue generation over the network instead of embedding provider SDKs in-process.

## Why split LLM out

- **Secrets out of robot code.** API keys and provider credentials live only on the server, loaded from env/secret storage. The robot holds no keys.
- **Provider swapping without touching robot code.** Change from IBM watsonx.ai to another backend (OpenAI, Anthropic, local models, …) by updating the server; the robot's contract stays the same.
- **Non-blocking dialogue.** The robot never blocks inside a provider SDK — it makes an HTTP/WS call and can time out, retry, or fall back cleanly.
- **Conversation memory.** Multi-turn context lives on the server, not scattered across ROS nodes.
- **Shared by more than one consumer.** Future tooling (dashboards, evaluation harnesses) can hit the same API.

## Scope (initial)

- Single chat-style endpoint: given an utterance (+ optional conversation id), return a reply.
- Configurable provider and model via env.
- Rolling conversation memory keyed by conversation id.
- Health check.

## Not in scope (yet)

- Streaming responses, tool/function calling, TTS/STT, authentication, deployment manifests.

## Status

Skeleton only — framework, layout, and API surface still to be decided. See the parent `docs/01-repo-analysis.md` §14 and §16 for the broader context that motivated this component.
