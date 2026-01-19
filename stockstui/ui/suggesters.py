from textual.suggester import Suggester


class TickerSuggester(Suggester):
    """
    A custom suggester for ticker input fields. It formats suggestions as
    'TICKER - Description - TICKER' to ensure the ticker is always visible.
    It prioritizes autocompletion for ticker symbols but also allows discovery
    by searching the description text.
    """

    def __init__(self, items: list[tuple[str, str]], *, case_sensitive: bool = False):
        """
        Initializes the TickerSuggester.

        Args:
            items: A list of tuples, where each tuple is (ticker_symbol, description).
                   The description is used for fuzzy matching.
            case_sensitive: If True, matching will be case-sensitive. Defaults to False.
        """
        super().__init__(case_sensitive=case_sensitive)
        self._items = items  # Stores the original items
        # Pre-process items for case-insensitive comparison if needed
        self._for_comparison = (
            [(item[0].casefold(), item[1].casefold()) for item in items]
            if not self.case_sensitive
            else items
        )

    async def get_suggestion(self, value: str) -> str | None:
        """
        Provides a suggestion based on the input `value`.

        It first attempts to match the `value` as a prefix of a ticker symbol.
        If no prefix match is found, it then searches for the `value` within
        the description of any ticker.

        Args:
            value: The current input string from the user.

        Returns:
            A formatted suggestion string (e.g., 'TICKER - Description - TICKER')
            or None if no suitable suggestion is found.
        """
        if not value:
            return None

        search_value = value if self.case_sensitive else value.casefold()

        # --- Priority 1: Match the start of the ticker for perfect autocompletion ---
        for i, (ticker_val, _) in enumerate(self._for_comparison):
            if ticker_val.startswith(search_value):
                original_ticker, original_desc = self._items[i]
                # Format is "TICKER - Description - TICKER"
                suggestion_text = (
                    f"{original_ticker} - {original_desc} - {original_ticker}"
                )
                # Return the remainder of the string for a clean autocomplete.
                return suggestion_text[len(value) :]

        # --- Priority 2: Match within the description for discovery ---
        for i, (_, desc_val) in enumerate(self._for_comparison):
            if search_value in desc_val:
                original_ticker, original_desc = self._items[i]
                # Return the full string for discovery.
                return f"{original_ticker} - {original_desc} - {original_ticker}"

        return None
