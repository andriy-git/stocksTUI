import unittest
import argparse
from importlib import metadata

from stockstui.parser import create_arg_parser, SessionListAction

class TestArgParser(unittest.TestCase):
    """Unit tests for the command-line argument parser."""

    def setUp(self):
        """Create a new parser for each test."""
        self.parser = create_arg_parser()

    def test_version_flag(self):
        """Test that --version prints the version and exits."""
        try:
            version = metadata.version("stocksTUI")
        except metadata.PackageNotFoundError:
            version = "0.0.0-dev"

        with self.assertRaises(SystemExit) as cm:
            self.parser.parse_args(['--version'])
        self.assertEqual(cm.exception.code, 0)

    def test_view_selection_flags(self):
        """Test flags that determine the starting view of the TUI."""
        # Test --tab
        args = self.parser.parse_args(['--tab', 'crypto'])
        self.assertEqual(args.tab, 'crypto')
        
        # Test --news without ticker
        args = self.parser.parse_args(['--news'])
        self.assertTrue(args.news)
        
        # Test --news with tickers
        args = self.parser.parse_args(['-N', 'AAPL,MSFT'])
        self.assertEqual(args.news, 'AAPL,MSFT')
        
        # Test --history without ticker
        args = self.parser.parse_args(['--history'])
        self.assertTrue(args.history)
        
        # Test --history with ticker
        args = self.parser.parse_args(['-H', 'TSLA'])
        self.assertEqual(args.history, 'TSLA')
        
        # Test --options without ticker
        args = self.parser.parse_args(['--options'])
        self.assertTrue(args.options)
        
        # Test --options with ticker
        args = self.parser.parse_args(['-O', 'V'])
        self.assertEqual(args.options, 'V')
        
        # Test --debug and --configs
        args = self.parser.parse_args(['--debug'])
        self.assertTrue(args.debug)
        args = self.parser.parse_args(['--configs'])
        self.assertTrue(args.configs)

    def test_history_options(self):
        """Test flags specific to the history view."""
        args = self.parser.parse_args(['--period', '1y', '--chart'])
        self.assertEqual(args.period, '1y')
        self.assertTrue(args.chart)

    def test_output_flag(self):
        """Test the --output flag for CLI mode."""
        # No value, should default to 'all'
        args = self.parser.parse_args(['-o'])
        self.assertEqual(args.output, 'all')
        
        # With a specific list
        args = self.parser.parse_args(['--output', 'stocks,crypto'])
        self.assertEqual(args.output, 'stocks,crypto')

    def test_session_list_action(self):
        """Test the custom action for creating temporary session lists."""
        # Single session list
        args = self.parser.parse_args(['--session-list', 'my_stocks=AAPL,TSLA'])
        expected = {'my stocks': ['AAPL', 'TSLA']}
        self.assertEqual(args.session_list, expected)

        # Multiple session lists
        args = self.parser.parse_args([
            '--session-list', 'stocks=GOOG,AMZN', 'crypto=BTC-USD,ETH-USD'
        ])
        expected = {
            'stocks': ['GOOG', 'AMZN'],
            'crypto': ['BTC-USD', 'ETH-USD']
        }
        self.assertEqual(args.session_list, expected)

    def test_session_list_action_invalid_format(self):
        """Test that SessionListAction raises an error for malformed input."""
        # FIX: argparse calls sys.exit(2) after printing an error.
        # We need to catch SystemExit instead of argparse.ArgumentError.
        with self.assertRaises(SystemExit):
            self.parser.parse_args(['--session-list', 'no_equals_sign'])

        with self.assertRaises(SystemExit):
            self.parser.parse_args(['--session-list', 'empty_list='])

if __name__ == '__main__':
    unittest.main()
