#!/usr/bin/env python3
"""
Test runner script for the Plexus MCP Server tests
"""
import sys
import os
import subprocess
from pathlib import Path

def run_tests(test_type="all", verbose=True, coverage=True):
    """
    Run tests with various options
    
    Args:
        test_type: "unit", "integration", or "all"
        verbose: Enable verbose output
        coverage: Generate coverage report
    """
    # Get the MCP directory
    mcp_dir = Path(__file__).parent.parent
    os.chdir(mcp_dir)
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test path based on type
    if test_type == "unit":
        cmd.append("tests/unit/")
    elif test_type == "integration":
        cmd.append("tests/integration/")
    elif test_type == "all":
        cmd.append("tests/")
    else:
        raise ValueError(f"Unknown test type: {test_type}")
    
    # Add options
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend([
            "--cov=shared",
            "--cov=tools",
            "--cov=server",
            "--cov-report=term-missing",
            "--cov-report=html:tests/coverage_html"
        ])
    
    # Add markers
    cmd.extend(["-m", f"{test_type}" if test_type != "all" else "unit or integration"])
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with return code: {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest pytest-cov pytest-asyncio")
        return 1

def main():
    """Main entry point for test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Plexus MCP Server tests")
    parser.add_argument(
        "--type", 
        choices=["unit", "integration", "all"], 
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--no-verbose", 
        action="store_true", 
        help="Disable verbose output"
    )
    parser.add_argument(
        "--no-coverage", 
        action="store_true", 
        help="Disable coverage reporting"
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install test dependencies before running tests"
    )
    
    args = parser.parse_args()
    
    if args.install_deps:
        print("Installing test dependencies...")
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "pytest", "pytest-cov", "pytest-asyncio", "pytest-mock"
        ], check=True)
    
    return run_tests(
        test_type=args.type,
        verbose=not args.no_verbose,
        coverage=not args.no_coverage
    )

if __name__ == "__main__":
    sys.exit(main())