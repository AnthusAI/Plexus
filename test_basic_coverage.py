#!/usr/bin/env python3
"""
Basic coverage test script for plexus modules
This tests individual modules without requiring the full dependency tree
"""
import sys
import os
import importlib.util

# Add current directory to path
sys.path.insert(0, '.')

def test_individual_module(module_path, module_name):
    """Test importing and basic functionality of an individual module"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            print(f"✗ Failed to load spec for {module_name}")
            return False
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"✓ Successfully imported {module_name}")
        return True
    except Exception as e:
        print(f"✗ Failed to import {module_name}: {e}")
        return False

def find_python_files(directory):
    """Find all Python files in a directory"""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        if '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                python_files.append(os.path.join(root, file))
    return python_files

def main():
    print("Basic Python Module Coverage Test")
    print("=" * 50)
    
    # Test CLI modules specifically
    cli_files = find_python_files('plexus/cli')
    
    success_count = 0
    total_count = 0
    
    print("\nTesting CLI modules:")
    for file_path in cli_files:
        if 'test' not in file_path and '__' not in os.path.basename(file_path):
            total_count += 1
            module_name = os.path.basename(file_path)[:-3]  # Remove .py
            if test_individual_module(file_path, module_name):
                success_count += 1
    
    # Test other key modules
    key_modules = [
        'plexus/_version.py',
        'plexus/plexus_logging/__init__.py',
        'plexus/utils/__init__.py'
    ]
    
    print("\nTesting key utility modules:")
    for file_path in key_modules:
        if os.path.exists(file_path):
            total_count += 1
            module_name = os.path.basename(file_path)[:-3]
            if test_individual_module(file_path, module_name):
                success_count += 1
    
    print(f"\nResults:")
    print(f"Successfully imported: {success_count}/{total_count} modules")
    print(f"Coverage percentage: {(success_count/total_count)*100:.1f}%")
    
    # Count total Python files for context
    all_python_files = find_python_files('plexus')
    test_files = find_python_files('plexus/tests')
    non_test_files = [f for f in all_python_files if 'test' not in f and '__pycache__' not in f]
    
    print(f"\nContext:")
    print(f"Total Python files in plexus/: {len(non_test_files)}")
    print(f"Test files: {len(test_files)}")
    print(f"Modules tested: {total_count}")

if __name__ == "__main__":
    main()