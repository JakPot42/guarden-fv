import json
import sys
from pathlib import Path

import click

from rule_engine import GuardenVerifier, load_rule_set

RULES_DIR = Path(__file__).parent / "rule_sets"

_DEMO_FILES = [
    RULES_DIR / "rs_01_clean.json",
    RULES_DIR / "rs_02_emergency_conflict.json",
    RULES_DIR / "rs_03_signal_conflict.json",
]


@click.group()
def cli() -> None:
    """Guarden-FV: UAV Geofencing Formal Verification CLI.

    Uses Z3 to check whether a UAV rule set contains logical contradictions.
    Reports named conflicting rules when UNSAT — same technique as formal
    contract verification applied to autonomous-system policy.
    """


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--json-out", is_flag=True, help="Output results as JSON.")
def verify(file: Path, json_out: bool) -> None:
    """Verify FILE (a UAV rule set JSON) for logical conflicts."""
    rule_set = load_rule_set(file)
    result = GuardenVerifier().verify(rule_set)

    if json_out:
        click.echo(json.dumps(result.to_dict(), indent=2))
        sys.exit(0 if result.status == "PASS" else 1)

    rule_set_id = rule_set.get("rule_set_id", file.stem)
    description = rule_set.get("description", "")
    n_rules = len(rule_set.get("rules", {}))

    click.echo(f"\nGuarden-FV  |  {rule_set_id}")
    if description:
        click.echo(f"            |  {description}")
    click.echo("-" * 60)

    if result.status == "PASS":
        click.secho(
            f"\n  PASS  No conflicts detected in {n_rules} rules.\n",
            fg="green",
            bold=True,
        )
    else:
        click.secho(
            f"\n  FAIL  {len(result.conflicts)} conflict(s) detected.\n",
            fg="red",
            bold=True,
        )
        for i, conflict in enumerate(result.conflicts, 1):
            click.echo(f"  [{i}] Conflicting rules:")
            for rule in conflict.rules:
                click.secho(f"       * {rule}", fg="red")
            click.echo(f"      {conflict.explanation}\n")

    sys.exit(0 if result.status == "PASS" else 1)


@cli.command()
def demo() -> None:
    """Run all three demo rule sets and report results."""
    verifier = GuardenVerifier()
    click.echo("\nGuarden-FV  |  Demo Run -- 3 Rule Sets")
    click.echo("=" * 60)

    exit_code = 0
    for path in _DEMO_FILES:
        if not path.exists():
            click.secho(f"  SKIP  {path.name} not found", fg="yellow")
            continue

        rule_set = load_rule_set(path)
        result = verifier.verify(rule_set)
        label = rule_set.get("rule_set_id", path.stem)

        if result.status == "PASS":
            click.secho(f"  PASS  {label}", fg="green")
        else:
            click.secho(f"  FAIL  {label}", fg="red")
            for conflict in result.conflicts:
                rules_str = " + ".join(conflict.rules)
                click.echo(f"        -> {rules_str}")
            exit_code = 1

    click.echo()
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
