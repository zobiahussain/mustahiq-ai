"""Train the synthetic eligibility confidence scorer and save its artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.features import build_feature_row
from data.synthetic import (
    build_synthetic_programs,
    generate_labeled_dataset,
    generate_synthetic_profiles,
)

from eligibility.persistence import save_scorer
from eligibility.scoring import train_and_evaluate


def train_synthetic_scorer(
    *,
    profile_count: int = 3_000,
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
    save_scorer(model, output_dir)
    return report, len(examples)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=int, default=3_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="artifacts/eligibility-scorer")
    args = parser.parse_args()

    report, example_count = train_synthetic_scorer(
        profile_count=args.profiles,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    print(json.dumps({"examples": example_count, **report.__dict__}, indent=2))
    print(f"Saved scorer to {Path(args.output_dir)}")


if __name__ == "__main__":
    main()