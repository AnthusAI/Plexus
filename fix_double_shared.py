#!/usr/bin/env python3
"""
Fix double 'shared' paths in imports
"""

import os
import re
import glob

def fix_double_shared_in_file(file_path):
    """Fix double shared paths in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix double shared paths
        DOUBLE_SHARED_FIXES = [
            (r'plexus\.cli\.shared\.shared\.', 'plexus.cli.shared.'),
            (r'from plexus\.cli\.shared\.shared import', 'from plexus.cli.shared import'),
            (r'import plexus\.cli\.shared\.shared', 'import plexus.cli.shared'),
        ]
        
        # Apply the fixes
        for pattern, replacement in DOUBLE_SHARED_FIXES:
            content = re.sub(pattern, replacement, content)
        
        # Write back if changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Fix double shared paths in all files"""
    files_changed = 0
    
    # Find all Python files that might have double shared imports
    patterns = [
        'plexus/**/*.py',
        'tests/**/*.py',
        'MCP/**/*.py',
    ]
    
    files_to_check = set()
    for pattern in patterns:
        files_to_check.update(glob.glob(pattern, recursive=True))
    
    # Filter out __pycache__ and other unwanted files
    files_to_check = [f for f in files_to_check if '__pycache__' not in f and f.endswith('.py')]
    
    print(f"Checking {len(files_to_check)} files for double shared paths...")
    
    for file_path in sorted(files_to_check):
        if fix_double_shared_in_file(file_path):
            print(f"Fixed double shared paths in: {file_path}")
            files_changed += 1
    
    print(f"Fixed double shared paths in {files_changed} files")

if __name__ == '__main__':
    main()