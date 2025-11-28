import pandas as pd
from textual_plotext import PlotextPlot

class OIChart(PlotextPlot):
    """A custom widget to display Open Interest by strike using plotext."""

    def __init__(self, calls_df: pd.DataFrame, puts_df: pd.DataFrame, underlying_price: float, ticker: str = "", *args, **kwargs):
        """
        Args:
            calls_df: DataFrame containing calls data.
            puts_df: DataFrame containing puts data.
            underlying_price: Current price of underlying asset.
            ticker: The ticker symbol (optional).
        """
        super().__init__(*args, **kwargs)
        self._calls_df = calls_df
        self._puts_df = puts_df
        self._underlying_price = underlying_price
        self._ticker = ticker

    def on_mount(self) -> None:
        """Draws the plot when the widget is mounted."""
        self.replot()

    def replot(self):
        """Redraws the chart with current data."""
        plt = self.plt
        plt.clear_data()
        
        if self._calls_df.empty and self._puts_df.empty:
            return

        # Merge all strikes
        all_strikes = set()
        if not self._calls_df.empty:
            all_strikes.update(self._calls_df['strike'].tolist())
        if not self._puts_df.empty:
            all_strikes.update(self._puts_df['strike'].tolist())
        
        all_strikes = sorted(list(all_strikes))
        
        if not all_strikes:
            return

        # Calculate total OI per strike to find "active" range
        strike_oi = {}
        for k in all_strikes:
            c_val = self._calls_df[self._calls_df['strike'] == k]['openInterest'].sum() if not self._calls_df.empty else 0
            p_val = self._puts_df[self._puts_df['strike'] == k]['openInterest'].sum() if not self._puts_df.empty else 0
            strike_oi[k] = c_val + p_val
            
        # Find active range (min and max strike with significant OI)
        max_strike_oi = max(strike_oi.values()) if strike_oi else 0
        threshold = max_strike_oi * 0.01
        
        active_strikes = [k for k, oi in strike_oi.items() if oi > threshold]
        
        if not active_strikes:
            # Fallback if no active strikes found
            min_active = min(all_strikes)
            max_active = max(all_strikes)
        else:
            min_active = min(active_strikes)
            max_active = max(active_strikes)
            
        # Ensure ATM is included in range
        center = self._underlying_price
        min_active = min(min_active, center * 0.95)
        max_active = max(max_active, center * 1.05)
        
        # Select strikes within this range
        candidates = [s for s in all_strikes if min_active <= s <= max_active]
        
        # Prefer round strikes (multiples of 5) if we have many candidates
        if len(candidates) > 20:
            # Determine rounding granularity based on price range
            strike_range = max_active - min_active
            if strike_range > 200:
                # For wide ranges, prefer multiples of 10
                round_candidates = [s for s in candidates if s % 10 == 0]
            elif strike_range > 50:
                # For medium ranges, prefer multiples of 5
                round_candidates = [s for s in candidates if s % 5 == 0]
            else:
                # For narrow ranges, keep all
                round_candidates = candidates
            
            # Use round strikes if we have enough, otherwise fall back
            if len(round_candidates) >= 10:
                candidates = round_candidates
        
        # Limit total count to ~40
        if len(candidates) > 40:
            # Zoom in around center
            closest_idx = min(range(len(candidates)), key=lambda i: abs(candidates[i] - center))
            start = max(0, closest_idx - 20)
            end = min(len(candidates), closest_idx + 21)
            strikes = candidates[start:end]
        else:
            strikes = candidates

        # Extract OI for these strikes
        call_oi = []
        put_oi = []
        
        for k in strikes:
            # Get call OI
            c_row = self._calls_df[self._calls_df['strike'] == k]
            c_val = c_row['openInterest'].sum() if not c_row.empty else 0
            call_oi.append(c_val)
            
            # Get put OI
            p_row = self._puts_df[self._puts_df['strike'] == k]
            p_val = p_row['openInterest'].sum() if not p_row.empty else 0
            put_oi.append(p_val)

        # Plot
        # Format labels
        labels = [f"{int(s)}" if s.is_integer() else f"{s:.1f}" for s in strikes]
        
        # Declutter X-axis if too many labels
        if len(labels) > 15:
            step = len(labels) // 15 + 1
            display_labels = []
            for i, label in enumerate(labels):
                if i % step == 0:
                    display_labels.append(label)
                else:
                    display_labels.append("")
            
            # Ensure ATM label is shown
            closest_label_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - center))
            display_labels[closest_label_idx] = labels[closest_label_idx]
            labels = display_labels
        
        plt.multiple_bar(
            labels,
            [call_oi, put_oi],
            labels=["Calls", "Puts"],
            color=["green", "red"]
        )
        
        plt.title(f"Open Interest by Strike for {self._ticker} (Near ${self._underlying_price:.2f})")
        plt.xlabel("Strike Price")
        plt.ylabel("Open Interest")
        
        # Calculate nice Y-axis ticks
        max_oi = max(max(call_oi) if call_oi else 0, max(put_oi) if put_oi else 0)
        if max_oi > 0:
            # Find a nice step size
            # We want about 5 ticks
            rough_step = max_oi / 5
            magnitude = 10 ** (len(str(int(rough_step))) - 1)
            base = rough_step / magnitude
            
            # Round to nice base
            if base < 1.5: nice_base = 1
            elif base < 3: nice_base = 2
            elif base < 7: nice_base = 5
            else: nice_base = 10
            
            step = nice_base * magnitude
            
            # Generate ticks
            ticks = []
            current = 0
            while current <= max_oi * 1.1: # Go slightly above max
                ticks.append(current)
                current += step
                
            def format_large_num(n):
                if n == 0: return "0"
                if n >= 1_000_000: 
                    val = n/1_000_000
                    return f"{int(val)}M" if val.is_integer() else f"{val:.1f}M"
                if n >= 1_000: 
                    val = n/1_000
                    return f"{int(val)}K" if val.is_integer() else f"{val:.1f}K"
                return str(int(n))
                
            plt.yticks(ticks, [format_large_num(t) for t in ticks])
            
        plt.grid(True, True)
