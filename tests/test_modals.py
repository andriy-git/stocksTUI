import unittest
from unittest.mock import MagicMock

from textual.app import App
from stockstui.ui.modals import (
    ConfirmDeleteModal, AddListModal, EditListModal,
    AddTickerModal, EditTickerModal, CreatePortfolioModal, EditPortfolioModal
)

class ModalsTestApp(App):
    """A minimal app for testing modals."""
    pass

class TestModals(unittest.IsolatedAsyncioTestCase):
    """
    Unit tests for all modal dialogs.
    These tests verify that modals compose correctly and return the expected
    data when their buttons are pressed.
    """
    async def test_confirm_delete_modal(self):
        """Test the ConfirmDeleteModal."""
        app = ModalsTestApp()
        async with app.run_test() as pilot:
            result = None
            def set_result(r):
                nonlocal result
                result = r

            # Test confirm
            await pilot.app.push_screen(ConfirmDeleteModal("item", "Delete?"), set_result)
            await pilot.pause()
            await pilot.click("#delete")
            await pilot.pause()
            self.assertTrue(result)

            # Test cancel
            await pilot.app.push_screen(ConfirmDeleteModal("item", "Delete?"), set_result)
            await pilot.pause()
            await pilot.click("#cancel")
            await pilot.pause()
            self.assertFalse(result)

    async def test_add_list_modal(self):
        """Test the AddListModal."""
        app = ModalsTestApp()
        async with app.run_test() as pilot:
            result = "" # Use a non-None default
            def set_result(r):
                nonlocal result
                result = r

            # Test add
            await pilot.app.push_screen(AddListModal(), set_result)
            await pilot.pause()
            await pilot.press("t", "e", "s", "t", " ", "l", "i", "s", "t")
            await pilot.click("#add")
            await pilot.pause()
            self.assertEqual(result, "test_list")
            
            # Test cancel
            await pilot.app.push_screen(AddListModal(), set_result)
            await pilot.pause()
            await pilot.click("#cancel")
            await pilot.pause()
            self.assertIsNone(result)

    async def test_edit_list_modal(self):
        """Test the EditListModal."""
        app = ModalsTestApp()
        async with app.run_test() as pilot:
            result = ""
            def set_result(r):
                nonlocal result
                result = r
            
            current_value = "old_name"
            await pilot.app.push_screen(EditListModal(current_value), set_result)
            await pilot.pause()
            
            # FIX: Clear the input before typing to prevent overwriting selected text.
            for _ in current_value:
                await pilot.press("backspace")
            await pilot.press("n", "e", "w", "_", "n", "a", "m", "e")
            
            await pilot.click("#save")
            await pilot.pause()
            self.assertEqual(result, "new_name")

    async def test_add_ticker_modal(self):
        """Test the AddTickerModal."""
        app = ModalsTestApp()
        async with app.run_test() as pilot:
            result = None
            def set_result(r):
                nonlocal result
                result = r

            await pilot.app.push_screen(AddTickerModal(), set_result)
            await pilot.pause()
            await pilot.press("a", "a", "p", "l", "tab", "a", "p", "p", "l", "e", "tab", "n", "o", "t", "e", "tab", "t", "a", "g")
            await pilot.click("#add")
            await pilot.pause()
            self.assertEqual(result, ("AAPL", "apple", "note", "tag"))

    async def test_edit_ticker_modal(self):
        """Test the EditTickerModal."""
        app = ModalsTestApp()
        async with app.run_test() as pilot:
            result = None
            def set_result(r):
                nonlocal result
                result = r

            current_alias = "alias"
            await pilot.app.push_screen(EditTickerModal("TICK", current_alias, "note", "tags"), set_result)
            await pilot.pause()
            await pilot.press("tab") # Focus the alias input
            
            # FIX: Clear and re-type to avoid selection issues.
            for _ in current_alias:
                await pilot.press("backspace")
            await pilot.press("n", "e", "w", "_", "a", "l", "i", "a", "s")

            await pilot.click("#save")
            await pilot.pause()
            self.assertEqual(result, ("TICK", "new_alias", "note", "tags"))
            
    async def test_create_portfolio_modal(self):
        """Test the CreatePortfolioModal."""
        app = ModalsTestApp()
        async with app.run_test() as pilot:
            result = None
            def set_result(r):
                nonlocal result
                result = r

            await pilot.app.push_screen(CreatePortfolioModal(), set_result)
            await pilot.pause()
            await pilot.press("n", "a", "m", "e", "tab", "d", "e", "s", "c")
            await pilot.click("#create")
            await pilot.pause()
            self.assertEqual(result, ("name", "desc"))

    async def test_edit_portfolio_modal(self):
        """Test the EditPortfolioModal."""
        app = ModalsTestApp()
        async with app.run_test() as pilot:
            result = None
            def set_result(r):
                nonlocal result
                result = r
            
            current_name = "old"
            await pilot.app.push_screen(EditPortfolioModal(current_name, "old_desc"), set_result)
            await pilot.pause()

            # FIX: Clear and re-type to avoid selection issues.
            for _ in current_name:
                await pilot.press("backspace")
            await pilot.press("n", "e", "w", "_", "n", "a", "m", "e")

            await pilot.click("#save")
            await pilot.pause()
            self.assertEqual(result, ("new_name", "old_desc"))
