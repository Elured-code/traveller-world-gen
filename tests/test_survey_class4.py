"""Tests for TravellerSystem.to_survey_form_html_class4().

Verifies that the Class IV Survey form renders correctly with and without
social detail, and that all eight social-detail sections are represented
when full detail is attached.
"""
import random
import unittest
import unittest.mock as mock


def _make_world_data():
    from traveller_gen.traveller_map_fetch import MapWorldData
    return MapWorldData(
        name="Aegir",
        sector="Solomani Rim",
        hex_pos="1339",
        uwp="A76A885-D",
        bases="N S",
        remarks="Ri Wa Ht",
        zone="",
        pbg="502",
        stars_str="M2 V",
        worlds=5,
        cx="6B3B",
        importance=3,
    )


def _build_system(seed: int = 42, social: bool = True):
    from traveller_gen.traveller_map_fetch import generate_system_from_map
    from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
    data = _make_world_data()
    with mock.patch("traveller_gen.traveller_map_fetch.fetch_world_data", return_value=data):
        sys = generate_system_from_map("Aegir", sector="Solomani Rim", seed=seed)
    rng = random.Random(seed)
    run_detail_pipeline(sys, rng, PipelineOptions(
        want_detail=True, want_social_detail=social,
    ))
    return sys


class TestClass4FormBasic(unittest.TestCase):
    """Basic structural tests — the form must render without errors."""

    def test_returns_string(self):
        sys = _build_system()
        html = sys.to_survey_form_html_class4()
        assert isinstance(html, str) and len(html) > 100

    def test_valid_html_doctype(self):
        html = _build_system().to_survey_form_html_class4()
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_title_contains_world_name(self):
        html = _build_system().to_survey_form_html_class4()
        assert "Aegir" in html

    def test_form_header_text(self):
        html = _build_system().to_survey_form_html_class4()
        assert "Form 0407F-IV Part C" in html
        assert "IISS Class IV Survey" in html

    def test_uwp_in_output(self):
        html = _build_system().to_survey_form_html_class4()
        assert "A76A885-D" in html

    def test_no_exception_without_social_detail(self):
        sys = _build_system(social=False)
        html = sys.to_survey_form_html_class4()
        assert isinstance(html, str) and len(html) > 100

    def test_stub_text_when_no_social_detail(self):
        html = _build_system(social=False).to_survey_form_html_class4()
        assert "no population detail" in html
        assert "no government detail" in html

    def test_deterministic_repeated_calls(self):
        sys = _build_system(seed=99)
        html1 = sys.to_survey_form_html_class4()
        html2 = sys.to_survey_form_html_class4()
        assert html1 == html2, "Repeated calls on same system should produce identical HTML"


class TestClass4FormSections(unittest.TestCase):
    """Each social-detail section must appear in the rendered form."""

    def setUp(self):
        self.html = _build_system().to_survey_form_html_class4()

    def test_population_section(self):
        assert "POPULATION" in self.html.upper()

    def test_government_section(self):
        assert "GOVERNMENT" in self.html.upper()

    def test_law_section(self):
        assert "LAW LEVEL" in self.html.upper()

    def test_technology_section(self):
        assert "TECHNOLOGY" in self.html.upper()

    def test_culture_section(self):
        assert "CULTURE" in self.html.upper()

    def test_economics_section(self):
        assert "ECONOMICS" in self.html.upper()

    def test_starport_section(self):
        assert "STARPORT" in self.html.upper()

    def test_military_section(self):
        assert "MILITARY" in self.html.upper()


class TestClass4FormPopulation(unittest.TestCase):
    """Population section data."""

    def setUp(self):
        self.html = _build_system().to_survey_form_html_class4()

    def test_population_profile_present(self):
        assert "Population Profile" in self.html

    def test_urbanisation_field(self):
        assert "Urbanisation" in self.html

    def test_pcr_field(self):
        assert "PCR" in self.html


class TestClass4FormGovernment(unittest.TestCase):
    """Government section data."""

    def setUp(self):
        self.html = _build_system().to_survey_form_html_class4()

    def test_government_profile_field(self):
        assert "Government Profile" in self.html

    def test_centralisation_field(self):
        assert "Centralisation" in self.html

    def test_government_code_present(self):
        assert "Type" in self.html or "gov" in self.html.lower()


class TestClass4FormLaw(unittest.TestCase):
    """Law section data."""

    def setUp(self):
        self.html = _build_system().to_survey_form_html_class4()

    def test_law_profile_field(self):
        assert "Law Profile" in self.html

    def test_presumption_field(self):
        assert "Presumption" in self.html

    def test_death_penalty_field(self):
        assert "Death Penalty" in self.html

    def test_justice_profile_field(self):
        assert "Justice Profile" in self.html


class TestClass4FormTech(unittest.TestCase):
    """Technology section data."""

    def setUp(self):
        self.html = _build_system().to_survey_form_html_class4()

    def test_technology_profile_field(self):
        assert "Technology Profile" in self.html

    def test_tl_high_field(self):
        assert "TL High" in self.html

    def test_tl_space_field(self):
        assert "Space" in self.html


class TestClass4FormStarport(unittest.TestCase):
    """Starport section data including base codes."""

    def setUp(self):
        self.sys = _build_system()
        self.html = self.sys.to_survey_form_html_class4()

    def test_starport_profile_field(self):
        assert "Profile" in self.html

    def test_navy_base_shown(self):
        assert "Navy (N)" in self.html

    def test_scout_base_shown(self):
        assert "Scout (S)" in self.html

    def test_weekly_traffic_field(self):
        assert "Weekly Traffic" in self.html


class TestClass4FormMilitary(unittest.TestCase):
    """Military section data."""

    def setUp(self):
        self.html = _build_system().to_survey_form_html_class4()

    def test_military_profile_field(self):
        assert "Military Profile" in self.html

    def test_budget_pct_field(self):
        assert "Budget % GWP" in self.html

    def test_enforcement_branch(self):
        assert "Enforcement" in self.html

    def test_navy_branch(self):
        assert "Navy" in self.html


class TestClass4FormEconomics(unittest.TestCase):
    """Economics section data."""

    def setUp(self):
        self.html = _build_system().to_survey_form_html_class4()

    def test_importance_field(self):
        assert "Importance" in self.html

    def test_trade_codes_field(self):
        assert "Trade Codes" in self.html

    def test_ru_field(self):
        assert "RU" in self.html

    def test_gwp_per_capita_field(self):
        assert "GWP/Capita" in self.html

    def test_wtn_field(self):
        assert "WTN" in self.html


if __name__ == "__main__":
    unittest.main()
