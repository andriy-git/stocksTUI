import unittest
import math
from stockstui.utils.black_scholes import calculate_greeks, _norm_cdf, _norm_pdf


class TestBlackScholes(unittest.TestCase):
    """Test suite for Black-Scholes calculator."""

    def test_norm_cdf_standard_values(self):
        """Test normal CDF with known values."""
        # P(Z <= 0) = 0.5 for standard normal
        self.assertAlmostEqual(_norm_cdf(0), 0.5, places=4)
        
        # P(Z <= 1.96) ≈ 0.975 (95th percentile)
        self.assertAlmostEqual(_norm_cdf(1.96), 0.975, places=2)
        
        # P(Z <= -1.96) ≈ 0.025
        self.assertAlmostEqual(_norm_cdf(-1.96), 0.025, places=2)

    def test_norm_pdf_standard_values(self):
        """Test normal PDF with known values."""
        # PDF at mean is 1/sqrt(2*pi) ≈ 0.3989
        self.assertAlmostEqual(_norm_pdf(0), 1 / math.sqrt(2 * math.pi), places=4)
        
        # PDF should be symmetric
        self.assertAlmostEqual(_norm_pdf(1), _norm_pdf(-1), places=10)

    def test_greeks_call_itm(self):
        """Test Greeks for ITM call."""
        greeks = calculate_greeks(
            flag='c',
            S=110,  # ITM
            K=100,
            T=30 / 365,
            r=0.05,
            sigma=0.25
        )
        
        # Delta should be positive and high for ITM call
        self.assertGreater(greeks['delta'], 0.5)
        self.assertLess(greeks['delta'], 1.0)
        
        # Gamma should be positive
        self.assertGreater(greeks['gamma'], 0)
        
        # Theta should be negative (time decay)
        self.assertLess(greeks['theta'], 0)
        
        # Vega should be positive
        self.assertGreater(greeks['vega'], 0)

    def test_greeks_put_itm(self):
        """Test Greeks for ITM put."""
        greeks = calculate_greeks(
            flag='p',
            S=90,  # ITM
            K=100,
            T=30 / 365,
            r=0.05,
            sigma=0.25
        )
        
        # Delta should be negative for put
        self.assertLess(greeks['delta'], 0)
        self.assertGreater(greeks['delta'], -1.0)
        
        # Gamma should be positive
        self.assertGreater(greeks['gamma'], 0)
        
        # Theta should be negative
        self.assertLess(greeks['theta'], 0)
        
        # Vega should be positive
        self.assertGreater(greeks['vega'], 0)

    def test_greeks_atm(self):
        """Test Greeks for ATM option."""
        greeks = calculate_greeks(
            flag='c',
            S=100,
            K=100,
            T=30 / 365,
            r=0.05,
            sigma=0.25
        )
        
        # ATM call delta should be around 0.5
        self.assertAlmostEqual(greeks['delta'], 0.5, delta=0.15)
        
        # Gamma should be highest at ATM
        self.assertGreater(greeks['gamma'], 0.01)

    def test_greeks_expiring_soon(self):
        """Test Greeks with very short time to expiration."""
        greeks = calculate_greeks(
            flag='c',
            S=100,
            K=100,
            T=1 / 365,  # 1 day
            r=0.05,
            sigma=0.25
        )
        
        # Theta should be negative near expiration (adjusted for realistic values)
        self.assertLess(greeks['theta'], 0)

    def test_greeks_zero_time(self):
        """Test Greeks with zero time to expiration."""
        greeks = calculate_greeks(
            flag='c',
            S=100,
            K=100,
            T=0,
            r=0.05,
            sigma=0.25
        )
        
        # Should return zeros for expired option
        self.assertEqual(greeks['delta'], 0.0)
        self.assertEqual(greeks['gamma'], 0.0)

    def test_greeks_deep_otm(self):
        """Test Greeks for deep OTM option."""
        greeks = calculate_greeks(
            flag='c',
            S=100,
            K=150,  # Deep OTM call
            T=30 / 365,
            r=0.05,
            sigma=0.25
        )
        
        # Delta should be very low for deep OTM
        self.assertLess(greeks['delta'], 0.1)

    def test_greeks_deep_itm(self):
        """Test Greeks for deep ITM option."""
        greeks = calculate_greeks(
            flag='c',
            S=100,
            K=50,  # Deep ITM call
            T=30 / 365,
            r=0.05,
            sigma=0.25
        )
        
        # Delta should be very high for deep ITM
        self.assertGreater(greeks['delta'], 0.9)

    def test_greeks_high_volatility(self):
        """Test Greeks with high volatility."""
        low_vol = calculate_greeks(flag='c', S=100, K=100, T=30/365, r=0.05, sigma=0.10)
        high_vol = calculate_greeks(flag='c', S=100, K=100, T=30/365, r=0.05, sigma=0.50)
        
        # Higher volatility should mean higher vega
        self.assertGreater(high_vol['vega'], low_vol['vega'])

    def test_greeks_invalid_inputs(self):
        """Test that invalid inputs return zeros."""
        # Negative price
        greeks = calculate_greeks(flag='c', S=-100, K=100, T=30/365, r=0.05, sigma=0.25)
        self.assertEqual(greeks['delta'], 0.0)
        
        # Negative strike
        greeks = calculate_greeks(flag='c', S=100, K=-100, T=30/365, r=0.05, sigma=0.25)
        self.assertEqual(greeks['delta'], 0.0)
        
        # Negative volatility
        greeks = calculate_greeks(flag='c', S=100, K=100, T=30/365, r=0.05, sigma=-0.25)
        self.assertEqual(greeks['delta'], 0.0)

    def test_greeks_with_dividend(self):
        """Test Greeks with dividend yield."""
        no_div = calculate_greeks(flag='c', S=100, K=100, T=30/365, r=0.05, sigma=0.25, q=0.0)
        with_div = calculate_greeks(flag='c', S=100, K=100, T=30/365, r=0.05, sigma=0.25, q=0.02)
        
        # Dividend should reduce call delta
        self.assertLess(with_div['delta'], no_div['delta'])

    def test_greeks_unknown_flag(self):
        """Test that unknown flag returns empty dict."""
        greeks = calculate_greeks(flag='x', S=100, K=100, T=30/365, r=0.05, sigma=0.25)
        self.assertEqual(greeks, {})


if __name__ == '__main__':
    unittest.main()
