"""Shared dependency exposing the startup-loaded XGBoost eligibility scorer."""

from fastapi import Request

from eligibility.persistence import SavedScorer


def get_eligibility_scorer(request: Request) -> SavedScorer:
    return request.app.state.eligibility_scorer
