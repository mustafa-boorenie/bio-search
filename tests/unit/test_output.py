"""Tests for output modules."""

import json
import tempfile
from pathlib import Path

from bio_search.output.report import ReportGenerator
from bio_search.output.structured import StructuredExporter


class TestStructuredExporter:
    def test_to_csv(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = StructuredExporter(output_dir=Path(tmpdir))
            path = exporter.to_csv(sample_results)
            assert path.exists()
            content = path.read_text()
            lines = content.strip().split("\n")
            assert len(lines) == len(sample_results) + 1  # header + data
            assert "exposure" in lines[0]

    def test_to_json(self, sample_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = StructuredExporter(output_dir=Path(tmpdir))
            path = exporter.to_json(sample_results)
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["n_results"] == len(sample_results)
            assert len(data["results"]) == len(sample_results)

    def test_ewas_to_csv(self, sample_ewas):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = StructuredExporter(output_dir=Path(tmpdir))
            path = exporter.ewas_to_csv(sample_ewas)
            assert path.exists()
            assert "ewas_OUTCOME" in path.name


class TestReportGenerator:
    def test_generate_text_report(self, sample_ewas):
        gen = ReportGenerator()
        report = gen.generate_text_report(sample_ewas)
        assert "OUTCOME" in report
        assert "Total exposures tested" in report

    def test_save_report(self, sample_ewas):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator(output_dir=Path(tmpdir))
            path = gen.save_report(sample_ewas)
            assert path.exists()
            content = path.read_text()
            assert "EWAS Report" in content
