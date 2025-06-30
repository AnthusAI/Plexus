#!/usr/bin/env python3
"""
Test coverage runner for ReportBlock functionality.
Runs individual coverage reports to avoid import issues.
"""
import subprocess
import sys
import os

def run_coverage_test(test_file, module_path, output_dir):
    """Run coverage test for a specific test file."""
    print(f"\n{'='*60}")
    print(f"Running coverage for: {test_file}")
    print(f"Module: {module_path}")
    print(f"{'='*60}")
    
    cmd = [
        sys.executable, "-m", "pytest", 
        test_file,
        f"--cov={module_path}",
        "--cov-report=term-missing",
        f"--cov-report=html:{output_dir}",
        "-v"
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f".:{env.get('PYTHONPATH', '')}"
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        print(f"Return code: {result.returncode}")
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Test timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"Error running test: {e}")
        return False

def main():
    """Run coverage tests for all ReportBlock test files."""
    
    # Test configurations: (test_file, module_path, output_dir)
    test_configs = [
        ("plexus/reports/blocks/base_test.py", "plexus.reports.blocks.base", "htmlcov_base"),
        ("plexus/reports/blocks/report_block_orm_test.py", "plexus.reports.blocks.report_block_orm", "htmlcov_orm"),
        ("plexus/reports/blocks/score_info_test.py", "plexus.reports.blocks.score_info", "htmlcov_score_info"),
        ("plexus/reports/blocks/data_utils_test.py", "plexus.reports.blocks.data_utils", "htmlcov_data_utils"),
    ]
    
    print("ReportBlock Test Coverage Runner")
    print("=" * 60)
    
    results = {}
    
    for test_file, module_path, output_dir in test_configs:
        if os.path.exists(test_file):
            success = run_coverage_test(test_file, module_path, output_dir)
            results[test_file] = success
        else:
            print(f"\nSkipping {test_file} - file not found")
            results[test_file] = False
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    for test_file, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} {test_file}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    print(f"\nTotal: {total_tests}, Passed: {passed_tests}, Failed: {total_tests - passed_tests}")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 