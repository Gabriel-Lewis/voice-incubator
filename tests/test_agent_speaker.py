"""Telling an LLM agent who is speaking (voice_incubator/agent.py ``told``)."""

from __future__ import annotations

import asyncio
from typing import Any

from voice_incubator.agent import HOME_ASSISTANT_AGENT, Agent


class Hass:
    """Home Assistant's conversation/process, as far as an agent asks it."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def call(self, message: dict[str, Any], timeout: float | None = None) -> Any:
        self.sent.append(message)
        return {"response": {"response_type": "query_answer", "speech": {"plain": {"speech": "Hi."}}}}


def asked(agent: Agent, speaker: str | None) -> tuple[str, Any]:
    reply = asyncio.run(agent.ask("kitchen", "what's on my calendar", speaker=speaker))
    return agent.hass.sent[-1]["text"], reply


def test_off_by_default():
    agent = Agent(Hass(), "conversation.chatty")
    text, reply = asked(agent, "Anna")
    assert text == "what's on my calendar" and reply.speaker is None


def test_told_who_when_on_and_known():
    agent = Agent(Hass(), "conversation.chatty")
    agent.configure("conversation.chatty", 300, tell_speaker=True)
    text, reply = asked(agent, "Anna")
    assert text == "[Speaker:Anna] what's on my calendar"
    assert reply.speaker == "Anna" and reply.to_json()["speaker"] == "Anna"
    # Nobody known: the sentence as it was.
    text, reply = asked(agent, None)
    assert text == "what's on my calendar" and reply.speaker is None


def test_never_home_assistants_own_agent():
    # Its sentences are matched as said: a prefix would break every one.
    agent = Agent(Hass(), HOME_ASSISTANT_AGENT, tell_speaker=True)
    text, reply = asked(agent, "Anna")
    assert text == "what's on my calendar" and reply.speaker is None
