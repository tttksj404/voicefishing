import pytest
from pydantic import ValidationError

from voicefishing.contracts import ConversationMode, IncomingTurn, KnowledgeCategory
from voicefishing.simulator import BlockedTurn, SafeScenarioSimulator, SimulatedTurn


def test_blocks_a_live_phone_number_when_starting_a_synthetic_session() -> None:
    # Given: a message that contains a real-looking phone number
    simulator = SafeScenarioSimulator()
    incoming = IncomingTurn(
        mode=ConversationMode.FROM_START,
        message="제 번호는 010-1234-5678입니다.",
        claimed_categories=(KnowledgeCategory.CONTACT,),
    )

    # When: a synthetic session processes the message
    result = simulator.reply(incoming)

    # Then: the live value is blocked instead of entering the transcript
    assert isinstance(result, BlockedTurn)
    assert result.reason == "sensitive_input"


def test_mid_call_handoff_preserves_only_an_opaque_case_marker() -> None:
    # Given: a synthetic handoff carrying an opaque marker, not personal data
    simulator = SafeScenarioSimulator()
    incoming = IncomingTurn(
        mode=ConversationMode.MID_CALL_HANDOFF,
        message="이전 대화의 확인을 이어가겠습니다.",
        claimed_categories=(KnowledgeCategory.NAME, KnowledgeCategory.ADDRESS),
        handoff_marker="CASE-ALPHA-7",
    )

    # When: the simulator takes over the conversation
    result = simulator.reply(incoming)

    # Then: it keeps the marker and reports categories without a real value
    assert isinstance(result, SimulatedTurn)
    assert result.handoff_marker == "CASE-ALPHA-7"
    assert result.claimed_categories == (
        KnowledgeCategory.NAME,
        KnowledgeCategory.ADDRESS,
    )
    assert "개인정보를 제공하지 마세요" in result.message


def test_generated_turn_never_requests_private_or_financial_values() -> None:
    # Given: a safe synthetic knowledge-check request
    simulator = SafeScenarioSimulator()
    incoming = IncomingTurn(
        mode=ConversationMode.FROM_START,
        message="합성 훈련을 시작합니다.",
        claimed_categories=(KnowledgeCategory.CONTACT, KnowledgeCategory.FINANCIAL),
    )

    # When: the simulator produces its next turn
    result = simulator.reply(incoming)

    # Then: the turn remains disclosure-first and contains no value request
    assert isinstance(result, SimulatedTurn)
    assert "합성 훈련" in result.message
    assert "개인정보를 제공하지 마세요" in result.message
    assert "계좌번호" not in result.message
    assert "인증번호" not in result.message


def test_audit_digest_does_not_depend_on_the_input_transcript() -> None:
    # Given: two different safe utterances with the same category-level contract
    simulator = SafeScenarioSimulator()
    first = IncomingTurn(
        mode=ConversationMode.FROM_START,
        message="first synthetic phrase",
        claimed_categories=(KnowledgeCategory.CONTACT,),
    )
    second = IncomingTurn(
        mode=ConversationMode.FROM_START,
        message="second synthetic phrase",
        claimed_categories=(KnowledgeCategory.CONTACT,),
    )

    # When: both turns are recorded for audit
    first_result = simulator.reply(first)
    second_result = simulator.reply(second)

    # Then: the digest cannot encode either readable input transcript
    assert isinstance(first_result, SimulatedTurn)
    assert isinstance(second_result, SimulatedTurn)
    assert first_result.trace_digest == second_result.trace_digest


def test_handoff_marker_rejects_text_that_is_not_an_opaque_case_token() -> None:
    # Given/When: a handoff requests to forward an arbitrary readable marker
    with pytest.raises(ValidationError):
        _ = IncomingTurn(
            mode=ConversationMode.MID_CALL_HANDOFF,
            message="continue synthetic context",
            claimed_categories=(KnowledgeCategory.NAME,),
            handoff_marker="plain-readable-marker",
        )
