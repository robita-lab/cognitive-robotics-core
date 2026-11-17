"""Robot-free local test harness.

Exercises router + LLMClient against a running FastAPI server without needing
ROS, the robot, or any audio hardware. Useful for:

  - Validating the server is reachable and responding sensibly.
  - Iterating on the router's classification rules.
  - Sanity-checking Spanish persona / model output.

Usage:
    python -m llm_dialog_manager.cli \\
        --server-url http://localhost:8080 \\
        --local-url  http://localhost:8080

Interactive mode by default; --once consumes a single utterance from argv.
"""

from __future__ import annotations

import argparse
import sys
import uuid

from llm_dialog_manager.llm_client import LLMClient
from llm_dialog_manager.router import route


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--server-url", default="http://localhost:8080")
    p.add_argument("--local-url", default="http://localhost:8080")
    p.add_argument("--conversation-id", default=None)
    p.add_argument("--persona", default="default")
    p.add_argument("--max-tokens", type=int, default=80)
    p.add_argument(
        "--once",
        metavar="TEXT",
        default=None,
        help="one-shot mode: classify + send a single utterance and exit",
    )
    return p.parse_args(argv)


def _one_turn(
    user_text: str,
    clients: dict[str, LLMClient],
    conversation_id: str,
    last,
    persona: str,
    max_tokens: int,
):
    decision = route(user_text, last_decision=last)
    try:
        reply = clients[decision.tier].chat(
            conversation_id,
            user_text,
            persona=persona,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            "[intent=%s tier=%s ERROR] %s" % (decision.intent, decision.tier, exc),
            file=sys.stderr,
        )
        return decision
    print(
        "[intent=%s tier=%s latency=%dms model=%s]"
        % (decision.intent, decision.tier, reply.latency_ms, reply.model or "?")
    )
    print(reply.reply)
    print()
    return decision


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    conversation_id = args.conversation_id or "cli-%s" % uuid.uuid4().hex[:8]
    clients: dict[str, LLMClient] = {
        "server": LLMClient(args.server_url),
        "local": LLMClient(args.local_url),
    }

    for tier, client in clients.items():
        ok = client.healthy()
        marker = "ok" if ok else "UNREACHABLE"
        print("tier=%s %s -> %s" % (tier, args.server_url if tier == "server" else args.local_url, marker))

    print("conversation_id=%s persona=%s max_tokens=%d" % (conversation_id, args.persona, args.max_tokens))
    print()

    if args.once is not None:
        _one_turn(args.once, clients, conversation_id, None, args.persona, args.max_tokens)
        for c in clients.values():
            c.close()
        return

    print('type "exit" or ctrl-d to stop.')
    last = None
    try:
        while True:
            try:
                user = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if user.lower() in {"exit", "quit"}:
                break
            if not user:
                continue
            last = _one_turn(user, clients, conversation_id, last, args.persona, args.max_tokens)
    finally:
        for c in clients.values():
            c.close()


if __name__ == "__main__":
    main()
