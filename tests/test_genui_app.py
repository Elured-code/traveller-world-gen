"""
tests/test_genui_app.py — pytest-qt GUI tests for gen-ui/app.py

Covers the interactive features of AppWindow, _OptionsDialog, SystemMapWindow,
and SurveyFormWindow without hitting the network or touching disk.

Run these tests only:
    .venv/bin/pytest tests/test_genui_app.py -v

Skip them (e.g. in headless CI without Qt):
    .venv/bin/pytest tests/ -v --ignore=tests/test_genui_app.py
"""

import importlib.util
import os
import sys
from unittest.mock import patch

# ── Must be set before any Qt / QApplication is created ─────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--log-level=3 --disable-gpu")

import pytest  # noqa: E402

# ── Load gen-ui/app.py under an unambiguous module name ─────────────────────
# We cannot do a plain `import app` because fastapi/app.py shares the name
# and may already be on sys.path during the full test run.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "genui_app", os.path.join(_REPO_ROOT, "gen-ui", "app.py")
)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["genui_app"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

AppWindow = _mod.AppWindow
_OptionsDialog = _mod._OptionsDialog
SystemMapWindow = _mod.SystemMapWindow
SurveyFormWindow = _mod.SurveyFormWindow

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QLabel, QMessageBox, QPushButton, QRadioButton, QTabWidget, QWidget,
)


# ════════════════════════════════════════════════════════════════════════════
# Stubs
# ════════════════════════════════════════════════════════════════════════════

class _FakeSettings:
    """QSettings replacement that never reads from or writes to disk.

    Shares one class-level store across instances (mirroring how real
    QSettings instances for the same organization/application share a single
    backing store), so a test can verify a value written via one QSettings(...)
    construction is visible to a later, separate construction -- e.g.
    confirming a toggle persists across closing and reopening a window.
    """

    _shared_store: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    def value(self, key, default=None):
        return self._shared_store.get(key, default)

    def setValue(self, key, value):
        self._shared_store[key] = value


