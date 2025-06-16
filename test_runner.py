#!/usr/bin/env python3
"""
Simple test runner to check coverage for ReportBlock functionality
"""
import sys
import os
import subprocess

def run_coverage_test(module_path, test_path):
    """Run coverage test for a specific module"""
    cmd = [
        sys.executable, "-m", "pytest", 
        test_path,
        f"--cov={module_path}",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov_before",
        "-v"
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f".:{env.get('PYTHONPATH', '')}"
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
    print(f"Return code: {result.returncode}")
    
    return result.returncode == 0

if __name__ == "__main__":
    # Test individual modules
    modules_to_test = [
        ("plexus.reports.blocks.base", "plexus/reports/blocks/base_test.py"),
        ("plexus.reports.blocks.score_info", "plexus/reports/blocks/score_info_test.py"),
        ("plexus.reports.blocks.report_block_orm", None),  # No test file yet
    ]
    
    for module, test_file in modules_to_test:
        if test_file and os.path.exists(test_file):
            print(f"\n{'='*60}")
            print(f"Testing {module}")
            print(f"{'='*60}")
            run_coverage_test(module, test_file)
        else:
            print(f"\nSkipping {module} - no test file found") 