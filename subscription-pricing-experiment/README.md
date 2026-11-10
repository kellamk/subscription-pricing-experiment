# Subscription Pricing Experiment

Would increasing a monthly subscription from **$29 to $32** improve 90-day contribution enough to justify the loss in conversion and retention?

This case study simulates a randomized A/B test with **40,000 synthetic visitors** across organic, paid search, and referral channels. It uses SQL to build the analysis and Python to estimate effects, quantify uncertainty, and generate the Power BI report inputs.

## Results at a glance

| Metric | $29 control | $32 treatment | Treatment minus control |
| --- | ---: | ---: | ---: |
| 90-day contribution per assigned visitor | $5.38 | $6.06 | **+$0.68** |
| Conversion | 18.62% | 16.94% | −1.68 pp |
| 90-day retained subscribers per assigned visitor | 12.78% | 11.09% | −1.69 pp |

**Recommendation:** Proceed with a staged rollout in this simulated scenario. Both guardrails pass, though conversion is close to the threshold. [Read the recommendation and confidence intervals](reports/recommendation.md).

## Power BI dashboard

Download or clone the whole repository and open [Pricing Experiment.pbip](power-bi/Pricing%20Experiment.pbip) in a recent version of **Power BI Desktop** on Windows. Keep the report and semantic model folders together. If the report opens with blank visuals, select **Home → Refresh** to load the six embedded summary rows. There are no credentials or machine-specific data paths. The model includes DAX measures for visitor count, conversion, 90-day retained visitors, and contribution per visitor. Three charts compare experiment arms, and a table breaks results down by acquisition channel. The GitHub results table above provides a browser-readable summary.

## Reproduce the experiment

Run this from the repository root with Python 3.10 or newer. It uses only the standard library.

```sh
python run_experiment.py
```

1. Python simulates visitor assignments and outcomes using seed 42. Each channel is split equally between control and treatment.
2. SQLite runs [analysis.sql](analysis.sql) to calculate visitor-level contribution and summarize counts, sums, and squared sums by arm and channel.
3. Python calculates channel-weighted differences and approximate 95% confidence intervals, exports the [summary data](data/experiment_summary.csv), and rebuilds the recommendation and Power BI project.

The generator overwrites the generated data, report, and Power BI definitions. Save any manual Power BI customizations separately before rerunning it.

## Measurement choices

- **Primary metric:** 90-day contribution per assigned visitor. Contribution is collected subscription revenue less simulated service and onboarding costs. Nonbuyers contribute zero. The model excludes fixed overhead, acquisition spend, refunds, and taxes.
- **Guardrails:** conversion and 90-day retained subscribers, each divided by all assigned visitors. The rollout rule requires the lower 95% confidence bound for each change to be above −2.5 percentage points and the lower bound for contribution lift to be positive.
- **Buyer retention:** the share of buyers still subscribed in month three is descriptive because pricing can change who converts. The per-visitor retention measure keeps the original randomized groups intact.
- **Uncertainty:** differences are weighted by channel traffic share, with normal-approximation intervals from within-channel sample variances. These are individual intervals. The decision rule is illustrative, and a real test should justify its thresholds and inference plan before launch.

All visitors, costs, and outcomes are synthetic. The assumed price response is built into the simulation. The results illustrate the analysis workflow and do not estimate actual customer behavior.
