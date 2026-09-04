"""Save and load the trained XGBoost confidence scorer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from xgboost import XGBClassifier

from data.features import FEATURE_COLUMNS


@dataclass
class SavedScorer:
    model: XGBClassifier
    feature_columns: list[str]

    def predict_confidence(self, feature_row: dict[str, Any]) -> float:
        frame = pd.DataFrame([feature_row], columns=self.feature_columns, dtype="float64")
        return float(self.model.predict_proba(frame)[0][1])


def save_scorer(model: XGBClassifier, out_dir: str | Path) -> None:
    """Persist the model and the feature-column order used to train it."""

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(str(output_dir / "scorer.json"))

    metadata = {"feature_columns": list(FEATURE_COLUMNS)}
    (output_dir / "scorer_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def load_scorer(model_dir: str | Path) -> SavedScorer:
    """Load a scorer and reject artifacts with an incompatible feature contract."""

    model_dir_path = Path(model_dir)
    model = XGBClassifier()
    model.load_model(str(model_dir_path / "scorer.json"))
    metadata = json.loads(
        (model_dir_path / "scorer_metadata.json").read_text(encoding="utf-8")
    )
    feature_columns = metadata.get("feature_columns")
    if feature_columns != list(FEATURE_COLUMNS):
        raise ValueError("saved scorer feature columns do not match the current feature contract")

    return SavedScorer(model=model, feature_columns=feature_columns)