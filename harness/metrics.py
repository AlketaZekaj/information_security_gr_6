#!/usr/bin/env python3
"""Compute the study's metrics from raw.csv; every number is derived from the raw rows.

  python harness/metrics.py                          # reads results/raw.csv
  python harness/metrics.py results/pilot/raw.csv

Writes next to raw.csv, and prints the same as readable tables:
  summary.csv        false-accept and false-reject rates per component x config x category,
                     plus category ALL; error rows are counted but excluded from every rate
  coverage.csv       per component x config: case-level rejection coverage (CONTRACT.md),
                     and separately requirements R1-R7 as enforced, not_enforced, or
                     undetermined (a deciding case errored or was not run)
  errors.csv         every error row (not 200/401/403, or no response), listed separately;
                     only written when there are errors
  responses.csv      how rejections look per component x config: status, body shape,
                     WWW-Authenticate, and whether the framework or our wrapper wrote it
  latency.csv        median and p95 latency of the non-error requests
  config_effort.csv  every setting row of each target's CONFIG_NOTES.md and how it was counted

Rates are written unrounded; rounding happens only when printing. Standard library only.
"""
import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("component version config test_id category expected actual_status accepted "
          "correct latency_ms response_body www_authenticate").split()

# Which test cases decide each requirement (CONTRACT.md section 5). A requirement is
# enforced only when every one of its cases was rejected. NBF-MISSING is an acceptance
# check, not a requirement.
REQUIREMENTS = {
    "R1": ("issuer validated", ("ISS-INVALID", "ISS-MISSING")),
    "R2": ("audience validated", ("AUD-INVALID", "AUD-MISSING")),
    "R3": ("expiry validated", ("EXP-EXPIRED", "EXP-SKEW-120")),
    "R4": ("expiry required", ("EXP-MISSING",)),
    "R5": ("nbf validated", ("NBF-FUTURE",)),
    "R6": ("algorithm restricted", ("ALG-NONE", "ALG-UNEXPECTED", "ALG-RS512", "ALG-CONFUSION")),
    "R7": ("signature verified", ("SIG-TAMPERED",)),
}
NOTES_COLUMNS = ("Setting", "In default?", "In hardened?", "Changes behavior vs default?")


def warn(message):
    print(f"warning: {message}", file=sys.stderr)


def load_raw(path):
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            missing = [field for field in FIELDS if field not in (reader.fieldnames or [])]
            if missing:
                sys.exit(f"{path} is missing columns: {', '.join(missing)}")
            rows = list(reader)
    except OSError as error:
        sys.exit(f"cannot read {path}: {error}")
    if not rows:
        sys.exit(f"{path} has no rows")
    seen = set()
    for number, row in enumerate(rows, start=2):
        if row["accepted"] not in ("true", "false", ""):
            sys.exit(f"{path} line {number}: accepted must be true, false or empty (error), "
                     f"got {row['accepted']!r}")
        if (row["correct"] == "") != (row["accepted"] == ""):
            sys.exit(f"{path} line {number}: correct must be empty exactly when accepted is empty")
        if row["expected"] not in ("accept", "reject"):
            sys.exit(f"{path} line {number}: expected must be accept or reject, got {row['expected']!r}")
        key = (row["component"], row["config"], row["test_id"])
        if key in seen:
            sys.exit(f"{path} line {number}: duplicate row for {' / '.join(key)}")
        seen.add(key)
    return rows


def groups(rows):
    """Rows per (component, version, config), in the order they first appear."""
    result = {}
    for row in rows:
        result.setdefault((row["component"], row["version"], row["config"]), []).append(row)
    return result


def is_error(row):
    """CONTRACT.md section 5: an error (not 200/401/403, or no response) has accepted empty."""
    return row["accepted"] == ""


