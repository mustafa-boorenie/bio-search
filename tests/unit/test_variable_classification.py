"""Tests for variable type classification."""

import pandas as pd

from bio_search.data.loader import DataLoader
from bio_search.models.nhanes import VariableType


class TestClassifyVariable:
    def test_seqn_is_identifier(self):
        s = pd.Series(range(100), name="SEQN")
        assert DataLoader.classify_variable(s) == VariableType.IDENTIFIER

    def test_strata_is_survey_design(self):
        s = pd.Series([1, 2, 3], name="SDMVSTRA")
        assert DataLoader.classify_variable(s) == VariableType.SURVEY_DESIGN

    def test_psu_is_survey_design(self):
        s = pd.Series([1, 2], name="SDMVPSU")
        assert DataLoader.classify_variable(s) == VariableType.SURVEY_DESIGN

    def test_weight_column(self):
        s = pd.Series([1000.0, 2000.0], name="WTMEC2YR")
        assert DataLoader.classify_variable(s) == VariableType.WEIGHT

    def test_binary_01(self):
        s = pd.Series([0, 1, 0, 1, 1], name="HAS_DIABETES")
        assert DataLoader.classify_variable(s) == VariableType.BINARY

    def test_binary_12(self):
        s = pd.Series([1, 2, 1, 2, 1], name="RIAGENDR")
        assert DataLoader.classify_variable(s) == VariableType.BINARY

    def test_categorical(self):
        s = pd.Series([1, 2, 3, 4, 5, 6, 7], name="RIDRETH3")
        assert DataLoader.classify_variable(s) == VariableType.CATEGORICAL

    def test_continuous(self):
        import numpy as np
        s = pd.Series(np.random.normal(10, 2, 100), name="LBXGLU")
        assert DataLoader.classify_variable(s) == VariableType.CONTINUOUS
