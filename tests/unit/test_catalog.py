"""Tests for NHANES catalog."""

from bio_search.data.catalog import NHANESCatalog


class TestNHANESCatalog:
    def test_has_cycles(self):
        catalog = NHANESCatalog()
        cycles = catalog.get_cycles()
        assert len(cycles) >= 5
        assert "2021-2023" in cycles
        assert "2017-2018" in cycles

    def test_tables_per_cycle(self):
        catalog = NHANESCatalog()
        tables = catalog.get_tables("2017-2018")
        assert len(tables) > 10
        names = [t.name for t in tables]
        assert "DEMO_J" in names

    def test_get_table(self):
        catalog = NHANESCatalog()
        table = catalog.get_table("2017-2018", "DEMO_J")
        assert table is not None
        assert table.name == "DEMO_J"
        assert "wwwn.cdc.gov" in table.xpt_url

    def test_get_table_missing(self):
        catalog = NHANESCatalog()
        table = catalog.get_table("2017-2018", "NONEXISTENT")
        assert table is None

    def test_search_variables(self):
        catalog = NHANESCatalog()
        results = catalog.search_variables("glucose")
        assert len(results) > 0
        # All results should mention glucose in name or label
        for v in results:
            assert "glu" in v.name.lower() or "glucose" in v.label.lower()

    def test_xpt_url_format(self):
        catalog = NHANESCatalog()
        tables = catalog.get_all_tables()
        for t in tables:
            assert t.xpt_url.endswith(".XPT")
            assert t.xpt_url.startswith("https://")
