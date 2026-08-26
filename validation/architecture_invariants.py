from enum import Enum


class Call(str, Enum):
    USER_ACTIVE = "USER_ACTIVE"
    HANDOFF_PENDING = "HANDOFF_PENDING"
    BAIT_ACTIVE = "BAIT_ACTIVE"
    AUTO_REJECTED = "AUTO_REJECTED"
    ENDED = "ENDED"


class Scam(str, Enum):
    UNCLASSIFIED = "UNCLASSIFIED"
    NORMAL = "NORMAL"
    SUSPECTED = "SUSPECTED"
    PHISHING_CONFIRMED = "PHISHING_CONFIRMED"


class Safety(str, Enum):
    PASS = "PASS"
    DEFEND = "DEFEND"


def actions(call: Call, scam: Scam, safety: Safety | None = None) -> set[str]:
    out: set[str] = set()
    if call in {Call.ENDED, Call.AUTO_REJECTED}:
        return out

    # 보이스피싱 판단은 통화 주체와 독립이며, 확정 후에만 탐지 RAG를 중단한다.
    if scam != Scam.PHISHING_CONFIRMED:
        out |= {"scenario_rag_retrieve", "scenario_judge"}

    if call == Call.USER_ACTIVE:
        out |= {"store_turn", "show_analysis"}
        if safety == Safety.DEFEND:
            out |= {"log_attack_event"}
        return out

    if call == Call.HANDOFF_PENDING:
        return out | {"freeze_turn_boundary", "build_context_snapshot"}

    if call == Call.BAIT_ACTIVE:
        out |= {"store_turn", "rule_safety"}
        if safety == Safety.PASS:
            out |= {"extractor", "responder", "tts"}
            if scam == Scam.PHISHING_CONFIRMED:
                out |= {"update_confirmed_event", "check_report_readiness"}
            else:
                out |= {"update_candidate_event"}
        elif safety == Safety.DEFEND:
            out |= {
                "defensive_responder",
                "tts",
                "log_attack_event",
                "adversarial_rag_ingest",
            }
    return out


def handoff(call: Call, scam: Scam) -> tuple[Call, Scam]:
    assert call == Call.USER_ACTIVE
    return Call.HANDOFF_PENDING, scam


checks: list[str] = []


def check(name: str, condition: bool) -> None:
    assert condition, name
    checks.append(name)


check("mode2_no_ai_calls", actions(Call.AUTO_REJECTED, Scam.UNCLASSIFIED) == set())

a = actions(Call.BAIT_ACTIVE, Scam.SUSPECTED, Safety.PASS)
check(
    "mode3_bait_before_confirmed",
    {"scenario_rag_retrieve", "scenario_judge", "extractor", "responder", "tts"} <= a,
)
check("mode3_candidate_not_report", "update_candidate_event" in a and "check_report_readiness" not in a)

a = actions(Call.BAIT_ACTIVE, Scam.PHISHING_CONFIRMED, Safety.PASS)
check("confirmed_bypasses_scenario_rag", "scenario_rag_retrieve" not in a and "scenario_judge" not in a)
check("confirmed_runtime_continues", {"extractor", "responder", "tts", "check_report_readiness"} <= a)

for state in Scam:
    new_call, new_scam = handoff(Call.USER_ACTIVE, state)
    check(
        f"handoff_preserves_{state.value}",
        new_call == Call.HANDOFF_PENDING and new_scam == state,
    )

for state in Scam:
    for safety in Safety:
        current = actions(Call.USER_ACTIVE, state, safety)
        check(
            f"user_active_no_bot_tts_{state.value}_{safety.value}",
            "tts" not in current
            and "responder" not in current
            and "defensive_responder" not in current,
        )

for state in Scam:
    passed = actions(Call.BAIT_ACTIVE, state, Safety.PASS)
    defended = actions(Call.BAIT_ACTIVE, state, Safety.DEFEND)
    check(
        f"pass_routes_separate_{state.value}",
        {"extractor", "responder"} <= passed and "defensive_responder" not in passed,
    )
    check(
        f"defend_routes_separate_{state.value}",
        "defensive_responder" in defended
        and "extractor" not in defended
        and "responder" not in defended,
    )
    check(
        f"defend_ingests_attack_rag_{state.value}",
        "adversarial_rag_ingest" in defended,
    )

for state in [Scam.UNCLASSIFIED, Scam.NORMAL, Scam.SUSPECTED]:
    check(
        f"no_report_before_confirmed_{state.value}",
        "check_report_readiness"
        not in actions(Call.BAIT_ACTIVE, state, Safety.PASS),
    )

print(f"PASS {len(checks)} architecture invariants")
for item in checks:
    print(f"- {item}")