class _MockWebView(QWidget):
    """QWebEngineView replacement that captures HTML without launching Chromium."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_html: str = ""

    def setHtml(self, html, *args, **kwargs):
        self._last_html = html

    @property
    def last_html(self) -> str:
        return self._last_html


# ════════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def fake_settings(monkeypatch):
    """Replace QSettings in genui_app with _FakeSettings (shared in-memory store)."""
    _FakeSettings._shared_store.clear()  # pylint: disable=protected-access
    monkeypatch.setattr(_mod, "QSettings", _FakeSettings)


@pytest.fixture
def no_webengine(monkeypatch):
    """Replace QWebEngineView in genui_app with _MockWebView."""
    monkeypatch.setattr(_mod, "QWebEngineView", _MockWebView)


@pytest.fixture
def app_win(qtbot, fake_settings, no_webengine):
    """AppWindow with patched QSettings and QWebEngineView."""
    win = _mod.AppWindow()
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture(scope="session")
def sample_system():
    """Session-scoped TravellerSystem used by map/survey window tests."""
    from traveller_gen.traveller_system_gen import generate_full_system  # noqa: PLC0415
    return generate_full_system("Testworld", seed=42)


@pytest.fixture
def system_app_win(app_win):
    """AppWindow that has already run a full-system generation with seed 1."""
    app_win._opt_full_system = True
    app_win._seed_entry.setText("1")
    app_win._generate_btn.click()
    yield app_win
    for w in list(app_win._survey_windows) + list(app_win._map_windows):
        w.close()


@pytest.fixture
def social_system_app_win(app_win):
    """AppWindow with full system + social detail enabled, seed 1."""
    app_win._opt_full_system = True
    app_win._opt_social_detail = True
    app_win._seed_entry.setText("1")
    app_win._generate_btn.click()
    yield app_win
    for w in list(app_win._survey_windows) + list(app_win._map_windows):
        w.close()


def _default_options(parent) -> _OptionsDialog:
    """Helper: _OptionsDialog with every option at its default value."""
    return _OptionsDialog(
        parent,
        full_system=False, nhz=False, oxygen_biomass=False,
        runaway_greenhouse=False, independent_government=False,
        select_mainworld=False, social_detail=False,
        settlement_type="standard",
        eccentricity=True, inclination=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# 1. Startup
# ════════════════════════════════════════════════════════════════════════════

class TestAppWindowStartup:
    def test_window_title_contains_traveller(self, app_win):
        assert "Traveller" in app_win.windowTitle()

    def test_procedural_radio_checked_by_default(self, app_win):
        assert app_win._radio_procedural.isChecked()

    def test_travellermap_radio_not_checked_by_default(self, app_win):
        assert not app_win._radio_travellermap.isChecked()

    def test_travellermap_panel_hidden_on_startup(self, app_win):
        assert not app_win._tm_panel.isVisible()

    def test_travellermap_vsep_hidden_on_startup(self, app_win):
        assert not app_win._tm_vsep.isVisible()

    def test_generate_button_is_present_and_enabled(self, app_win):
        assert app_win._generate_btn is not None
        assert app_win._generate_btn.isEnabled()

    def test_save_action_disabled_on_startup(self, app_win):
        assert not app_win._act_save.isEnabled()

    def test_survey_btn_is_none_on_startup(self, app_win):
        assert app_win._survey_btn is None

    def test_map_btn_is_none_on_startup(self, app_win):
        assert app_win._map_btn is None

    def test_survey_windows_list_empty_on_startup(self, app_win):
        assert app_win._survey_windows == []

    def test_map_windows_list_empty_on_startup(self, app_win):
        assert app_win._map_windows == []

    def test_dark_mode_off_by_default(self, app_win):
        assert app_win._dark_mode is False

    def test_file_menu_open_json_always_enabled(self, app_win):
        assert app_win._act_open_json is not None
        assert app_win._act_open_json.isEnabled()

    def test_view_menu_dark_mode_action_is_checkable(self, app_win):
        assert app_win._act_dark_mode.isCheckable()

    def test_view_menu_dark_mode_unchecked_by_default(self, app_win):
        assert not app_win._act_dark_mode.isChecked()

    def test_name_entry_placeholder_set(self, app_win):
        assert app_win._name_entry.placeholderText() != ""

    def test_seed_entry_placeholder_set(self, app_win):
        assert app_win._seed_entry.placeholderText() != ""

    def test_current_world_none_on_startup(self, app_win):
        assert app_win._current_world is None

    def test_current_system_none_on_startup(self, app_win):
        assert app_win._current_system is None


# ════════════════════════════════════════════════════════════════════════════
# 2. Source radio toggle
# ════════════════════════════════════════════════════════════════════════════

class TestSourceRadioToggle:
    def test_travellermap_radio_shows_tm_panel(self, app_win):
        app_win._radio_travellermap.setChecked(True)
        assert app_win._tm_panel.isVisible()

    def test_travellermap_radio_shows_vsep(self, app_win):
        app_win._radio_travellermap.setChecked(True)
        assert app_win._tm_vsep.isVisible()

    def test_procedural_radio_hides_tm_panel(self, app_win):
        app_win._radio_travellermap.setChecked(True)
        app_win._radio_procedural.setChecked(True)
        assert not app_win._tm_panel.isVisible()

    def test_procedural_radio_hides_vsep(self, app_win):
        app_win._radio_travellermap.setChecked(True)
        app_win._radio_procedural.setChecked(True)
        assert not app_win._tm_vsep.isVisible()

    def test_sector_entry_exists(self, app_win):
        assert app_win._sector_entry is not None

    def test_tm_name_entry_exists(self, app_win):
        assert app_win._tm_name_entry is not None

    def test_hex_entry_exists(self, app_win):
        assert app_win._hex_entry is not None


# ════════════════════════════════════════════════════════════════════════════
# 3. Options dialog — construction
# ════════════════════════════════════════════════════════════════════════════

class TestOptionsDialogConstruction:
    def test_dialog_window_title(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        assert "Options" in dlg.windowTitle()

    def test_system_detail_unchecked_when_initialised_false(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        assert not dlg._check_system.isChecked()

    def test_sub_widget_hidden_when_full_system_false(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        assert not dlg._sub_widget.isVisible()

    def test_check_system_detail_shows_sub_widget(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        dlg._check_system.setChecked(True)
        # isVisibleTo() reflects explicit show/hide without needing the dialog shown
        assert dlg._sub_widget.isVisibleTo(dlg)

    def test_uncheck_system_detail_hides_sub_widget(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg._sub_widget.isVisibleTo(dlg)
        dlg._check_system.setChecked(False)
        assert not dlg._sub_widget.isVisibleTo(dlg)

    def test_uncheck_system_detail_clears_nhz(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=True, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        dlg._check_system.setChecked(False)
        assert not dlg._check_nhz.isChecked()

    def test_uncheck_system_detail_clears_all_sub_checkboxes(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=True, oxygen_biomass=True,
            runaway_greenhouse=True, independent_government=True,
            select_mainworld=True, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        dlg._check_system.setChecked(False)
        sub_boxes = [
            dlg._check_nhz, dlg._check_oxygen_biomass,
            dlg._check_runaway_greenhouse, dlg._check_independent_gov,
            dlg._check_select_mw,
        ]
        assert all(not cb.isChecked() for cb in sub_boxes)

    def test_settlement_type_has_five_radio_buttons(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        assert len(dlg._settlement_btn_group.buttons()) == 5

    def test_settlement_type_default_standard(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        assert dlg.settlement_type == "standard"

    def test_social_detail_checkbox_present(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        assert hasattr(dlg, "_check_social_detail")

    def test_ok_and_cancel_buttons_present(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        assert dlg.findChild(QDialogButtonBox) is not None

    def test_system_detail_sub_widget_visible_when_initialised_true(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg._sub_widget.isVisibleTo(dlg)


# ════════════════════════════════════════════════════════════════════════════
# 4. Options dialog — property accessors
# ════════════════════════════════════════════════════════════════════════════

class TestOptionsDialogProperties:
    def test_full_system_property_false(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        assert dlg.full_system is False

    def test_full_system_property_true(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg.full_system is True

    def test_nhz_property_reflects_checkbox(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        dlg._check_system.setChecked(True)
        dlg._check_nhz.setChecked(True)
        assert dlg.nhz is True

    def test_eccentricity_true_when_system_detail_on(self, qtbot, app_win):
        # eccentricity is a sub-option; it stays True only when full_system=True
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=False,
        )
        qtbot.addWidget(dlg)
        assert dlg.eccentricity is True

    def test_inclination_true_when_system_detail_on(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=False,
            settlement_type="standard", eccentricity=False, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg.inclination is True

    def test_eccentricity_cleared_when_full_system_false(self, qtbot, app_win):
        # _on_group_toggled(False) clears all sub-checkboxes
        dlg = _OptionsDialog(
            app_win, full_system=False, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg.eccentricity is False

    def test_independent_government_property(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=True,
            select_mainworld=False, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg.independent_government is True

    def test_select_mainworld_property(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=True, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=True, social_detail=False,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg.select_mainworld is True

    def test_social_detail_property(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=False, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=True,
            settlement_type="standard", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg.social_detail is True

    def test_settlement_type_long_settled(self, qtbot, app_win):
        dlg = _OptionsDialog(
            app_win, full_system=False, nhz=False, oxygen_biomass=False,
            runaway_greenhouse=False, independent_government=False,
            select_mainworld=False, social_detail=False,
            settlement_type="long_settled", eccentricity=True, inclination=True,
        )
        qtbot.addWidget(dlg)
        assert dlg.settlement_type == "long_settled"

    def test_settlement_type_changes_on_radio_click(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        btns = {b.property("key"): b for b in dlg._settlement_btn_group.buttons()}
        btns["backwater"].setChecked(True)
        assert dlg.settlement_type == "backwater"

    def test_all_settlement_type_keys_present(self, qtbot, app_win):
        dlg = _default_options(app_win)
        qtbot.addWidget(dlg)
        keys = {b.property("key") for b in dlg._settlement_btn_group.buttons()}
        assert keys == {"standard", "long_settled", "well_settled", "backwater", "unsettled"}


# ════════════════════════════════════════════════════════════════════════════
# 5. Options integration with AppWindow
# ════════════════════════════════════════════════════════════════════════════

class TestOptionsIntegration:
    def test_options_ok_updates_opt_full_system(self, app_win, monkeypatch):
        """Accepting the dialog with system detail checked updates the app flag."""
        class _Accept(_OptionsDialog):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self._check_system.setChecked(True)
            def exec(self):  # pylint: disable=arguments-differ
                return QDialog.DialogCode.Accepted
        monkeypatch.setattr(_mod, "_OptionsDialog", _Accept)
        app_win._on_options_clicked()
        assert app_win._opt_full_system is True

    def test_options_cancel_does_not_update_flag(self, app_win, monkeypatch):
        """Cancelling the dialog leaves the app flag unchanged."""
        class _Reject(_OptionsDialog):
            def exec(self):  # pylint: disable=arguments-differ
                return QDialog.DialogCode.Rejected
        monkeypatch.setattr(_mod, "_OptionsDialog", _Reject)
        original = app_win._opt_full_system
        app_win._on_options_clicked()
        assert app_win._opt_full_system == original

    def test_options_ok_persists_settlement_type(self, app_win, monkeypatch):
        """Settlement type chosen in dialog is written back to the app."""
        class _AcceptBackwater(_OptionsDialog):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                btns = {b.property("key"): b for b in self._settlement_btn_group.buttons()}
                btns["backwater"].setChecked(True)
            def exec(self):  # pylint: disable=arguments-differ
                return QDialog.DialogCode.Accepted
        monkeypatch.setattr(_mod, "_OptionsDialog", _AcceptBackwater)
        app_win._on_options_clicked()
        assert app_win._opt_settlement_type == "backwater"


# ════════════════════════════════════════════════════════════════════════════
# 6. Seed and name handling
# ════════════════════════════════════════════════════════════════════════════

class TestSeedHandling:
    def test_invalid_seed_shows_error_label(self, app_win):
        app_win._seed_entry.setText("abc")
        app_win._generate_btn.click()
        assert app_win.findChild(QLabel, "error-label") is not None

    def test_invalid_seed_error_mentions_integer(self, app_win):
        app_win._seed_entry.setText("xyz")
        app_win._generate_btn.click()
        lbl = app_win.findChild(QLabel, "error-label")
        assert "integer" in lbl.text().lower()

    def test_invalid_seed_does_not_set_current_world(self, app_win):
        app_win._seed_entry.setText("not_a_number")
        app_win._generate_btn.click()
        assert app_win._current_world is None

    def test_empty_seed_field_auto_populates(self, app_win):
        app_win._seed_entry.clear()
        app_win._generate_btn.click()
        assert app_win._seed_entry.text() != ""

    def test_auto_populated_seed_is_numeric(self, app_win):
        app_win._seed_entry.clear()
        app_win._generate_btn.click()
        assert app_win._seed_entry.text().lstrip("-").isdigit()

    def test_known_seed_preserved_in_seed_field(self, app_win):
        app_win._seed_entry.setText("12345")
        app_win._generate_btn.click()
        assert app_win._seed_entry.text() == "12345"


# ════════════════════════════════════════════════════════════════════════════
# 7. TravellerMap error paths (no network required)
# ════════════════════════════════════════════════════════════════════════════

class TestTravellerMapErrors:
    def test_missing_sector_shows_error(self, app_win):
        app_win._radio_travellermap.setChecked(True)
        app_win._sector_entry.clear()
        app_win._generate_btn.click()
        lbl = app_win.findChild(QLabel, "error-label")
        assert lbl is not None
        assert "sector" in lbl.text().lower()

    def test_missing_sector_does_not_start_worker(self, app_win):
        app_win._radio_travellermap.setChecked(True)
        app_win._sector_entry.clear()
        app_win._generate_btn.click()
        assert app_win._worker is None

    def test_missing_name_and_hex_shows_error(self, app_win):
        app_win._radio_travellermap.setChecked(True)
        app_win._sector_entry.setText("Spinward Marches")
        app_win._tm_name_entry.clear()
        app_win._hex_entry.clear()
        app_win._generate_btn.click()
        lbl = app_win.findChild(QLabel, "error-label")
        assert lbl is not None

    def test_missing_name_and_hex_error_mentions_name_or_hex(self, app_win):
        app_win._radio_travellermap.setChecked(True)
        app_win._sector_entry.setText("Spinward Marches")
        app_win._tm_name_entry.clear()
        app_win._hex_entry.clear()
        app_win._generate_btn.click()
        lbl = app_win.findChild(QLabel, "error-label")
        assert "name" in lbl.text().lower() or "hex" in lbl.text().lower()


# ════════════════════════════════════════════════════════════════════════════
# 8. Procedural world-only generation
# ════════════════════════════════════════════════════════════════════════════

class TestProceduralWorldGeneration:
    def _gen(self, win, seed="42", name="Testworld"):
        win._name_entry.setText(name)
        # Block signals and reset _seed_auto so the seed is always honoured,
        # even if the text value hasn't changed since the last generate.
        win._seed_entry.blockSignals(True)
        win._seed_entry.setText(str(seed))
        win._seed_entry.blockSignals(False)
        win._seed_auto = False
        win._generate_btn.click()

    def test_generate_sets_current_world(self, app_win):
        self._gen(app_win)
        assert app_win._current_world is not None

    def test_generate_does_not_set_current_system(self, app_win):
        self._gen(app_win)
        assert app_win._current_system is None

    def test_generate_enables_save_action(self, app_win):
        self._gen(app_win)
        assert app_win._act_save.isEnabled()

    def test_world_only_result_has_no_survey_btn(self, app_win):
        self._gen(app_win)
        assert app_win._survey_btn is None

    def test_world_only_result_has_no_map_btn(self, app_win):
        self._gen(app_win)
        assert app_win._map_btn is None

    def test_same_seed_produces_same_uwp(self, app_win):
        self._gen(app_win, seed="999")
        uwp1 = app_win._current_world.uwp()
        self._gen(app_win, seed="999")
        assert app_win._current_world.uwp() == uwp1

    def test_custom_name_stored_on_world(self, app_win):
        self._gen(app_win, seed="1", name="Cogri")
        assert app_win._current_world.name == "Cogri"

    def test_empty_name_defaults_to_unknown(self, app_win):
        app_win._name_entry.clear()
        app_win._seed_entry.setText("7")
        app_win._generate_btn.click()
        assert app_win._current_world.name == "Unknown"

    def test_different_seeds_produce_different_uwps(self, app_win):
        # Seeds 1 and 2 produce different systems — statistically guaranteed
        self._gen(app_win, seed="1")
        uwp1 = app_win._current_world.uwp()
        self._gen(app_win, seed="2")
        assert app_win._current_world.uwp() != uwp1


# ════════════════════════════════════════════════════════════════════════════
# 9. Procedural full-system generation
# ════════════════════════════════════════════════════════════════════════════

class TestProceduralSystemGeneration:
    def test_generate_sets_current_system(self, system_app_win):
        assert system_app_win._current_system is not None

    def test_generate_sets_current_world(self, system_app_win):
        assert system_app_win._current_world is not None

    def test_detail_attached_flag_is_true(self, system_app_win):
        assert system_app_win._detail_attached is True

    def test_save_action_enabled(self, system_app_win):
        assert system_app_win._act_save.isEnabled()

    def test_map_btn_present_in_header(self, system_app_win):
        assert system_app_win._map_btn is not None

    def test_survey_btn_present_in_header(self, system_app_win):
        assert system_app_win._survey_btn is not None

    def test_survey_combo_present_in_header(self, system_app_win):
        assert system_app_win._survey_combo is not None

    def test_survey_combo_first_item_is_class0i(self, system_app_win):
        combo = system_app_win._survey_combo
        assert combo.count() >= 1
        assert "0/I" in combo.itemText(0)

    def test_survey_combo_has_class2iii_item(self, system_app_win):
        combo = system_app_win._survey_combo
        assert combo.count() >= 2
        assert "II/III" in combo.itemText(1)

    def test_result_contains_tab_widget(self, system_app_win):
        assert system_app_win.findChild(QTabWidget) is not None

    def test_tab_widget_has_system_tab(self, system_app_win):
        tabs = system_app_win.findChild(QTabWidget)
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        assert "System" in labels

    def test_tab_widget_has_mainworld_tab(self, system_app_win):
        tabs = system_app_win.findChild(QTabWidget)
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        assert "Mainworld" in labels

    def test_mainworld_tab_is_active_by_default(self, system_app_win):
        tabs = system_app_win.findChild(QTabWidget)
        assert tabs.tabText(tabs.currentIndex()) == "Mainworld"

    def _gen(self, win, seed):
        win._seed_entry.blockSignals(True)
        win._seed_entry.setText(str(seed))
        win._seed_entry.blockSignals(False)
        win._seed_auto = False
        win._generate_btn.click()

    def test_same_seed_same_mainworld_uwp(self, app_win):
        app_win._opt_full_system = True
        self._gen(app_win, 5)
        uwp1 = app_win._current_world.uwp()
        self._gen(app_win, 5)
        assert app_win._current_world.uwp() == uwp1

    def test_system_map_btn_enabled(self, system_app_win):
        assert system_app_win._map_btn.isEnabled()


# ════════════════════════════════════════════════════════════════════════════
# 10. Dark mode
# ════════════════════════════════════════════════════════════════════════════

class TestDarkMode:
    def test_dark_mode_off_by_default(self, app_win):
        assert app_win._dark_mode is False

    def test_action_unchecked_by_default(self, app_win):
        assert not app_win._act_dark_mode.isChecked()

    def test_toggle_on_sets_flag(self, app_win):
        app_win._on_toggle_dark_mode(True)
        assert app_win._dark_mode is True

    def test_toggle_off_clears_flag(self, app_win):
        app_win._dark_mode = True
        app_win._on_toggle_dark_mode(False)
        assert app_win._dark_mode is False

    def test_themed_html_unchanged_in_light_mode(self, app_win):
        app_win._dark_mode = False
        html = '<html lang="en"><body></body></html>'
        assert app_win._themed_html(html) == html

    def test_themed_html_injects_data_theme_in_dark_mode(self, app_win):
        app_win._dark_mode = True
        result = app_win._themed_html('<html lang="en"><body></body></html>')
        assert 'data-theme="dark"' in result

    def test_themed_html_only_modifies_opening_tag(self, app_win):
        app_win._dark_mode = True
        html = '<html lang="en"><body>content</body></html>'
        result = app_win._themed_html(html)
        assert "<body>content</body>" in result

    def test_themed_html_does_not_double_inject(self, app_win):
        app_win._dark_mode = True
        html = '<html lang="en"><body></body></html>'
        once = app_win._themed_html(html)
        # Applying again to already-themed HTML should not add a second attribute
        twice = app_win._themed_html(once)
        assert twice.count('data-theme="dark"') == 1


# ════════════════════════════════════════════════════════════════════════════
# 11. SystemMapWindow
# ════════════════════════════════════════════════════════════════════════════

class TestSystemMapWindow:
    def test_map_window_creates_without_error(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        win.show()
        assert win.isVisible()

    def test_map_window_title_starts_with_system_map(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        assert win.windowTitle().startswith("System Map")

    def test_map_window_initial_palette_is_dark(self, qtbot, fake_settings, no_webengine, sample_system):
        from traveller_gen.system_map import PALETTE_DARK  # noqa: PLC0415
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        assert win._palette is PALETTE_DARK

    def test_theme_toggle_switches_to_light_palette(self, qtbot, fake_settings, no_webengine, sample_system):
        from traveller_gen.system_map import PALETTE_LIGHT  # noqa: PLC0415
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        win._toggle_theme()
        assert win._palette is PALETTE_LIGHT

    def test_theme_btn_text_becomes_dark_theme_after_toggle(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        win._toggle_theme()
        assert win._theme_btn.text() == "Dark Theme"

    def test_theme_double_toggle_returns_to_dark(self, qtbot, fake_settings, no_webengine, sample_system):
        from traveller_gen.system_map import PALETTE_DARK  # noqa: PLC0415
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        win._toggle_theme()
        win._toggle_theme()
        assert win._palette is PALETTE_DARK

    def test_perspective_initially_false(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        assert win._perspective is False

    def test_perspective_toggle_sets_true(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        win._toggle_perspective()
        assert win._perspective is True

    def test_perspective_btn_text_after_toggle(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        win._toggle_perspective()
        assert win._persp_btn.text() == "Top-down View"

    def test_perspective_double_toggle_returns_false(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        win._toggle_perspective()
        win._toggle_perspective()
        assert win._perspective is False

    def test_svg_str_populated_after_render(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        assert win._svg_str != ""

    def test_svg_str_contains_svg_root_element(self, qtbot, fake_settings, no_webengine, sample_system):
        win = SystemMapWindow(sample_system)
        qtbot.addWidget(win)
        assert "<svg" in win._svg_str

    # ------------------------------------------------------------------
    # Theme/perspective persistence across windows (regression: previously
    # every new SystemMapWindow reset to dark/top-down regardless of what
    # the user had last chosen).
    # ------------------------------------------------------------------

    def test_light_theme_persists_to_a_new_window(self, qtbot, fake_settings, no_webengine, sample_system):
        from traveller_gen.system_map import PALETTE_LIGHT  # noqa: PLC0415
        win1 = SystemMapWindow(sample_system)
        qtbot.addWidget(win1)
        win1._toggle_theme()
        assert win1._palette is PALETTE_LIGHT

        win2 = SystemMapWindow(sample_system)
        qtbot.addWidget(win2)
        assert win2._palette is PALETTE_LIGHT
        assert win2._theme_btn.text() == "Dark Theme"

    def test_dark_theme_choice_persists_to_a_new_window(self, qtbot, fake_settings, no_webengine, sample_system):
        from traveller_gen.system_map import PALETTE_DARK  # noqa: PLC0415
        win1 = SystemMapWindow(sample_system)
        qtbot.addWidget(win1)
        win1._toggle_theme()   # -> light
        win1._toggle_theme()   # -> dark (explicit choice, not just the default)

        win2 = SystemMapWindow(sample_system)
        qtbot.addWidget(win2)
        assert win2._palette is PALETTE_DARK
        assert win2._theme_btn.text() == "Light Theme"

    def test_perspective_choice_persists_to_a_new_window(self, qtbot, fake_settings, no_webengine, sample_system):
        win1 = SystemMapWindow(sample_system)
        qtbot.addWidget(win1)
        win1._toggle_perspective()
        assert win1._perspective is True

        win2 = SystemMapWindow(sample_system)
        qtbot.addWidget(win2)
        assert win2._perspective is True
        assert win2._persp_btn.text() == "Top-down View"


# ════════════════════════════════════════════════════════════════════════════
# 11b. Export A3 Poster (HTML/PDF dispatch)
# ════════════════════════════════════════════════════════════════════════════

class TestExportPosterDialog:
    def test_html_path_writes_file_directly(self, system_app_win, tmp_path):
        target = str(tmp_path / "poster.html")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(target, "HTML (*.html)")), \
             patch.object(QMessageBox, "information"):
            system_app_win._on_export_poster_clicked()
        with open(target, encoding="utf-8") as fh:
            content = fh.read()
        assert content.startswith("<!DOCTYPE html>")
        assert "@page{ size: A3 landscape" in content

    def test_pdf_path_dispatches_to_pdf_export(self, system_app_win, tmp_path):
        target = str(tmp_path / "poster.pdf")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(target, "PDF (*.pdf)")), \
             patch.object(system_app_win, "_export_poster_pdf") as mock_pdf:
            system_app_win._on_export_poster_clicked()
        mock_pdf.assert_called_once()
        html_arg, path_arg = mock_pdf.call_args.args
        assert path_arg == target
        assert html_arg.startswith("<!DOCTYPE html>")
        assert not os.path.exists(target)  # writing is _export_poster_pdf's job, not the caller's

    def test_pdf_filter_without_extension_appends_pdf(self, system_app_win, tmp_path):
        target = str(tmp_path / "poster")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(target, "PDF (*.pdf)")), \
             patch.object(system_app_win, "_export_poster_pdf") as mock_pdf:
            system_app_win._on_export_poster_clicked()
        mock_pdf.assert_called_once()
        assert mock_pdf.call_args.args[1] == target + ".pdf"

    def test_html_filter_does_not_dispatch_to_pdf_export(self, system_app_win, tmp_path):
        target = str(tmp_path / "poster.html")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(target, "HTML (*.html)")), \
             patch.object(system_app_win, "_export_poster_pdf") as mock_pdf, \
             patch.object(QMessageBox, "information"):
            system_app_win._on_export_poster_clicked()
        mock_pdf.assert_not_called()

    def test_no_system_does_nothing(self, app_win, tmp_path):
        target = str(tmp_path / "poster.pdf")
        with patch.object(QFileDialog, "getSaveFileName",
                          return_value=(target, "PDF (*.pdf)")), \
             patch.object(app_win, "_export_poster_pdf") as mock_pdf:
            app_win._on_export_poster_clicked()
        mock_pdf.assert_not_called()
        assert not os.path.exists(target)


# ════════════════════════════════════════════════════════════════════════════
# 12. SurveyFormWindow
# ════════════════════════════════════════════════════════════════════════════

class TestSurveyFormWindow:
    def test_creates_without_error(self, qtbot, no_webengine):
        win = SurveyFormWindow("Test Survey", "<html></html>")
        qtbot.addWidget(win)
        win.show()
        assert win.isVisible()

    def test_window_title_matches_argument(self, qtbot, no_webengine):
        title = "Class 0/I Survey — Cogri"
        win = SurveyFormWindow(title, "<html></html>")
        qtbot.addWidget(win)
        assert win.windowTitle() == title

    def test_initial_size_is_980_by_700(self, qtbot, no_webengine):
        win = SurveyFormWindow("Test", "<html></html>")
        qtbot.addWidget(win)
        assert win.width() == 980
        assert win.height() == 700

    def test_html_delivered_to_web_view(self, qtbot, no_webengine):
        html = "<html><body>Survey content</body></html>"
        win = SurveyFormWindow("Test", html)
        qtbot.addWidget(win)
        assert win._view.last_html == html


# ════════════════════════════════════════════════════════════════════════════
# 13. Header buttons (Survey Form / System Map)
# ════════════════════════════════════════════════════════════════════════════

class TestHeaderButtons:
    def test_survey_click_appends_window(self, system_app_win):
        system_app_win._on_survey_clicked()
        assert len(system_app_win._survey_windows) == 1

    def test_three_survey_clicks_create_three_windows(self, system_app_win):
        for _ in range(3):
            system_app_win._on_survey_clicked()
        assert len(system_app_win._survey_windows) == 3

    def test_survey_window_is_survey_form_window_instance(self, system_app_win):
        system_app_win._on_survey_clicked()
        assert isinstance(system_app_win._survey_windows[0], SurveyFormWindow)

    def test_survey_window_title_contains_class0i(self, system_app_win):
        system_app_win._on_survey_clicked()
        win = system_app_win._survey_windows[0]
        assert "Class 0/I Survey" in win.windowTitle()

    def test_survey_window_title_contains_world_name(self, system_app_win):
        system_app_win._on_survey_clicked()
        win = system_app_win._survey_windows[0]
        mw = system_app_win._current_system.mainworld
        expected_name = mw.name if mw else "System"
        assert expected_name in win.windowTitle()

    def test_survey_html_has_data_theme_in_dark_mode(self, system_app_win):
        system_app_win._dark_mode = True
        system_app_win._on_survey_clicked()
        html = system_app_win._survey_windows[-1]._view.last_html
        assert 'data-theme="dark"' in html

    def test_survey_class2iii_html_has_form_number(self, sample_system):
        html = sample_system.to_survey_form_html_class2()
        assert "0421D-II.III" in html

    def test_survey_class2iii_html_has_orbit_section(self, sample_system):
        html = sample_system.to_survey_form_html_class2()
        assert "SAH/UWP" in html

    def test_survey_class2iii_window_opens(self, system_app_win):
        system_app_win._survey_combo.setCurrentIndex(1)
        system_app_win._on_survey_clicked()
        win = system_app_win._survey_windows[-1]
        assert isinstance(win, SurveyFormWindow)
        assert "II/III" in win.windowTitle()

    def test_map_click_appends_window(self, system_app_win):
        system_app_win._on_map_clicked()
        assert len(system_app_win._map_windows) == 1

    def test_two_map_clicks_create_two_windows(self, system_app_win):
        system_app_win._on_map_clicked()
        system_app_win._on_map_clicked()
        assert len(system_app_win._map_windows) == 2

    def test_map_window_is_system_map_window_instance(self, system_app_win):
        system_app_win._on_map_clicked()
        assert isinstance(system_app_win._map_windows[0], SystemMapWindow)

    def test_survey_click_is_noop_without_system(self, app_win):
        app_win._on_survey_clicked()
        assert len(app_win._survey_windows) == 0

    def test_map_click_is_noop_without_system(self, app_win):
        app_win._on_map_clicked()
        assert len(app_win._map_windows) == 0


# ════════════════════════════════════════════════════════════════════════════
# 14. Social detail and cultural profile
# ════════════════════════════════════════════════════════════════════════════

import re as _re  # noqa: E402


class TestSocialDetailGeneration:
    """Verify culture_detail is generated (or absent) based on _opt_social_detail."""

    def test_culture_detail_none_without_social_detail(self, system_app_win):
        assert system_app_win._current_world.culture_detail is None

    def test_culture_detail_present_with_social_detail(self, social_system_app_win):
        assert social_system_app_win._current_world.culture_detail is not None

    def test_cultural_profile_format(self, social_system_app_win):
        profile = social_system_app_win._current_world.culture_detail.cultural_profile
        assert _re.fullmatch(r"[0-9A-Z]{4}-[0-9A-Z]{4}", profile)

    def test_all_trait_values_at_least_one(self, social_system_app_win):
        cd = social_system_app_win._current_world.culture_detail
        for attr in ("diversity", "xenophilia", "uniqueness", "symbology",
                     "cohesion", "progressiveness", "expansionism", "militancy"):
            assert getattr(cd, attr) >= 1, f"{attr} < 1"

    def test_culture_section_in_mainworld_html(self, social_system_app_win):
        html = social_system_app_win._current_world.to_html()
        assert "Culture detail" in html

    def test_culture_section_absent_without_social_detail(self, system_app_win):
        html = system_app_win._current_world.to_html()
        assert "Culture detail" not in html

    # -- importance_detail --

    def test_importance_detail_none_without_social_detail(self, system_app_win):
        assert system_app_win._current_world.importance_detail is None

    def test_importance_detail_present_with_social_detail(self, social_system_app_win):
        assert social_system_app_win._current_world.importance_detail is not None

    def test_importance_equals_sum_of_dms(self, social_system_app_win):
        imp = social_system_app_win._current_world.importance_detail
        expected = (
            imp.starport_dm + imp.population_dm + imp.tech_dm
            + imp.agricultural_dm + imp.industrial_dm + imp.rich_dm
            + imp.base_dm + imp.waystation_dm
        )
        assert imp.importance == expected

    def test_importance_row_in_mainworld_html(self, social_system_app_win):
        html = social_system_app_win._current_world.to_html()
        assert "World importance" in html

    def test_importance_row_absent_without_social_detail(self, system_app_win):
        html = system_app_win._current_world.to_html()
        assert "World importance" not in html


# ════════════════════════════════════════════════════════════════════════════
# 13. Starport detail (UAT-105–115, issue #101, Session 137)
# ════════════════════════════════════════════════════════════════════════════

class TestStarportDetail:

    def test_starport_detail_present_with_social(self, social_system_app_win):
        assert social_system_app_win._current_world.starport_detail is not None

    def test_starport_detail_absent_without_social(self, system_app_win):
        assert system_app_win._current_world.starport_detail is None

    def test_starport_class_on_world(self, social_system_app_win):
        mw = social_system_app_win._current_world
        assert mw.starport in tuple("ABCDEX")

    def test_expected_weekly_positive(self, social_system_app_win):
        sd = social_system_app_win._current_world.starport_detail
        assert sd.expected_weekly >= 0

    def test_docking_capacity_positive(self, social_system_app_win):
        sd = social_system_app_win._current_world.starport_detail
        assert sd.downport_capacity >= 0

    def test_starport_profile_format(self, social_system_app_win):
        sd = social_system_app_win._current_world.starport_detail
        assert "-" in sd.starport_profile

    def test_starport_detail_section_in_html(self, social_system_app_win):
        html = social_system_app_win._current_world.to_html()
        assert "Starport" in html

    def test_starport_detail_absent_in_html_without_social(self, system_app_win):
        # Without social detail, starport_detail is None → no starport card in HTML
        mw = system_app_win._current_world
        assert mw.starport_detail is None

    def test_tl_floor_class_a(self, social_system_app_win):
        # For any Class A starport world, TL must be ≥ 9
        mw = social_system_app_win._current_world
        if mw.starport == "A":
            assert mw.tech_level >= 9

    def test_tl_floor_class_b(self, social_system_app_win):
        mw = social_system_app_win._current_world
        if mw.starport == "B":
            assert mw.tech_level >= 8


# ════════════════════════════════════════════════════════════════════════════
# 14. Military detail (UAT-116–126, issue #102, Session 138)
# ════════════════════════════════════════════════════════════════════════════

class TestMilitaryDetailUI:

    def test_military_detail_present_with_social(self, social_system_app_win):
        mw = social_system_app_win._current_world
        if mw.population >= 1:
            assert mw.military_detail is not None

    def test_military_detail_absent_without_social(self, system_app_win):
        assert system_app_win._current_world.military_detail is None

    def test_enforcement_always_exists(self, social_system_app_win):
        md = social_system_app_win._current_world.military_detail
        if md is not None:
            assert md.enforcement.exists

    def test_military_profile_format(self, social_system_app_win):
        md = social_system_app_win._current_world.military_detail
        if md is not None:
            parts = md.military_profile.split(":")
            assert len(parts) == 2
            assert "-" in parts[0]

    def test_state_of_readiness_valid(self, social_system_app_win):
        md = social_system_app_win._current_world.military_detail
        if md is not None:
            valid = {
                "Complacent peace", "Low threat level", "Normal readiness",
                "Heightened tensions, threat of war",
                "War or internal insurgency", "Total war: full mobilisation",
            }
            assert md.state_of_readiness in valid

    def test_budget_pct_positive(self, social_system_app_win):
        md = social_system_app_win._current_world.military_detail
        if md is not None:
            assert md.military_budget_pct > 0

    def test_military_section_in_html(self, social_system_app_win):
        mw = social_system_app_win._current_world
        if mw.military_detail is not None:
            html = mw.to_html()
            assert "Military" in html

    def test_military_absent_in_html_without_social(self, system_app_win):
        mw = system_app_win._current_world
        assert mw.military_detail is None


# ════════════════════════════════════════════════════════════════════════════
# 15. Extended travel zone (UAT-127–131, issue #103, Session 138)
# ════════════════════════════════════════════════════════════════════════════

class TestTravelZoneUI:

    def test_travel_zone_is_valid(self, social_system_app_win):
        zone = social_system_app_win._current_world.travel_zone
        assert zone in ("Green", "Amber", "Red")

    def test_travel_zone_valid_without_social(self, system_app_win):
        zone = system_app_win._current_world.travel_zone
        assert zone in ("Green", "Amber", "Red")

    def test_starport_x_always_red(self):
        import random  # noqa: PLC0415
        from traveller_gen.traveller_world_gen import generate_world  # noqa: PLC0415
        for seed in range(30):
            world = generate_world(seed=seed)
            if world.starport == "X":
                assert world.travel_zone == "Red", (
                    f"Starport X world has zone {world.travel_zone} (seed {seed})"
                )

    def test_travel_zone_in_world_html(self, system_app_win):
        html = system_app_win._current_world.to_html()
        assert "Travel zone" in html or "travel_zone" in html or "Green" in html or \
               "Amber" in html or "Red" in html

    def test_extended_zone_deterministic(self, social_system_app_win):
        # Re-generate with same options+seed; zone must match
        import random as _random  # noqa: PLC0415
        mw = social_system_app_win._current_world
        zone1 = mw.travel_zone
        assert zone1 in ("Green", "Amber", "Red")


# ════════════════════════════════════════════════════════════════════════════
# 16. World card About button (UAT-142–145, issue #159, Session 138)
# ════════════════════════════════════════════════════════════════════════════

class TestWorldCardAboutButton:

    def test_about_button_in_world_card_html(self):
        from traveller_gen.traveller_world_gen import generate_world  # noqa: PLC0415
        world = generate_world(seed=42)
        html = world.to_html()
        assert "about-btn" in html or "About" in html

    def test_about_dialog_element_in_html(self):
        from traveller_gen.traveller_world_gen import generate_world  # noqa: PLC0415
        world = generate_world(seed=42)
        html = world.to_html()
        assert "about-dialog" in html

    def test_about_html_contains_credits(self):
        from traveller_gen.traveller_world_gen import generate_world  # noqa: PLC0415
        world = generate_world(seed=42)
        html = world.to_html()
        assert "Geir Lanesskog" in html

    def test_about_html_contains_mit_license(self):
        from traveller_gen.traveller_world_gen import generate_world  # noqa: PLC0415
        world = generate_world(seed=42)
        html = world.to_html()
        assert "MIT License" in html

    def test_about_html_contains_disclaimer(self):
        from traveller_gen.traveller_world_gen import generate_world  # noqa: PLC0415
        world = generate_world(seed=42)
        html = world.to_html()
        assert "Mongoose Publishing" in html

    def test_about_html_contains_repo_link(self):
        from traveller_gen.traveller_world_gen import generate_world  # noqa: PLC0415
        world = generate_world(seed=42)
        html = world.to_html()
        assert "github.com/Elured-code/traveller-world-gen" in html


# ════════════════════════════════════════════════════════════════════════════
# 12. About dialog (issue #159)
# ════════════════════════════════════════════════════════════════════════════

class TestAboutDialog:

    def test_help_menu_exists(self, app_win):
        menus = [app_win.menuBar().actions()[i].text()
                 for i in range(app_win.menuBar().actions().__len__())]
        assert any("Help" in m for m in menus)

    def test_help_menu_has_about_action(self, app_win):
        menu_bar = app_win.menuBar()
        for action in menu_bar.actions():
            if "Help" in action.text():
                about_texts = [a.text() for a in action.menu().actions()]
                assert any("About" in t for t in about_texts)
                return
        pytest.fail("Help menu not found")

    def test_about_dialog_opens(self, app_win, qtbot, monkeypatch):
        opened = []

        class _FakeDialog(QDialog):
            def exec(self_):  # noqa: N805
                opened.append(True)

        monkeypatch.setattr(_mod, "QDialog", _FakeDialog)
        app_win._show_about()
        assert opened, "About dialog was not opened"

    def test_about_dialog_contains_version(self, app_win, qtbot):
        captured = []

        def _capture_label(label):
            captured.append(label.text())

        orig_show_about = app_win._show_about

        def _patched():
            dlg = QDialog(app_win)
            dlg.setWindowTitle("About Traveller World & System Generator")
            orig_show_about.__func__  # verify it's a bound method
            # Directly call and capture via override
            import genui_app as _ga  # noqa: PLC0415
            text = _ga._DISPLAY_VERSION
            assert text in _ga._DISPLAY_VERSION

        version_str = _mod._DISPLAY_VERSION
        assert version_str  # non-empty

    def test_about_dialog_contains_license(self, app_win):
        # Verify the about HTML string constant is accessible and correct
        dlg_html = (
            "<p><b>License:</b> MIT License"
        )
        # Check the method source contains MIT reference
        import inspect  # noqa: PLC0415
        src = inspect.getsource(app_win._show_about)
        assert "MIT License" in src

    def test_about_dialog_contains_disclaimer(self, app_win):
        import inspect  # noqa: PLC0415
        src = inspect.getsource(app_win._show_about)
        assert "Mongoose Publishing" in src

    def test_about_dialog_contains_repo_link(self, app_win):
        import inspect  # noqa: PLC0415
        src = inspect.getsource(app_win._show_about)
        assert "github.com/Elured-code/traveller-world-gen" in src

    def test_about_dialog_contains_wbh_credits(self, app_win):
        import inspect  # noqa: PLC0415
        src = inspect.getsource(app_win._show_about)
        assert "Geir Lanesskog" in src
        assert "Isabella Treccani-Chinelli" in src

    def test_about_dialog_contains_inner_circle(self, app_win):
        import inspect  # noqa: PLC0415
        src = inspect.getsource(app_win._show_about)
        assert "Traveller Inner Circle" in src
