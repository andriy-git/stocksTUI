
import sys
import os
import logging

# Add project root to path
sys.path.append(os.getcwd())

from stockstui.data_providers import options_provider

# Configure logging
logging.basicConfig(level=logging.INFO)

def verify_options_provider():
    ticker = "SPY"
    print(f"Fetching expirations for {ticker}...")
    expirations = options_provider.get_available_expirations(ticker)
    
    if not expirations:
        print(f"❌ Failed to fetch expirations for {ticker}")
        return
    
    print(f"✅ Found {len(expirations)} expirations. First one: {expirations[0]}")
    
    target_date = expirations[0]
    print(f"Fetching options chain for {ticker} expiring {target_date}...")
    chain = options_provider.get_options_chain(ticker, target_date)
    
    if not chain:
        print(f"❌ Failed to fetch options chain")
        return
        
    calls = chain.get('calls')
    puts = chain.get('puts')
    underlying = chain.get('underlying')
    
    if calls is None or calls.empty:
        print("❌ Calls data is empty")
    else:
        print(f"✅ Calls data found: {len(calls)} rows")
        print(f"   Columns: {calls.columns.tolist()}")
        
        # Check for Greeks
        expected_greeks = ['delta', 'gamma', 'theta', 'vega']
        missing_greeks = [g for g in expected_greeks if g not in calls.columns]
        if missing_greeks:
            print(f"❌ Missing Greeks columns: {missing_greeks}")
        else:
            print("✅ Greeks columns present")
            # Print sample Greeks
            sample = calls.iloc[0]
            print(f"   Sample Greeks: Δ={sample.get('delta'):.2f}, Γ={sample.get('gamma'):.3f}, Θ={sample.get('theta'):.3f}, ν={sample.get('vega'):.3f}")
        
    if puts is None or puts.empty:
        print("❌ Puts data is empty")
    else:
        print(f"✅ Puts data found: {len(puts)} rows")
        
    if not underlying:
        print("❌ Underlying data missing")
    else:
        print(f"✅ Underlying data found: Price = {underlying.get('regularMarketPrice')}")

    # --- Test Position Tracking ---
    print("\nTesting Position Tracking...")
    from stockstui.database.db_manager import DbManager
    from pathlib import Path
    
    db_path = Path("test_db.sqlite")
    db = DbManager(db_path)
    
    symbol = "TEST_OPTION"
    db.save_option_position(symbol, "TEST", 5, 1.50)
    
    pos = db.get_option_position(symbol)
    if pos and pos['quantity'] == 5 and pos['avg_cost'] == 1.50:
        print(f"✅ Position saved and retrieved: {pos}")
    else:
        print(f"❌ Failed to save/retrieve position: {pos}")
        
    db.delete_option_position(symbol)
    pos = db.get_option_position(symbol)
    if pos is None:
        print("✅ Position deleted successfully")
    else:
        print(f"❌ Failed to delete position: {pos}")
        
    db.close()
    if db_path.exists():
        db_path.unlink()

    # --- Test Chart Logic ---
    print("\nTesting Chart Logic...")
    from stockstui.ui.widgets.oi_chart import OIChart
    try:
        chart = OIChart(calls, puts, 680.0)
        print("✅ OIChart initialized successfully")
    except Exception as e:
        print(f"❌ OIChart initialization failed: {e}")

    # Test Caching
    print("\nTesting Cache...")
    start_time = os.times().elapsed
    _ = options_provider.get_options_chain(ticker, target_date)
    end_time = os.times().elapsed
    print(f"✅ Cached fetch took {end_time - start_time:.4f}s")

if __name__ == "__main__":
    verify_options_provider()
