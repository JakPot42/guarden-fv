from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from z3 import Bool, Int, Solver, unsat


@dataclass
class Conflict:
    rules: list[str]
    explanation: str


@dataclass
class VerificationResult:
    status: str  # "PASS" or "FAIL"
    conflicts: list[Conflict]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "conflicts": [
                {"rules": c.rules, "explanation": c.explanation}
                for c in self.conflicts
            ],
        }


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def load_rule_set(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


class GuardenVerifier:
    """
    Checks a UAV geofencing rule set for logical contradictions using Z3.

    SCOPE: Verifies discrete logical rule sets only. Does NOT model physical
    flight dynamics, sensor noise, wind, or real hardware behaviour. Rule
    conflicts reported here mean the policy is self-contradictory — not that a
    specific aircraft will violate a boundary.
    """

    def verify(self, rule_set: dict) -> VerificationResult:
        rules = rule_set.get("rules", {})
        conflicts: list[Conflict] = []

        for check in (
            self._check_altitude_range,
            self._check_emergency_vs_absolute_min,
            self._check_signal_loss_dual_action,
        ):
            result = check(rules)
            if result is not None:
                conflicts.append(result)

        return VerificationResult(
            status="PASS" if not conflicts else "FAIL",
            conflicts=conflicts,
        )

    # ------------------------------------------------------------------
    # Check 1: Altitude range feasibility
    # Fails when min_altitude_m > max_altitude_m — no valid altitude exists.
    # ------------------------------------------------------------------
    def _check_altitude_range(self, rules: dict) -> Conflict | None:
        max_rule = rules.get("max_altitude", {})
        min_rule = rules.get("min_altitude", {})

        if not max_rule.get("enabled", True) or not min_rule.get("enabled", True):
            return None
        if "max_altitude_m" not in max_rule or "min_altitude_m" not in min_rule:
            return None

        s = Solver()
        alt = Int("altitude_m")
        s.assert_and_track(alt <= max_rule["max_altitude_m"], Bool(_safe_name(max_rule["rule_name"])))
        s.assert_and_track(alt >= min_rule["min_altitude_m"], Bool(_safe_name(min_rule["rule_name"])))

        if s.check() == unsat:
            return Conflict(
                rules=[max_rule["rule_name"], min_rule["rule_name"]],
                explanation=(
                    f"Altitude range is infeasible: max_altitude_m="
                    f"{max_rule['max_altitude_m']}m is below min_altitude_m="
                    f"{min_rule['min_altitude_m']}m. No valid operating altitude exists."
                ),
            )
        return None

    # ------------------------------------------------------------------
    # Check 2: Emergency descent vs. absolute minimum altitude
    # Fails when emergency descent can reach a floor that an absolute
    # minimum rule forbids — the two altitude constraints are UNSAT.
    # ------------------------------------------------------------------
    def _check_emergency_vs_absolute_min(self, rules: dict) -> Conflict | None:
        emg = rules.get("emergency_descent", {})
        min_rule = rules.get("min_altitude", {})

        if not emg.get("enabled", True):
            return None
        if not emg.get("overrides_min_altitude", False):
            return None
        if not min_rule.get("enabled", True):
            return None
        if not min_rule.get("is_absolute", False):
            return None
        if "descent_target_altitude_m" not in emg or "min_altitude_m" not in min_rule:
            return None

        s = Solver()
        alt = Int("emergency_altitude_m")
        s.assert_and_track(alt <= emg["descent_target_altitude_m"], Bool(_safe_name(emg["rule_name"])))
        s.assert_and_track(alt >= min_rule["min_altitude_m"], Bool(_safe_name(min_rule["rule_name"])))

        if s.check() == unsat:
            return Conflict(
                rules=[emg["rule_name"], min_rule["rule_name"]],
                explanation=(
                    f"Emergency descent to {emg['descent_target_altitude_m']}m "
                    f"contradicts the absolute minimum altitude of "
                    f"{min_rule['min_altitude_m']}m. The override cannot simultaneously "
                    f"reach its target and respect the non-overridable floor."
                ),
            )
        return None

    # ------------------------------------------------------------------
    # Check 3: Signal-loss dual-action conflict
    # Fails when HOLD_POSITION and RETURN_TO_HOME are both enabled for the
    # same trigger — the required response is logically ambiguous (UNSAT).
    # ------------------------------------------------------------------
    def _check_signal_loss_dual_action(self, rules: dict) -> Conflict | None:
        hold = rules.get("signal_loss_hold", {})
        rth = rules.get("signal_loss_rth", {})

        if not hold.get("enabled", False) or not rth.get("enabled", False):
            return None

        s = Solver()
        action = Int("signal_loss_action")
        # HOLD = 0, RTH = 1
        s.assert_and_track(action == 0, Bool(_safe_name(hold["rule_name"])))
        s.assert_and_track(action == 1, Bool(_safe_name(rth["rule_name"])))

        if s.check() == unsat:
            return Conflict(
                rules=[hold["rule_name"], rth["rule_name"]],
                explanation=(
                    "Signal-loss response is logically ambiguous: both HOLD_POSITION "
                    "and RETURN_TO_HOME are enabled for the same trigger. "
                    "A UAV cannot simultaneously hold position and return to home."
                ),
            )
        return None
