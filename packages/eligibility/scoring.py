"""Train and use the XGBoost confidence model after hard-rule evaluation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold
from xgboost import XGBClassifier

from data.features import build_feature_frame


@dataclass(frozen=True)
class EvaluationReport:
    precision: float
    recall: float
    f1: float
    confusion_matrix: list[list[int]]
    train_size: int
    test_size: int
    train_profile_count: int
    test_profile_count: int
    positive_rate: float


def _classifier(*, scale_pos_weight: float) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=42,
        n_jobs=1,
    )


def train_and_evaluate(
    feature_rows: Sequence[dict[str, Any]],
    labels: Sequence[bool],
    profile_groups: Sequence[int],
) -> tuple[XGBClassifier, EvaluationReport]:
    """Train with an 80/20 stratified split that never shares a profile.

    A beneficiary can produce several program examples. Grouping by profile
    prevents those near-identical examples from leaking into the held-out set.
    """

    if len(feature_rows) != len(labels) or len(labels) != len(profile_groups):
        raise ValueError("feature_rows, labels, and profile_groups must have equal length")
    if len(feature_rows) < 10 or len(set(labels)) != 2:
        raise ValueError("training requires at least 10 examples containing both label classes")
    if len(set(profile_groups)) < 5:
        raise ValueError("training requires examples from at least five profiles")

    frame = build_feature_frame(feature_rows)
    target = [int(label) for label in labels]
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    train_indices, test_indices = next(splitter.split(frame, target, groups=profile_groups))

    train_frame = frame.iloc[train_indices]
    test_frame = frame.iloc[test_indices]
    train_labels = [target[index] for index in train_indices]
    test_labels = [target[index] for index in test_indices]
    train_groups = {profile_groups[index] for index in train_indices}
    test_groups = {profile_groups[index] for index in test_indices}
    if train_groups & test_groups:
        raise RuntimeError("profile leakage detected in train/test split")

    positive = sum(train_labels)
    negative = len(train_labels) - positive
    if positive == 0 or negative == 0:
        raise ValueError("training split must contain both label classes")

    model = _classifier(scale_pos_weight=negative / positive)
    model.fit(train_frame, train_labels)
    predictions = model.predict(test_frame)
    matrix = confusion_matrix(test_labels, predictions, labels=[0, 1]).tolist()

    report = EvaluationReport(
        precision=float(precision_score(test_labels, predictions, zero_division=0)),
        recall=float(recall_score(test_labels, predictions, zero_division=0)),
        f1=float(f1_score(test_labels, predictions, zero_division=0)),
        confusion_matrix=matrix,
        train_size=len(train_indices),
        test_size=len(test_indices),
        train_profile_count=len(train_groups),
        test_profile_count=len(test_groups),
        positive_rate=sum(target) / len(target),
    )
    return model, report


def predict_confidence(model: XGBClassifier, feature_row: dict[str, Any]) -> float:
    """Return the confidence stored on a discovery match after hard-rule pass."""

    return float(model.predict_proba(build_feature_frame([feature_row]))[0][1])
