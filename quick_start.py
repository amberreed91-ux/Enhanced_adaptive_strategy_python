#!/usr/bin/env python3
"""
Quick start script to test installation and generate first backtest.
"""
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if all required packages are installed."""
    print("Checking dependencies...")

    required = [
        'pandas', 'numpy', 'xgboost', 'stable_baselines3', 
        'pypfopt', 'sqlalchemy', 'loguru', 'pydantic', 'gymnasium'
    ]

    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - MISSING")
            missing.append(package)

    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False

    print("\n✅ All dependencies installed\n")
    return True


def check_config():
    """Check if configuration exists."""
    print("Checking configuration...")

    config_file = Path("config/config.yaml")
    if not config_file.exists():
        print("  ✗ config/config.yaml not found")
        return False

    print("  ✓ config/config.yaml exists")

    env_file = Path(".env")
    if not env_file.exists():
        print("  ⚠ .env not found (using defaults)")
    else:
        print("  ✓ .env exists")

    print("\n✅ Configuration ready\n")
    return True


def generate_data():
    """Generate sample data if not exists."""
    print("Checking for sample data...")

    data_file = Path("data/historical/sample_data.csv")

    if data_file.exists():
        print(f"  ✓ Sample data exists ({data_file})")
        return str(data_file)

    print("  Generating sample data...")
    try:
        subprocess.run([
            sys.executable,
            "generate_sample_data.py",
            "--output", str(data_file),
            "--bars", "5000"
        ], check=True)
        print(f"  ✓ Generated sample data ({data_file})")
        return str(data_file)
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed to generate data: {e}")
        return None


def run_backtest(data_file):
    """Run a quick backtest."""
    print("\nRunning backtest...")
    print("This may take a few minutes...\n")

    try:
        subprocess.run([
            sys.executable,
            "backtest.py",
            "--data", data_file,
            "--output", "results/quickstart",
            "--no-train",  # Skip ML training for quick start
            "--log-level", "INFO"
        ], check=True)

        print("\n✅ Backtest complete!\n")
        print("Results saved to: results/quickstart/")
        print("  - trades.csv: Individual trade details")
        print("  - equity_curve.csv: Portfolio value over time")
        print("\nNext steps:")
        print("  1. Review results in results/quickstart/")
        print("  2. Train ML models: python train_models.py --data", data_file)
        print("  3. Customize config: edit config/config.yaml")
        print("  4. Read setup guide: docs/setup_guide.md")

        return True

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Backtest failed: {e}")
        return False


def main():
    """Main quick start routine."""
    print("="*60)
    print("ENHANCED ADAPTIVE STRATEGY - QUICK START")
    print("="*60)
    print()

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check config
    if not check_config():
        sys.exit(1)

    # Generate or find data
    data_file = generate_data()
    if not data_file:
        sys.exit(1)

    print("\n✅ Setup complete\n")

    # Run backtest
    run_backtest(data_file)


if __name__ == '__main__':
    main()
