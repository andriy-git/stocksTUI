from textual.widgets import Input


class SearchBox(Input):
    """A simple search box widget, extending Textual's Input with a default placeholder and ID."""

    def __init__(self, **kwargs):
        """
        Initializes the SearchBox.

        Args:
            **kwargs: Arbitrary keyword arguments passed to the parent Input class.
        """
        super().__init__(placeholder="Search...", id="search-box", **kwargs)
