from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class ScenarioResult:
    scenario: str
    request_count: int
    failure_count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_rps: float

    @property
    def failure_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return (self.failure_count / self.request_count) * 100.0


def _to_float(value: str | None) -> float:
    if value is None:
        return math.nan
    normalized = value.strip()
    if not normalized:
        return math.nan
    return float(normalized)


def _to_int(value: str | None) -> int:
    if value is None:
        return 0
    normalized = value.strip()
    if not normalized:
        return 0
    return int(float(normalized))


def _scenario_from_file(stats_file: Path) -> str:
    stem = stats_file.stem
    if stem.endswith("_stats"):
        return stem.removesuffix("_stats")
    return stem


def _load_scenario_result(stats_file: Path) -> ScenarioResult:
    with stats_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_type = (row.get("Type") or "").strip()
            row_name = (row.get("Name") or "").strip()
            if row_type == "POST" and row_name == "POST /api/v1/reservations":
                p50_ms = _to_float(row.get("50%"))
                if math.isnan(p50_ms):
                    p50_ms = _to_float(row.get("Median Response Time"))
                return ScenarioResult(
                    scenario=_scenario_from_file(stats_file),
                    request_count=_to_int(row.get("Request Count")),
                    failure_count=_to_int(row.get("Failure Count")),
                    p50_ms=p50_ms,
                    p95_ms=_to_float(row.get("95%")),
                    p99_ms=_to_float(row.get("99%")),
                    throughput_rps=_to_float(row.get("Requests/s")),
                )
    raise ValueError(f"POST /api/v1/reservations row not found in {stats_file}")


def _format_float(value: float) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value:.2f}"


def _build_markdown(
    results: list[ScenarioResult],
    threshold_ms: float,
    integrity_report_path: Path | None,
) -> str:
    lines: list[str] = []
    lines.append("# Stress Test Report")
    lines.append("")
    lines.append(f"- Generated at: {datetime.now(UTC).isoformat()}")
    lines.append(f"- P95 threshold reference: {threshold_ms:.2f} ms")
    lines.append("")
    lines.append(
        "| Scenario | Requests | Failures | Failure rate | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (req/s) |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    for result in results:
        lines.append(
            "| "
            f"{result.scenario} | "
            f"{result.request_count} | "
            f"{result.failure_count} | "
            f"{result.failure_rate:.2f}% | "
            f"{_format_float(result.p50_ms)} | "
            f"{_format_float(result.p95_ms)} | "
            f"{_format_float(result.p99_ms)} | "
            f"{_format_float(result.throughput_rps)} |"
        )

    lines.append("")
    breakpoint_result = next(
        (
            r
            for r in results
            if r.failure_count > 0 or (not math.isnan(r.p95_ms) and r.p95_ms > threshold_ms)
        ),
        None,
    )
    if breakpoint_result is None:
        lines.append("Point of break: not reached under executed scenarios.")
    else:
        lines.append(
            "Point of break: "
            f"{breakpoint_result.scenario} "
            f"(failure_rate={breakpoint_result.failure_rate:.2f}%, p95={_format_float(breakpoint_result.p95_ms)} ms)."
        )

    spike = next((r for r in results if r.scenario == "stress-spike-500"), None)
    recovery = next((r for r in results if r.scenario == "stress-recovery-50"), None)
    if spike is not None and recovery is not None:
        recovered = (
            recovery.failure_count == 0
            and not math.isnan(spike.p95_ms)
            and not math.isnan(recovery.p95_ms)
            and recovery.p95_ms < spike.p95_ms
        )
        lines.append(
            "Recovery after spike: "
            + ("PASS" if recovered else "FAIL")
            + f" (spike p95={_format_float(spike.p95_ms)} ms, recovery p95={_format_float(recovery.p95_ms)} ms)."
        )

    if integrity_report_path is not None:
        lines.append(f"Integrity report: `{integrity_report_path.as_posix()}`")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize Locust stress outputs.")
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing stress *_stats.csv files.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/stress/summary.md",
        help="Output markdown path.",
    )
    parser.add_argument(
        "--integrity-report",
        default="",
        help="Optional integrity report path to reference in markdown.",
    )
    parser.add_argument(
        "--p95-threshold-ms",
        type=float,
        default=500.0,
        help="P95 threshold reference in ms.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any scenario has failures.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    integrity_path = Path(args.integrity_report) if args.integrity_report else None

    stats_files = sorted(input_dir.glob("stress-*_stats.csv"))
    if not stats_files:
        raise FileNotFoundError(f"No stress-*_stats.csv files found in {input_dir}")

    execution_order = {
        "stress-ramp-500": 1,
        "stress-spike-500": 2,
        "stress-recovery-50": 3,
        "stress-breakpoint-1000": 4,
    }
    results = [_load_scenario_result(path) for path in stats_files]
    results.sort(key=lambda result: execution_order.get(result.scenario, 999))
    markdown = _build_markdown(results, args.p95_threshold_ms, integrity_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    if args.strict:
        has_failures = any(result.failure_count > 0 for result in results)
        return 1 if has_failures else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
