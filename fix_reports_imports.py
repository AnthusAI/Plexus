#!/usr/bin/env python3
"""
Fix all remaining reports import issues
"""

import os
import re
import glob

def fix_reports_imports_in_file(file_path):
    """Fix reports import paths in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix reports import patterns
        REPORTS_IMPORT_FIXES = [
            # Direct imports
            (r'from plexus\.cli\.reports import', 'from plexus.cli.report import'),
            (r'import plexus\.cli\.reports', 'import plexus.cli.report'),
            
            # Module path references in patches
            (r'plexus\.cli\.reports\.utils\.', 'plexus.cli.report.utils.'),
            (r'plexus\.cli\.reports\.report_commands\.', 'plexus.cli.report.reports.'),
            (r'plexus\.cli\.reports\.config_commands', 'plexus.cli.report.config'),
            
            # Direct reports references
            (r'plexus\.cli\.reports', 'plexus.cli.report'),
        ]
        
        # Apply the fixes
        for pattern, replacement in REPORTS_IMPORT_FIXES:
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
    """Fix reports imports in all relevant files"""
    files_changed = 0
    
    # Find all Python files that might have reports imports
    patterns = [
        'plexus/**/*.py',
        'MCP/**/*.py',
        'tests/**/*.py',
    ]
    
    files_to_check = set()
    for pattern in patterns:
        files_to_check.update(glob.glob(pattern, recursive=True))
    
    # Filter out __pycache__ and other unwanted files
    files_to_check = [f for f in files_to_check if '__pycache__' not in f and f.endswith('.py')]
    
    print(f"Checking {len(files_to_check)} files for reports import issues...")
    
    for file_path in sorted(files_to_check):
        if fix_reports_imports_in_file(file_path):
            print(f"Fixed reports imports in: {file_path}")
            files_changed += 1
    
    print(f"Fixed reports imports in {files_changed} files")

if __name__ == '__main__':
    main()