"""AgentRuntime — core agent loop with system prompt assembly."""

from __future__ import annotations

from dataclasses import dataclass, field

from vasini.llm.providers import LLMResponse, Message
from vasini.llm.router import LLMRouter
from vasini.models import AgentConfig
from vasini.runtime.state import TaskState, TaskStateMachine


@dataclass
class AgentResult:
    """Result returned after an agent run completes."""

    output: str
    state: TaskState
    steps_taken: int = 0
    messages: list[Message] = field(default_factory=list)


class AgentRuntime:
    """Executes the agent loop: LLM call -> tool calls -> repeat."""

    def __init__(self, config: AgentConfig, llm_router: LLMRouter) -> None:
        self.config = config
        self.llm_router = llm_router

    def _build_system_prompt(self) -> str:
        """Assemble system prompt from Soul + Role + Guardrails layers."""
        parts: list[str] = []

        # Soul layer
        soul = self.config.soul
        if soul.tone.default:
            parts.append(f"Tone: {soul.tone.default}")
        if soul.principles:
            principles_text = "; ".join(soul.principles)
            parts.append(f"Principles: {principles_text}")

        # Role layer
        role = self.config.role
        if role.title:
            parts.append(f"Role: {role.title}")
        if role.domain:
            parts.append(f"Domain: {role.domain}")
        if role.goal.primary:
            parts.append(f"Goal: {role.goal.primary}")
        if role.backstory:
            parts.append(f"Backstory: {role.backstory}")
        if role.limitations:
            limitations_text = "; ".join(role.limitations)
            parts.append(f"Limitations: {limitations_text}")

        # Guardrails layer
        guardrails = self.config.guardrails
        behavioral = guardrails.behavioral
        if behavioral.prohibited_actions:
            prohibited = "; ".join(behavioral.prohibited_actions)
            parts.append(f"Prohibited actions: {prohibited}")
        if behavioral.required_disclaimers:
            disclaimers = "; ".join(behavioral.required_disclaimers)
            parts.append(f"Required disclaimers: {disclaimers}")

        return "\n".join(parts)

    async def run(self, user_input: str) -> AgentResult:
        """Execute the agent loop for the given user input."""
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)

        system_prompt = self._build_system_prompt()

        messages: list[Message] = [Message(role="user", content=user_input)]

        max_steps = self.config.guardrails.behavioral.max_autonomous_steps
        steps_taken = 0

        for _ in range(max_steps + 1):
            response: LLMResponse = await self.llm_router.chat(
                messages=messages,
                system=system_prompt,
            )

            assistant_msg = Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls if response.tool_calls else None,
            )
            messages.append(assistant_msg)

            if not response.tool_calls:
                # No tool calls — we are done
                sm.transition(TaskState.DONE)
                return AgentResult(
                    output=response.content,
                    state=sm.state,
                    steps_taken=steps_taken,
                    messages=messages,
                )

            # Process tool calls with stub results
            steps_taken += 1
            for tc in response.tool_calls:
                tool_msg = Message(
                    role="tool",
                    content="[tool result stub]",
                    tool_call_id=tc.get("id", ""),
                )
                messages.append(tool_msg)

        # Exceeded max autonomous steps
        sm.transition(TaskState.DONE)
        return AgentResult(
            output=messages[-1].content if messages else "",
            state=sm.state,
            steps_taken=steps_taken,
            messages=messages,
        )