def rates(rows):
    errors = sum(is_error(row) for row in rows)
    invalid = [row for row in rows if row["expected"] == "reject" and not is_error(row)]
    valid = [row for row in rows if row["expected"] == "accept" and not is_error(row)]
    false_accepts = sum(row["accepted"] == "true" for row in invalid)
    false_rejects = [row["test_id"] for row in valid if row["accepted"] == "false"]
    return {
        "cases": len(rows),
        "errors": errors,
        "invalid_measured": len(invalid),
        "false_accepts": false_accepts,
        "false_accept_rate": false_accepts / len(invalid) if invalid else "",
        "valid_measured": len(valid),
        "false_rejects": len(false_rejects),
        "false_reject_rate": len(false_rejects) / len(valid) if valid else "",
        "false_reject_cases": ";".join(false_rejects),
    }


def summary_rows(grouped):
    result = []
    for (component, version, config), rows in grouped.items():
        categories = list(dict.fromkeys(row["category"] for row in rows))
        for category in categories + ["ALL"]:
            subset = rows if category == "ALL" else [row for row in rows if row["category"] == category]
            result.append({"component": component, "version": version, "config": config,
                           "category": category, **rates(subset)})
    return result


def requirement_status(outcomes):
    """outcomes: the accepted value of each deciding case, None when the case was not run."""
    if "true" in outcomes:
        return "not_enforced"
    if all(outcome == "false" for outcome in outcomes):
        return "enforced"
    return "undetermined"


def coverage_rows(grouped):
    """Case-level rejection coverage (CONTRACT.md section 5) and, separately, R1-R7."""
    result = []
    for (component, version, config), rows in grouped.items():
        invalid = [row for row in rows if row["expected"] == "reject"]
        measured = [row for row in invalid if not is_error(row)]
        rejected = sum(row["accepted"] == "false" for row in measured)
        by_id = {row["test_id"]: row["accepted"] for row in rows}
        statuses = {req: requirement_status([by_id.get(case) for case in cases])
                    for req, (_, cases) in REQUIREMENTS.items()}
        enforced = sum(status == "enforced" for status in statuses.values())
        result.append({"component": component, "version": version, "config": config,
                       "cases_rejected": rejected, "cases_measured": len(measured),
                       "case_coverage": rejected / len(measured) if measured else "",
                       "case_errors": len(invalid) - len(measured),
                       **statuses, "requirements_enforced": enforced,
                       "requirements_undetermined": sum(status == "undetermined" for status in statuses.values()),
                       "requirements_defined": len(REQUIREMENTS),
                       "requirement_coverage": enforced / len(REQUIREMENTS)})
    return result


def body_shape(body):
    if not body:
        return "empty"
    try:
        json.loads(body)
    except ValueError:
        return "text"
    return "json"


def response_rows(grouped, components):
    result = []
    for (component, version, config), rows in grouped.items():
        rejected = [row for row in rows if row["accepted"] == "false"]
        statuses = Counter(row["actual_status"] for row in rejected)
        headers = [row["www_authenticate"] for row in rejected if row["www_authenticate"]]
        result.append({
            "component": component, "version": version, "config": config,
            "response_author": components.get(component, {}).get("response_author", ""),
            "rejections": len(rejected),
            "statuses": ";".join(sorted(statuses)),
            "dominant_status": statuses.most_common(1)[0][0] if statuses else "",
            "body_shapes": ";".join(sorted({body_shape(row["response_body"]) for row in rejected})),
            "www_authenticate_share": len(headers) / len(rejected) if rejected else "",
            "www_authenticate_example": headers[0][:120] if headers else "",
        })
    return result


def status_consistency(responses):
    """Per config: the most common rejection status and the share of components using it."""
    result = {}
    for config in dict.fromkeys(row["config"] for row in responses):
        dominant = [row["dominant_status"] for row in responses if row["config"] == config and row["dominant_status"]]
        if dominant:
            status, count = Counter(dominant).most_common(1)[0]
            result[config] = (status, count, len(dominant))
    return result


def latency_rows(grouped):
    result = []
    for (component, version, config), rows in grouped.items():
        values = sorted(float(row["latency_ms"]) for row in rows if not is_error(row) and row["latency_ms"])
        if not values:
            continue
        p95 = statistics.quantiles(values, n=100, method="inclusive")[94] if len(values) > 1 else values[0]
        result.append({"component": component, "version": version, "config": config,
                       "requests": len(values), "median_ms": statistics.median(values), "p95_ms": p95})
    return result


