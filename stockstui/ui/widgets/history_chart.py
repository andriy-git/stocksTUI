import pandas as pd
import numpy as np
import plotext
from textual_plotext import PlotextPlot


class HistoryChart(PlotextPlot):
    """A custom widget to display a historical stock chart using plotext."""

    def __init__(self, data: pd.DataFrame, period: str, *args, **kwargs):
        """
        Initializes the HistoryChart widget.

        Args:
            data: A pandas DataFrame containing the historical data (must have a 'Close' column).
            period: The period of the historical data (e.g., "1mo", "1y"), used for date tick formatting.
            *args, **kwargs: Arguments passed to the parent PlotextPlot class.
        """
        super().__init__(*args, **kwargs)
        self._data = data
        self._period = period

    def on_mount(self) -> None:
        """Draws the plot when the widget is mounted to the application."""
        plt = self.plt # Get the plotext plotting object
        plt.clear_data() # Clear any existing data from the plot

        if self._data is None or self._data.empty:
            return # Nothing to plot if no data

        # Convert datetime index to numerical unix timestamps for plotting on the x-axis
        x_data = [d.timestamp() for d in self._data.index]
        
        # Try to get closing prices, fall back to other columns if Close is missing
        if 'Close' in self._data.columns:
            y_data = self._data['Close'].tolist()
        elif 'Open' in self._data.columns:
            y_data = self._data['Open'].tolist()
        elif len(self._data.columns) > 0:
            # Use the first available numeric column
            y_data = self._data.iloc[:, 0].tolist()
        else:
            return # No data to plot
        
        plt.plot(x_data, y_data, color="orange") # Plot the price history

        self._set_date_ticks() # Configure x-axis (date) ticks and labels
        self._set_price_ticks() # Configure y-axis (price) ticks and labels

        plt.title('Price History') # Set chart title
        plt.ylabel('Price (USD)') # Set y-axis label
        plt.grid(True, True) # Enable grid lines for better readability

    def _get_nice_y_ticks(self, y_min: float, y_max: float, num_ticks: int = 5) -> list[float]:
        """
        Calculates 'nice' (human-readable) tick values for the y-axis.
        This ensures that the price labels are well-spaced and easy to read.

        Args:
            y_min: The minimum value on the y-axis.
            y_max: The maximum value on the y-axis.
            num_ticks: The desired approximate number of ticks.

        Returns:
            A list of calculated tick values.
        """
        y_range = y_max - y_min
        if y_range == 0:
            return [y_min] # Handle cases with no range

        # Calculate a rough step size
        rough_step = y_range / (num_ticks - 1)
        
        if rough_step == 0: # Avoid division by zero if range is tiny
            return [y_min]

        # Determine the magnitude of the rough step
        power = 10 ** -np.floor(np.log10(abs(rough_step)))
        nice_rough_step = rough_step * power
        
        # Define preferred multipliers for nice steps
        nice_multipliers = [0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10]
        nice_step = rough_step
        # Find the smallest 'nice' multiplier that is greater than or equal to the rough step
        for mult in nice_multipliers:
            if mult >= nice_rough_step:
                nice_step = mult / power
                break

        # Calculate the tick values, starting from a "nice" number below y_min
        start_tick = np.floor(y_min / nice_step) * nice_step
        end_tick = np.ceil(y_max / nice_step) * nice_step
        
        ticks = np.arange(start_tick, end_tick + nice_step, nice_step)
        
        return list(ticks)

    def _set_price_ticks(self):
        """
        Sets the y-axis ticks and labels to human-readable, formatted price values.
        It calculates appropriate tick positions and forces plotext to use them.
        """
        plt = self.plt
        
        # Find the first numeric column to use for y-axis range
        price_column = None
        if 'Close' in self._data.columns:
            price_column = 'Close'
        elif 'Open' in self._data.columns:
            price_column = 'Open'
        elif len(self._data.columns) > 0:
            price_column = self._data.columns[0]
        
        if price_column is None:
            return
            
        y_min, y_max = self._data[price_column].min(), self._data[price_column].max()

        if y_min is not None and y_max is not None and y_max >= y_min:
            # Determine the number of ticks based on available vertical space.
            num_ticks = 4 if self.size.height < 15 else 6

            # First, calculate our own "nice" ticks.
            ticks = self._get_nice_y_ticks(y_min, y_max, num_ticks)
            
            # Create the corresponding labels, formatted as currency.
            labels = [f"{tick:,.2f}" for tick in ticks]
            
            # Then, set the y-axis limits to match our calculated ticks. This is the crucial step
            # to ensure plotext uses our custom ticks correctly.
            if ticks:
                if len(ticks) > 1:
                    plt.ylim(ticks[0], ticks[-1])
                else:
                    # Handle single tick case (flat line) to avoid plotext error (division by zero)
                    val = ticks[0]
                    delta = abs(val) * 0.05 if val != 0 else 1.0
                    plt.ylim(val - delta, val + delta)
            
            # Finally, apply our calculated ticks and labels.
            plt.yticks(ticks, labels)
        elif y_min is not None:
            # Fallback for single data point or flat line, just show the single price.
            plt.yticks([y_min], [f"{y_min:,.2f}"])

    def _set_date_ticks(self):
        """
        Sets the x-axis (date) ticks and labels dynamically based on the data period.
        It aims to provide readable date labels for different timeframes.
        """
        plt = self.plt
        
        start_date = self._data.index.min()
        end_date = self._data.index.max()
        
        freq = None # Frequency for pandas date_range
        label_format = "" # Format string for datetime objects
        ticks = [] # List to store calculated tick datetime objects

        # Determine appropriate frequency and label format based on the data period
        if self._period in ["5y", "max"]:
            freq = 'YS' # Year Start frequency
            label_format = '%Y' # Year (e.g., 2020)
        elif self._period in ["6mo", "ytd", "1y"]:
            freq = 'MS' # Month Start frequency
            label_format = '%b %Y' # Abbreviated month and year (e.g., Jan 2023)
        elif self._period == "1mo":
            freq = 'W-MON' # Weekly on Monday frequency
            label_format = '%b %d' # Abbreviated month and day (e.g., Jan 01)
        elif self._period == "5d":
            freq = 'D' # Daily frequency
            label_format = '%a %d' # Abbreviated weekday and day (e.g., Mon 01)
        elif self._period == "1d":
            # Special handling for 1-day period to show hourly ticks
            hour_ticks = []
            current_date = start_date.floor('H') # Start from the beginning of the hour
            if current_date < start_date:
                current_date += pd.Timedelta(hours=1) # Adjust if start_date is mid-hour
            
            while current_date <= end_date:
                hour_ticks.append(current_date)
                current_date += pd.Timedelta(hours=2) # Use 2-hour increments for clarity
            
            # Downsample ticks if too many for display
            if len(hour_ticks) > 8:
                step = round(len(hour_ticks) / 6) or 1
                ticks = hour_ticks[::step]
            else:
                ticks = hour_ticks
            
            label_format = '%H:%M' # Hour and minute (e.g., 10:30)

        # Generate ticks using pandas date_range if a frequency is defined
        if freq:
            ticks = pd.date_range(start=start_date, end=end_date, freq=freq).to_list()
        
        if ticks:
            # Filter out ticks outside the actual data range just in case
            ticks = [t for t in ticks if start_date <= t <= end_date]
            labels = [d.strftime(label_format) for d in ticks]
            
            # Convert datetime tick objects to numerical timestamps for positioning on plotext
            tick_positions = [t.timestamp() for t in ticks]
            plt.xticks(tick_positions, labels)