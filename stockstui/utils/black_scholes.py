"""
Black-Scholes Options Pricing Model Calculator.
Used to calculate Greeks (Delta, Gamma, Theta, Vega) for options.
"""
import math
import logging

# Standard normal distribution constants
INV_SQRT_2PI = 0.3989422804014327
DAYS_PER_YEAR = 365.0


def _norm_pdf(x):
    """Standard normal probability density function."""
    return INV_SQRT_2PI * math.exp(-0.5 * x * x)


def _norm_cdf(x):
    """Standard normal cumulative distribution function."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def calculate_greeks(
    flag: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0
) -> dict:
    """
    Calculate option Greeks using Black-Scholes model.

    Args:
        flag: 'c' for Call, 'p' for Put
        S: Underlying Asset Price
        K: Strike Price
        T: Time to Expiration (in years)
        r: Risk-Free Interest Rate (decimal, e.g., 0.05 for 5%)
        sigma: Volatility (decimal, e.g., 0.20 for 20%)
        q: Dividend Yield (decimal, e.g., 0.01 for 1%)

    Returns:
        Dictionary containing 'delta', 'gamma', 'theta', 'vega', 'rho'
    """
    try:
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0}

        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        pdf_d1 = _norm_pdf(d1)
        cdf_d1 = _norm_cdf(d1)
        cdf_d2 = _norm_cdf(d2)
        cdf_neg_d1 = _norm_cdf(-d1)
        cdf_neg_d2 = _norm_cdf(-d2)

        # Common Greeks
        gamma = (pdf_d1 * math.exp(-q * T)) / (S * sigma * sqrt_T)
        vega = S * math.exp(-q * T) * pdf_d1 * sqrt_T * 0.01  # Scaled by 0.01 for 1% change in vol

        if flag.lower() == 'c':
            # Call Greeks
            delta = math.exp(-q * T) * cdf_d1
            
            theta_part1 = -(S * sigma * math.exp(-q * T) * pdf_d1) / (2 * sqrt_T)
            theta_part2 = -r * K * math.exp(-r * T) * cdf_d2
            theta_part3 = q * S * math.exp(-q * T) * cdf_d1
            theta = (theta_part1 + theta_part2 + theta_part3) / DAYS_PER_YEAR  # Daily theta
            
            rho = K * T * math.exp(-r * T) * cdf_d2 * 0.01  # Scaled by 0.01 for 1% change in rate

        elif flag.lower() == 'p':
            # Put Greeks
            delta = -math.exp(-q * T) * cdf_neg_d1
            
            theta_part1 = -(S * sigma * math.exp(-q * T) * pdf_d1) / (2 * sqrt_T)
            theta_part2 = r * K * math.exp(-r * T) * cdf_neg_d2
            theta_part3 = -q * S * math.exp(-q * T) * cdf_neg_d1
            theta = (theta_part1 + theta_part2 + theta_part3) / DAYS_PER_YEAR  # Daily theta
            
            rho = -K * T * math.exp(-r * T) * cdf_neg_d2 * 0.01  # Scaled by 0.01 for 1% change in rate
        else:
            return {}

        return {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho
        }

    except Exception as e:
        logging.error(f"Error calculating Greeks: {e}")
        return {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0}
