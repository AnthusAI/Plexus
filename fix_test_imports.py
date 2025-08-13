#!/usr/bin/env python3
"""
Fix test import issues systematically
"""

import os
import re
import glob

def fix_test_imports_in_file(file_path):
    """Fix test imports in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Common test import patterns that need fixing
        TEST_IMPORT_FIXES = [
            # Patch paths that should match the actual import structure
            (r"patch\('plexus\.cli\.cost\.costs\.", "patch('plexus.cli.cost.analysis."),
            (r"patch\('plexus\.cli\.data\.data\.", "patch('plexus.cli.data.data."),
            (r"patch\('plexus\.cli\.dataset\.datasets\.", "patch('plexus.cli.dataset.datasets."),
            (r"patch\('plexus\.cli\.item\.items\.", "patch('plexus.cli.item.items."),
            (r"patch\('plexus\.cli\.prediction\.predictions\.", "patch('plexus.cli.prediction.predictions."),
            (r"patch\('plexus\.cli\.report\.reports\.", "patch('plexus.cli.report.reports."),
            (r"patch\('plexus\.cli\.task\.tasks\.", "patch('plexus.cli.task.tasks."),
            (r"patch\('plexus\.cli\.score\.scores\.", "patch('plexus.cli.score.scores."),
            (r"patch\('plexus\.cli\.scorecard\.scorecards\.", "patch('plexus.cli.scorecard.scorecards."),
            (r"patch\('plexus\.cli\.analyze\.analysis\.", "patch('plexus.cli.analyze.analysis."),
            (r"patch\('plexus\.cli\.batch\.operations\.", "patch('plexus.cli.batch.operations."),
            (r"patch\('plexus\.cli\.evaluation\.evaluations\.", "patch('plexus.cli.evaluation.evaluations."),
            (r"patch\('plexus\.cli\.feedback\.commands\.", "patch('plexus.cli.feedback.commands."),
            (r"patch\('plexus\.cli\.record_count\.counts\.", "patch('plexus.cli.record_count.counts."),
            (r"patch\('plexus\.cli\.result\.results\.", "patch('plexus.cli.result.results."),
            (r"patch\('plexus\.cli\.score_chat\.chat\.", "patch('plexus.cli.score_chat.chat."),
            (r"patch\('plexus\.cli\.training\.training\.", "patch('plexus.cli.training.training."),
            (r"patch\('plexus\.cli\.tuning\.tuning\.", "patch('plexus.cli.tuning.tuning."),
            (r"patch\('plexus\.cli\.data_lake\.lake\.", "patch('plexus.cli.data_lake.lake."),
        ]
        
        # Apply the fixes
        for pattern, replacement in TEST_IMPORT_FIXES:
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
    """Fix test imports in all relevant files"""
    files_changed = 0
    
    # Find all test files
    patterns = [
        'plexus/**/*_test.py',
        'plexus/**/test_*.py',
        'tests/**/*.py',
        'MCP/**/*_test.py',
        'MCP/**/test_*.py',
    ]
    
    files_to_check = set()
    for pattern in patterns:
        files_to_check.update(glob.glob(pattern, recursive=True))
    
    # Filter out __pycache__ and other unwanted files
    files_to_check = [f for f in files_to_check if '__pycache__' not in f and f.endswith('.py')]
    
    print(f"Checking {len(files_to_check)} test files for import issues...")
    
    for file_path in sorted(files_to_check):
        if fix_test_imports_in_file(file_path):
            print(f"Fixed test imports in: {file_path}")
            files_changed += 1
    
    print(f"Fixed test imports in {files_changed} files")

if __name__ == '__main__':
    main()