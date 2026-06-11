"""
Single-function LLM interface.

Swap provider by commenting/uncommenting the block below.
The signature  chat(messages, json_mode)  never changes.
"""

from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL

_groq = Groq(api_key=GROQ_API_KEY)


def chat(messages: list[dict], json_mode: bool = False) -> str:
    """Send a message list to the active LLM and return the reply as a string."""
    kwargs: dict = dict(
        model=GROQ_MODEL,
        temperature=0.1,
        messages=messages,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = _groq.chat.completions.create(**kwargs)
    return resp.choices[0].message.content


# ── Claude swap-in (uncomment + comment the Groq block above) ─────────────────
# from anthropic import Anthropic
# from app.config import ANTHROPIC_API_KEY
#
# _claude = Anthropic(api_key=ANTHROPIC_API_KEY)
#
# def chat(messages: list[dict], json_mode: bool = False) -> str:
#     system = next((m["content"] for m in messages if m["role"] == "system"), "")
#     convo  = [m for m in messages if m["role"] != "system"]
#     resp = _claude.messages.create(
#         model="claude-sonnet-4-5",
#         system=system,
#         messages=convo,
#         max_tokens=1024,
#         temperature=0.1,
#     )
#     return resp.content[0].text
