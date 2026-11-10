"""Generate a synthetic randomized experiment and its portfolio deliverables."""

import csv
import json
import math
import random
import sqlite3
from pathlib import Path

from build_power_bi import build_power_bi


ROOT = Path(__file__).resolve().parent
CHANNELS = {"Organic": (16000, .19), "Paid Search": (14000, .15), "Referral": (10000, .22)}


def generate(seed):
    rng = random.Random(seed)
    visitor_id = 0
    for channel, (count, conversion) in CHANNELS.items():
        assignments = ["Control"] * (count // 2) + ["Treatment"] * (count // 2)
        rng.shuffle(assignments)
        for variant in assignments:
            visitor_id += 1
            treatment = variant == "Treatment"
            price = 32 if treatment else 29
            converted = rng.random() < conversion - (.013 if treatment else 0)
            retained = converted and rng.random() < (.67 if treatment else .69)
            months = 3 if retained else rng.choice([1, 2]) if converted else 0
            revenue = price * 100 * months
            cost = (rng.randint(1450, 1750) * months + 400) if converted else 0
            yield visitor_id, variant, channel, price, int(converted), int(retained), months, revenue, cost


def export_experiment():
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        db.execute("""
            CREATE TABLE visitors (
                visitor_id INTEGER PRIMARY KEY, variant TEXT, channel TEXT, price INTEGER,
                converted INTEGER, retained INTEGER, paid_months INTEGER,
                revenue_cents INTEGER, cost_cents INTEGER
            )
        """)
        db.executemany("INSERT INTO visitors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", generate(42))
        db.executescript((ROOT / "analysis.sql").read_text(encoding="utf-8"))
        assert db.execute("""
            SELECT COUNT(*) FROM visitor_outcomes WHERE retained > converted
            OR (converted = 0 AND (paid_months <> 0 OR contribution_cents <> 0))
        """).fetchone()[0] == 0
        rows = [dict(row) for row in db.execute("SELECT * FROM experiment_summary ORDER BY variant, channel")]
        assert sum(row["visitors"] for row in rows) == 40000
        assert all(row["visitors"] * 2 == CHANNELS[row["channel"]][0] for row in rows)
    destination = ROOT / "data"
    destination.mkdir(exist_ok=True)
    with (destination / "experiment_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def rate_interval(treatment, control, metric):
    """Stratified difference, weighted by each channel's visitor share."""
    total = sum(row["visitors"] for row in control)
    effect = variance = 0
    for t, c in zip(treatment, control):
        assert t["channel"] == c["channel"]
        weight = c["visitors"] / total
        moments = []
        for row in (t, c):
            n = row["visitors"]
            if metric == "contribution":
                mean = row["total_cents"] / n
                sample_variance = (row["squared_cents"] - n * mean**2) / (n - 1)
                moments.append((mean / 100, sample_variance / n / 10000))
            else:
                mean = row[metric] / n
                moments.append((mean, mean * (1 - mean) / (n - 1)))
        effect += weight * (moments[0][0] - moments[1][0])
        variance += weight**2 * (moments[0][1] + moments[1][1])
    margin = 1.96 * math.sqrt(variance)
    return effect, effect - margin, effect + margin


def arm_metrics(rows):
    totals = {key: sum(row[key] for row in rows) for key in
              ("visitors", "conversions", "retained", "total_cents")}
    n = totals["visitors"]
    return {
        "visitors": n,
        "conversion": totals["conversions"] / n,
        "retained_per_visitor": totals["retained"] / n,
        "retention_among_buyers": totals["retained"] / totals["conversions"],
        "contribution": totals["total_cents"] / 100 / n,
    }


def main():
    rows = export_experiment()
    control, treatment = ([r for r in rows if r["variant"] == arm] for arm in ("Control", "Treatment"))
    arms = {arm: arm_metrics(data) for arm, data in (("Control", control), ("Treatment", treatment))}
    effects = {metric: rate_interval(treatment, control, metric)
               for metric in ("contribution", "conversions", "retained")}
    effect, low, high = effects["contribution"]
    _, conversion_low, _ = effects["conversions"]
    _, retention_low, _ = effects["retained"]
    clears = low > 0 and conversion_low > -.025 and retention_low > -.025
    decision = "Proceed with a staged rollout" if clears else "Hold the full rollout"
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "results.json").write_text(json.dumps(
        {"arms": arms, "effects_95_ci": effects, "decision": decision}, indent=2
    ) + "\n", encoding="utf-8")
    lines = ["# Pricing recommendation", "", f"**{decision}.**", "",
             f"Moving from $29 to $32 changed 90-day contribution per assigned visitor by "
             f"${effect:+.2f} (95% CI ${low:+.2f} to ${high:+.2f}).", "",
             "| Metric | $29 control | $32 treatment | Change (95% CI) |",
             "| --- | ---: | ---: | ---: |"]
    for label, key, metric in (
        ("Contribution per visitor", "contribution", "contribution"),
        ("Conversion", "conversion", "conversions"),
        ("90-day retained per visitor", "retained_per_visitor", "retained"),
        ("90-day retention among buyers", "retention_among_buyers", None),
    ):
        values = [arm[key] for arm in arms.values()]
        if metric == "contribution":
            cells = [f"${v:.2f}" for v in values] + [f"${effect:+.2f} (${low:+.2f}, ${high:+.2f})"]
        else:
            cells = [f"{v:.2%}" for v in values]
            change = effects[metric] if metric else ()
            cells.append(f"{change[0]*100:+.2f} pp ({change[1]*100:+.2f}, {change[2]*100:+.2f})" if change else "Descriptive")
        lines.append("| " + " | ".join([label, *cells]) + " |")
    next_step = (
        "Ramp gradually and continue monitoring conversion and 90-day retained visitors."
        if clears else
        "Keep $29 as the default and test a smaller price increase in a new randomized experiment."
    )
    lines += ["", "The illustrative rollout rule requires a positive lower confidence bound on "
              "contribution lift and lower bounds above −2.5 percentage points for both "
              "conversion and retained visitors. " + next_step,
              "", "Buyer-only retention is descriptive because the price can change who subscribes. "
              "These results come from simulated behavior and do not predict a real pricing outcome."]
    (reports / "recommendation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    build_power_bi(ROOT / "power-bi", rows)
    print(f"{decision} | contribution lift ${effect:+.2f} | 40,000 simulated visitors")


if __name__ == "__main__":
    main()
