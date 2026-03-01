"""Tests for survey weight selection and adjustment."""

import numpy as np
import pandas as pd

from bio_search.models.nhanes import DataComponent
from bio_search.survey.weights import WeightSelector


class TestWeightSelector:
    def test_lab_uses_mec(self):
        w = WeightSelector.select_weight({DataComponent.LABORATORY})
        assert w == "WTMEC2YR"

    def test_exam_uses_mec(self):
        w = WeightSelector.select_weight({DataComponent.EXAMINATION})
        assert w == "WTMEC2YR"

    def test_questionnaire_uses_interview(self):
        w = WeightSelector.select_weight({DataComponent.QUESTIONNAIRE})
        assert w == "WTINT2YR"

    def test_demographics_uses_interview(self):
        w = WeightSelector.select_weight({DataComponent.DEMOGRAPHICS})
        assert w == "WTINT2YR"

    def test_mixed_uses_mec(self):
        """If any component requires MEC, use MEC weight."""
        w = WeightSelector.select_weight(
            {DataComponent.QUESTIONNAIRE, DataComponent.LABORATORY}
        )
        assert w == "WTMEC2YR"

    def test_adjust_single_cycle_no_change(self):
        df = pd.DataFrame({"WTMEC2YR": [1000.0, 2000.0, 3000.0]})
        result = WeightSelector.adjust_for_cycles(df, "WTMEC2YR", 1)
        np.testing.assert_array_equal(result["WTMEC2YR"].values, [1000, 2000, 3000])

    def test_adjust_two_cycles(self):
        df = pd.DataFrame({"WTMEC2YR": [1000.0, 2000.0, 3000.0]})
        result = WeightSelector.adjust_for_cycles(df, "WTMEC2YR", 2)
        np.testing.assert_array_almost_equal(
            result["WTMEC2YR"].values, [500, 1000, 1500]
        )
