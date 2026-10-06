"""Typed inputs for the synthetic-only conversation harness."""

from enum import StrEnum
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_LENGTH: Final[int] = 400
MAX_CLAIMED_CATEGORIES: Final[int] = 4
MAX_HANDOFF_MARKER_LENGTH: Final[int] = 64
OPAQUE_HANDOFF_MARKER_PATTERN: Final[str] = r"^CASE-[A-Z0-9-]{1,59}$"


class ConversationMode(StrEnum):
    """Describes when the disclosed simulator takes control."""

    FROM_START = "from_start"
    MID_CALL_HANDOFF = "mid_call_handoff"


class KnowledgeCategory(StrEnum):
    """Non-sensitive categories the synthetic actor can claim to know."""

    NAME = "name"
    CONTACT = "contact"
    ADDRESS = "address"
    FINANCIAL = "financial"


class IncomingTurn(BaseModel):
    """Validated boundary object that never promises a real data value."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    mode: ConversationMode
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    claimed_categories: tuple[KnowledgeCategory, ...] = Field(
        min_length=1,
        max_length=MAX_CLAIMED_CATEGORIES,
    )
    handoff_marker: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_HANDOFF_MARKER_LENGTH,
        pattern=OPAQUE_HANDOFF_MARKER_PATTERN,
    )
