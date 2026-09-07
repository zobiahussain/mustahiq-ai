"""Train the synthetic eligibility confidence scorer and save its artifact."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from data.features import FEATURE_COLUMNS, build_feature_row
from data.synthetic import (
    build_synthetic_programs,
    generate_labeled_dataset,
    generate_synthetic_profiles,
)

from eligibility.persistence import save_scorer
from eligibility.scoring import train_and_evaluate


# The first shipped demo model trained on this many synthetic profiles; kept
# here so the metadata can state plainly how much the caseload grew.
PREVIOUS_PROFILE_COUNT = 3_000
DEFAULT_PROFILE_COUNT = 15_000


def train_synthetic_scorer(
    *,
    profile_count: int = DEFAULT_PROFILE_COUNT,
    seed: int = 42,
    output_dir: str | Path = "artifacts/eligibility-scorer",
):
    """Generate, train, evaluate, and persist the demo confidence scorer."""

    profiles = generate_synthetic_profiles(profile_count, seed=seed)
    programs = build_synthetic_programs()
    examples = generate_labeled_dataset(profiles, programs, seed=seed)
    feature_rows = [
        build_feature_row(
            example.profile,
            program_domain=example.program.domain,
            program_rules=example.program.rules,
        )
        for example in examples
    ]
    model, report = train_and_evaluate(
        feature_rows,
        [example.verified for example in examples],
        [example.profile_index for example in examples],
    )

    training_summary = {
        "trained_on": date.today().isoformat(),
        "synthetic_profiles": profile_count,
        "previous_synthetic_profiles": PREVIOUS_PROFILE_COUNT,
        "programmes": len(programs),
        "programme_domains": sorted({program.domain for program in programs}),
        "labeled_examples": len(examples),
        "feature_count": len(FEATURE_COLUMNS),
        "seed": seed,
        "holdout_metrics": {
            "precision": round(report.precision, 4),
            "recall": round(report.recall, 4),
            "f1": round(report.f1, 4),
            "roc_auc": round(report.roc_auc, 4),
            "positive_rate": round(report.positive_rate, 4),
            "train_size": report.train_size,
            "test_size": report.test_size,
            "train_profile_count": report.train_profile_count,
            "test_profile_count": report.test_profile_count,
            "confusion_matrix": report.confusion_matrix,
        },
        "note": (
            "Synthetic data only (SRS 7.5). Trained on a single 80/20 "
            "StratifiedGroupKFold split grouped by profile so no beneficiary "
            "appears in both train and test."
        ),
    }
    save_scorer(model, output_dir, training_summary=training_summary)
    return report, len(examples), training_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=int, default=DEFAULT_PROFILE_COUNT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="artifacts/eligibility-scorer")
    args = parser.parse_args()

    report, example_count, training_summary = train_synthetic_scorer(
        profile_count=args.profiles,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    print(json.dumps({"examples": example_count, **report.__dict__}, indent=2))
    print(json.dumps({"training_summary": training_summary}, indent=2))
    print(f"Saved scorer to {Path(args.output_dir)}")


if __name__ == "__main__":
    main()