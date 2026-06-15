"""Tests for the EditFredSeriesModal."""

import unittest

from textual.app import App
from textual.widgets import Button, Input

from stockstui.ui.edit_fred_series_modal import EditFredSeriesModal


class TestApp(App):
    """A minimal app for testing."""
    pass


class TestEditFredSeriesModal(unittest.IsolatedAsyncioTestCase):
    """Tests for EditFredSeriesModal."""

    async def test_modal_displays_series_id_and_current_alias(self) -> None:
        """Test that the modal displays the series ID and current alias."""
        app = TestApp()
        async with app.run_test() as pilot:
            modal = EditFredSeriesModal(series_id="GDP", current_alias="Gross Domestic Product")
            await pilot.app.push_screen(modal)
            await pilot.pause()
            
            self.assertEqual(modal.series_id, "GDP")
            self.assertEqual(modal.current_alias, "Gross Domestic Product")

    async def test_modal_input_placeholder_when_no_alias(self) -> None:
        """Test that the input field is empty when no alias exists."""
        app = TestApp()
        async with app.run_test() as pilot:
            modal = EditFredSeriesModal(series_id="GDP", current_alias="")
            await pilot.app.push_screen(modal)
            await pilot.pause()
            
            alias_input = modal.query_one("#alias-input", Input)
            self.assertEqual(alias_input.value, "")

    async def test_save_button_saves_alias(self) -> None:
        """Test that pressing Save dismisses with the entered alias."""
        app = TestApp()
        result = None
        
        def capture_result(r):
            nonlocal result
            result = r
            
        async with app.run_test() as pilot:
            modal = EditFredSeriesModal(series_id="GDP", current_alias="")
            await pilot.app.push_screen(modal, capture_result)
            await pilot.pause()
            
            alias_input = modal.query_one("#alias-input", Input)
            alias_input.value = "New Alias"
            
            save_button = modal.query_one("#save", Button)
            await pilot.click("#save")
            await pilot.pause()
            
            self.assertEqual(result, "New Alias")

    async def test_cancel_button_dismisses_with_none(self) -> None:
        """Test that pressing Cancel dismisses with None."""
        app = TestApp()
        result = None
        
        def capture_result(r):
            nonlocal result
            result = r
            
        async with app.run_test() as pilot:
            modal = EditFredSeriesModal(series_id="GDP", current_alias="Existing Alias")
            await pilot.app.push_screen(modal, capture_result)
            await pilot.pause()
            
            await pilot.click("#cancel")
            await pilot.pause()
            
            self.assertIsNone(result)

    async def test_on_mount_focuses_alias_input(self) -> None:
        """Test that the alias input is focused when modal mounts."""
        app = TestApp()
        async with app.run_test() as pilot:
            modal = EditFredSeriesModal(series_id="GDP", current_alias="")
            await pilot.app.push_screen(modal)
            await pilot.pause()
            
            alias_input = modal.query_one("#alias-input", Input)
            self.assertTrue(alias_input.has_focus)

    async def test_enter_key_submits_alias(self) -> None:
        """Test that pressing Enter in the input field triggers save."""
        app = TestApp()
        result = None
        
        def capture_result(r):
            nonlocal result
            result = r
            
        async with app.run_test() as pilot:
            modal = EditFredSeriesModal(series_id="GDP", current_alias="")
            await pilot.app.push_screen(modal, capture_result)
            await pilot.pause()
            
            alias_input = modal.query_one("#alias-input", Input)
            alias_input.value = "Test Alias"
            alias_input.focus()
            
            await pilot.press("enter")
            await pilot.pause()
            
            self.assertEqual(result, "Test Alias")

    async def test_whitespace_is_stripped_from_saved_alias(self) -> None:
        """Test that leading/trailing whitespace is stripped from saved alias."""
        app = TestApp()
        result = None
        
        def capture_result(r):
            nonlocal result
            result = r
            
        async with app.run_test() as pilot:
            modal = EditFredSeriesModal(series_id="GDP", current_alias="")
            await pilot.app.push_screen(modal, capture_result)
            await pilot.pause()
            
            alias_input = modal.query_one("#alias-input", Input)
            alias_input.value = "  Spaced Alias  "
            
            await pilot.click("#save")
            await pilot.pause()
            
            self.assertEqual(result, "Spaced Alias")