def table_cells(line):
    line = line.strip()
    return [cell.strip() for cell in line.strip("|").split("|")] if line.startswith("|") else None


def normalized(cell):
    """Lower-case cell text without markdown emphasis, code marks or parenthetical remarks."""
    cell = re.sub(r"\(.*?\)", "", cell.replace("**", "").replace("`", ""))
    return " ".join(cell.lower().split())


def settings_table(path):
    """Rows of the CONFIG_NOTES.md table whose header starts with 'Setting', as dicts."""
    lines = path.read_text(encoding="utf-8").splitlines()
    for start, line in enumerate(lines):
        header = table_cells(line)
        if not header or header[0] != "Setting":
            continue
        missing = [column for column in NOTES_COLUMNS if column not in header]
        if missing:
            warn(f"{path}: settings table lacks column(s) {', '.join(missing)}")
            return None
        rows = []
        for body_line in lines[start + 2:]:  # skip the |---| separator
            cells = table_cells(body_line)
            if cells is None:
                break
            rows.append(dict(zip(header, cells)))
        return rows
    warn(f"{path}: no table with a 'Setting' header")
    return None


def config_effort(components, names):
    """Count configuration changes per component from its CONFIG_NOTES.md settings table.

    A row is a change when its hardened cell is not 'same' and differs from its default
    cell (so 'implicit true' -> 'explicit true' counts, a value present in both does not).
    A change alters behavior when its 'Changes behavior vs default?' cell starts with 'yes'.
    Every row and its classification is written to config_effort.csv so the count can be
    checked by hand against the notes."""
    detail, totals = [], {}
    for name in names:
        target_dir = components.get(name, {}).get("target_dir")
        notes = ROOT / target_dir / "CONFIG_NOTES.md" if target_dir else None
        if notes is None or not notes.is_file():
            warn(f"{name}: no CONFIG_NOTES.md, configuration effort not computed")
            continue
        table = settings_table(notes)
        if table is None:
            continue
        changes = behavior = 0
        for row in table:
            default, hardened = normalized(row["In default?"]), normalized(row["In hardened?"])
            is_change = hardened != "same" and hardened != default
            changes_behavior = is_change and normalized(row["Changes behavior vs default?"]).startswith("yes")
            changes += is_change
            behavior += changes_behavior
            detail.append({"component": name, "setting": row["Setting"], "in_default": row["In default?"],
                           "in_hardened": row["In hardened?"],
                           "changes_behavior": row["Changes behavior vs default?"],
                           "counted_as_change": str(is_change).lower(),
                           "counted_as_behavior_change": str(changes_behavior).lower()})
        totals[name] = (changes, behavior)
    return detail, totals


def write_csv(path, rows):
    """Write rows to path; return the file name, or None when there was nothing to write."""
    if not rows:
        path.unlink(missing_ok=True)  # never leave a stale file from an earlier run beside new results
        return None
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path.name


def print_table(title, headers, rows):
    widths = [max(len(str(value)) for value in column) for column in zip(headers, *rows)]
    print(f"\n{title}")
    for line in [headers, ["-" * width for width in widths], *rows]:
        print("  ".join(str(value).ljust(width) for value, width in zip(line, widths)).rstrip())


