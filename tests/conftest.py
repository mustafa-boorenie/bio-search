"""Shared fixtures for bio-search tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bio_search.models.analysis import AssociationResult, ConfidenceInterval, EWASResult


@pytest.fixture
def sample_df():
    """Synthetic NHANES-like DataFrame with known associations."""
    rng = np.random.default_rng(42)
    n = 500

    age = rng.normal(50, 15, n).clip(18, 85)
    sex = rng.choice([1, 2], n)
    race = rng.choice([1, 2, 3, 4, 6, 7], n)
    income = rng.uniform(0, 5, n)

    # True association: exposure_a → outcome with beta ≈ 2.0
    exposure_a = rng.normal(10, 3, n)
    outcome = 50 + 2.0 * exposure_a + 0.5 * age + rng.normal(0, 5, n)

    # Noise exposures
    noise_b = rng.normal(0, 1, n)
    noise_c = rng.normal(0, 1, n)
    noise_d = rng.normal(0, 1, n)
    noise_e = rng.normal(0, 1, n)

    # Binary outcome
    binary_outcome = (outcome > np.median(outcome)).astype(float)

    # Survey design columns
    strata = rng.choice(range(1, 16), n)
    psu = rng.choice([1, 2], n)
    weight = rng.uniform(1000, 50000, n)

    df = pd.DataFrame({
        "SEQN": range(1, n + 1),
        "RIDAGEYR": age,
        "RIAGENDR": sex.astype(float),
        "RIDRETH3": race.astype(float),
        "INDFMPIR": income,
        "EXPOSURE_A": exposure_a,
        "NOISE_B": noise_b,
        "NOISE_C": noise_c,
        "NOISE_D": noise_d,
        "NOISE_E": noise_e,
        "OUTCOME": outcome,
        "BINARY_OUTCOME": binary_outcome,
        "SDMVSTRA": strata.astype(float),
        "SDMVPSU": psu.astype(float),
        "WTMEC2YR": weight,
    })
    return df


@pytest.fixture
def sample_results():
    """Sample AssociationResult list for testing output/viz."""
    results = []
    rng = np.random.default_rng(99)
    for i in range(20):
        p = 10 ** rng.uniform(-8, -0.5)
        beta = rng.normal(0, 2)
        se = abs(beta) / max(abs(rng.normal(3, 1)), 0.5)
        results.append(AssociationResult(
            exposure=f"EXPOSURE_{i}",
            outcome="OUTCOME",
            beta=beta,
            se=se,
            p_value=p,
            ci=ConfidenceInterval(lower=beta - 1.96 * se, upper=beta + 1.96 * se),
            n=500,
            model_type="linear",
            fdr_p=p * 20 / (i + 1),
        ))
    return sorted(results, key=lambda r: r.p_value)


@pytest.fixture
def sample_ewas(sample_results):
    """Sample EWASResult for testing."""
    return EWASResult(
        outcome="OUTCOME",
        associations=sample_results,
        n_tests=20,
    )
