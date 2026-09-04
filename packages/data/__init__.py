"""Synthetic data and feature-building utilities for the eligibility engine."""

from .features import FEATURE_COLUMNS, build_feature_frame, build_feature_row
from .synthetic import (
    LabeledExample,
    SyntheticProgram,
    build_synthetic_programs,
    generate_labeled_dataset,
    generate_synthetic_profiles,
)

__all__ = [
    "FEATURE_COLUMNS",
    "LabeledExample",
    "SyntheticProgram",
    "build_feature_frame",
    "build_feature_row",
    "build_synthetic_programs",
    "generate_labeled_dataset",
    "generate_synthetic_profiles",
]