def fraction(count, total, rate):
    return f"{count}/{total} ({rate:.1%})" if total else "n/a"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw", nargs="?", default=str(ROOT / "results" / "raw.csv"))
    parser.add_argument("--components-file", default=str(ROOT / "components.json"))
    args = parser.parse_args()
    raw = Path(args.raw)
    out = raw.parent

    rows = load_raw(raw)
    try:
        components = {c["name"]: c for c in json.loads(Path(args.components_file).read_text(encoding="utf-8"))}
    except (OSError, ValueError) as error:
        sys.exit(f"cannot read {args.components_file}: {error}")
    unmapped = sorted({row["test_id"] for row in rows if row["expected"] == "reject"}
                      - {case for _, cases in REQUIREMENTS.values() for case in cases})
    if unmapped:
        warn(f"expected-reject cases not assigned to any requirement: {', '.join(unmapped)}")

    grouped = groups(rows)
    summary = summary_rows(grouped)
    coverage = coverage_rows(grouped)
    responses = response_rows(grouped, components)
    latency = latency_rows(grouped)
    names = list(dict.fromkeys(row["component"] for row in rows))
    effort_detail, effort = config_effort(components, names)

    errors = [row for row in rows if is_error(row)]
    outputs = {"summary.csv": summary, "coverage.csv": coverage, "errors.csv": errors,
               "responses.csv": responses, "latency.csv": latency, "config_effort.csv": effort_detail}
    written = [name for name in (write_csv(out / file, data) for file, data in outputs.items()) if name]

    print_table("False accepts and rejects (all categories; errors excluded from rates)",
                ["component", "config", "false accepts", "false rejects", "rejected valid cases", "errors"],
                [[r["component"], r["config"], fraction(r["false_accepts"], r["invalid_measured"], r["false_accept_rate"] or 0),
                  fraction(r["false_rejects"], r["valid_measured"], r["false_reject_rate"] or 0),
                  r["false_reject_cases"] or "-", r["errors"]]
                 for r in summary if r["category"] == "ALL"])
    categories = [c for c in dict.fromkeys(r["category"] for r in summary) if c != "ALL"]
    by_category = {(r["component"], r["config"], r["category"]): r for r in summary}

    def category_cell(row):
        return f"{row['false_accepts']}/{row['invalid_measured']}" if row and row["invalid_measured"] else "-"

    print_table("False accepts per category", ["component", "config", *categories],
                [[component, config, *[category_cell(by_category.get((component, config, c))) for c in categories]]
                 for component, _, config in grouped])
    print_table("Case-level rejection coverage (expected-reject cases rejected / non-error ones)",
                ["component", "config", "rejected", "errors"],
                [[r["component"], r["config"], fraction(r["cases_rejected"], r["cases_measured"], r["case_coverage"] or 0),
                  r["case_errors"]] for r in coverage])
    print_table("Requirement coverage, grouped measure (enforced when all its cases are rejected)",
                ["component", "config", *REQUIREMENTS, "enforced"],
                [[r["component"], r["config"],
                  *[{"enforced": "yes", "not_enforced": "NO", "undetermined": "?"}[r[req]] for req in REQUIREMENTS],
                  f"{r['requirements_enforced']}/{r['requirements_defined']} ({r['requirement_coverage']:.0%})"
                  + (f", {r['requirements_undetermined']} undetermined" if r["requirements_undetermined"] else "")]
                 for r in coverage])
    print("  " + "; ".join(f"{req} {label}" for req, (label, _) in REQUIREMENTS.items()) + ". ? = undetermined")
    if effort:
        print_table("Configuration effort (from CONFIG_NOTES.md; rows in config_effort.csv)",
                    ["component", "settings changed for hardened", "of which change behavior"],
                    [[name, changes, behavior] for name, (changes, behavior) in effort.items()])
    print_table("Rejection responses (wrapper = written by our code, framework = by the component)",
                ["component", "config", "author", "statuses", "body", "WWW-Authenticate"],
                [[r["component"], r["config"], r["response_author"] or "?", r["statuses"] or "-", r["body_shapes"] or "-",
                  f"{r['www_authenticate_share']:.0%}" if r["rejections"] else "-"] for r in responses])
    for config, (status, count, total) in status_consistency(responses).items():
        print(f"  {config}: {count}/{total} components reject mainly with {status}")
    if latency:
        print_table("Latency of non-error requests (single requests; diagnostic, not a benchmark)",
                    ["component", "config", "requests", "median ms", "p95 ms"],
                    [[r["component"], r["config"], r["requests"], f"{r['median_ms']:.1f}", f"{r['p95_ms']:.1f}"]
                     for r in latency])
    if errors:
        print_table("Errors (excluded from every rate)", ["component", "config", "test", "status", "response"],
                    [[r["component"], r["config"], r["test_id"], r["actual_status"] or "none", r["response_body"][:60]]
                     for r in errors])
    else:
        print("\nErrors: none")
    print(f"\nwrote {', '.join(written)} to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
