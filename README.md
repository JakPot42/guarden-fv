# Guarden-FV: UAV Geofencing Formal Verification

> **SCOPE DISCLAIMER — READ FIRST**
>
> Guarden-FV verifies **discrete logical rule sets** only.
> It does **NOT** model physical flight dynamics, sensor noise, wind, GPS drift,
> actuator failure, or real hardware behaviour.
> It does **NOT** produce safety guarantees about any aircraft.
>
> A **PASS** result means the policy document is internally consistent.
> It says nothing about whether a real UAV will respect that policy.
> A **FAIL** result means the written rules contain a logical contradiction
> that an autonomous system cannot simultaneously satisfy.
>
> This tool is a **rule-consistency checker for autonomous system policy** —
> analogous to how formal contract verification checks clause consistency,
> not whether parties will perform.

---

Uses the [Z3 SMT solver](https://github.com/Z3Prover/z3) to check whether a
UAV geofencing rule set contains logical contradictions. When Z3 finds UNSAT,
the CLI reports the **specific named rules** that conflict — same technique as
formal legal-contract verification applied to autonomous-system policy.

## Usage

```bash
pip install -r requirements.txt

# Verify a rule set
py cli.py verify rule_sets/rs_01_clean.json
py cli.py verify rule_sets/rs_02_emergency_conflict.json

# JSON output (for pipeline integration)
py cli.py verify rule_sets/rs_02_emergency_conflict.json --json-out

# Run all three demo rule sets
py cli.py demo
```

## Demo Rule Sets

| File | Expected | Scenario |
|------|----------|----------|
| `rs_01_clean.json` | **PASS** | Standard recreational quadcopter — all rules consistent |
| `rs_02_emergency_conflict.json` | **FAIL** | Emergency descent to 0m contradicts absolute 30m pedestrian safety floor |
| `rs_03_signal_conflict.json` | **FAIL** | HOLD_POSITION and RETURN_TO_HOME both active on signal loss |

## Sample Output

```
Guarden-FV  |  rs_02_emergency_conflict
            |  Urban delivery drone — emergency override contradicts absolute altitude floor
------------------------------------------------------------

  FAIL  1 conflict(s) detected.

  [1] Conflicting rules:
       • §3 Battery Critical Emergency Override
       • §2 Absolute Minimum — Pedestrian Safety
      Emergency descent to 0m contradicts the absolute minimum altitude of 30m.
      The override cannot simultaneously reach its target and respect the non-overridable floor.
```

## Rule Set Schema

```json
{
  "rule_set_id": "my_rules",
  "description": "human-readable description",
  "vehicle_class": "optional label",
  "rules": {
    "max_altitude":      { "rule_name": "...", "max_altitude_m": 120, "enabled": true },
    "min_altitude":      { "rule_name": "...", "min_altitude_m": 10, "is_absolute": false, "enabled": true },
    "emergency_descent": { "rule_name": "...", "descent_target_altitude_m": 0, "overrides_min_altitude": false, "enabled": true },
    "signal_loss_hold":  { "rule_name": "...", "trigger": "signal_loss", "action": "HOLD", "enabled": false },
    "signal_loss_rth":   { "rule_name": "...", "trigger": "signal_loss", "action": "RTH",  "enabled": true }
  }
}
```

**Key flag interactions checked by Z3:**
- `is_absolute: true` on `min_altitude` + `overrides_min_altitude: true` on `emergency_descent` → Check 2
- `enabled: true` on both `signal_loss_hold` and `signal_loss_rth` → Check 3
- `min_altitude_m > max_altitude_m` → Check 1

## Three Z3 Checks

| Check | What it finds |
|-------|---------------|
| Altitude range feasibility | `min_altitude_m > max_altitude_m` — no valid altitude exists |
| Emergency descent vs. absolute minimum | Emergency override descends below a non-overridable floor |
| Signal-loss dual-action | HOLD_POSITION and RETURN_TO_HOME both active on same trigger |

Each check uses Z3's `assert_and_track` so the UNSAT core names the conflicting rules directly in the output.

## Running Tests

```bash
pytest tests/ -v
```

32 tests, all passing. No network calls, no hardware required.

## Architecture

```
rule_engine.py   ← GuardenVerifier + Z3 checks + Conflict/VerificationResult dataclasses
cli.py           ← Click CLI (verify + demo commands)
rule_sets/       ← Demo JSON rule sets
tests/           ← pytest suite
```

## Tech Stack

- **Z3 SMT solver** (`z3-solver`) — the same solver used in z3-contract
- **Click** — CLI
- **pytest** — tests

## Related

The same `assert_and_track` / UNSAT-core naming technique appears in
[z3-contract](https://github.com/JakPot42/z3-contract), which applies it to
legal clause verification.
