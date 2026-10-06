"""A disclosed, deterministic substitute for a live social-engineering model."""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Final, assert_never

from voicefishing.contracts import ConversationMode, IncomingTurn, KnowledgeCategory
from voicefishing.safety import find_sensitive_input

_DISCLOSED_MESSAGE: Final[str] = (
    "[합성 훈련] 실제 개인정보를 제공하지 마세요. 이 턴은 상대가 안다고 "
    "주장한 정보의 범주만 기록하며, 값은 합성 토큰으로만 다룹니다."
)


class BlockReason(StrEnum):
    """Why the safety harness declined a supplied turn."""

    SENSITIVE_INPUT = "sensitive_input"


@dataclass(frozen=True, slots=True)
class SimulatedTurn:
    """Safe output containing category-level claims and no actual identifier."""

    mode: ConversationMode
    message: str
    claimed_categories: tuple[KnowledgeCategory, ...]
    handoff_marker: str | None
    trace_digest: str


@dataclass(frozen=True, slots=True)
class BlockedTurn:
    """A fail-closed result that excludes raw input from the output surface."""

    reason: BlockReason


type SimulationResult = SimulatedTurn | BlockedTurn


class SafeScenarioSimulator:
    """Generate only disclosed synthetic turns for bait-bot evaluation."""

    @staticmethod
    def reply(incoming: IncomingTurn) -> SimulationResult:
        """Return a synthetic turn or block a message that looks like live PII."""
        if find_sensitive_input(incoming.message, incoming.handoff_marker) is not None:
            return BlockedTurn(reason=BlockReason.SENSITIVE_INPUT)

        match incoming.mode:
            case ConversationMode.FROM_START:
                return SafeScenarioSimulator._simulate(incoming, handoff_marker=None)
            case ConversationMode.MID_CALL_HANDOFF:
                return SafeScenarioSimulator._simulate(
                    incoming,
                    handoff_marker=incoming.handoff_marker,
                )
            case _:
                assert_never(incoming.mode)

    @staticmethod
    def _simulate(
        incoming: IncomingTurn,
        handoff_marker: str | None,
    ) -> SimulatedTurn:
        """Create an auditable turn without retaining a readable transcript."""
        digest_material = "\x1f".join(
            (
                incoming.mode.value,
                ",".join(category.value for category in incoming.claimed_categories),
            ),
        )
        trace_digest = sha256(digest_material.encode("utf-8")).hexdigest()
        return SimulatedTurn(
            mode=incoming.mode,
            message=_DISCLOSED_MESSAGE,
            claimed_categories=incoming.claimed_categories,
            handoff_marker=handoff_marker,
            trace_digest=trace_digest,
        )
