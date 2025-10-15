#!/usr/bin/env python3
"""
Final comprehensive import fixing script for CLI restructuring
"""

import os
import re
import glob

def fix_remaining_imports_in_file(file_path):
    """Fix any remaining import issues in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Comprehensive list of import fixes
        REMAINING_IMPORT_FIXES = [
            # Any remaining old command class references
            (r'from plexus\.cli\.([A-Z]\w*Commands) import', r'from plexus.cli.\1 import'),
            (r'import plexus\.cli\.([A-Z]\w*Commands)', r'import plexus.cli.\1'),
            
            # Specific pattern fixes that might remain
            (r'plexus\.cli\.report\.reports\.', 'plexus.cli.report.report_commands.'),
            (r'plexus\.cli\.score\.scores\.', 'plexus.cli.score.score_commands.'),
            (r'plexus\.cli\.task\.tasks\.', 'plexus.cli.task.task_commands.'),
            (r'plexus\.cli\.item\.items\.', 'plexus.cli.item.item_commands.'),
            (r'plexus\.cli\.prediction\.predictions\.', 'plexus.cli.prediction.prediction_commands.'),
            (r'plexus\.cli\.scorecard\.scorecards\.', 'plexus.cli.scorecard.scorecard_commands.'),
            (r'plexus\.cli\.evaluation\.evaluations\.', 'plexus.cli.evaluation.evaluation_commands.'),
            (r'plexus\.cli\.feedback\.commands\.', 'plexus.cli.feedback.feedback_commands.'),
            (r'plexus\.cli\.analyze\.analysis\.', 'plexus.cli.analyze.analyze_commands.'),
            (r'plexus\.cli\.batch\.operations\.', 'plexus.cli.batch.batch_commands.'),
            (r'plexus\.cli\.cost\.analysis\.', 'plexus.cli.cost.cost_commands.'),
            (r'plexus\.cli\.data\.data\.', 'plexus.cli.data.data_commands.'),
            (r'plexus\.cli\.dataset\.datasets\.', 'plexus.cli.dataset.dataset_commands.'),
            (r'plexus\.cli\.record_count\.counting\.', 'plexus.cli.record_count.count_commands.'),
            (r'plexus\.cli\.result\.results\.', 'plexus.cli.result.result_commands.'),
            (r'plexus\.cli\.score_chat\.chat\.', 'plexus.cli.score_chat.chat_commands.'),
            (r'plexus\.cli\.training\.training\.', 'plexus.cli.training.training_commands.'),
            (r'plexus\.cli\.tuning\.tuning\.', 'plexus.cli.tuning.tuning_commands.'),
            (r'plexus\.cli\.data_lake\.lake\.', 'plexus.cli.data_lake.lake_commands.'),
            
            # But actually, let's be more specific and fix the actual module names:
            (r'plexus\.cli\.record_count\.count_commands\.', 'plexus.cli.record_count.counting.'),
            (r'plexus\.cli\.analyze\.analyze_commands\.', 'plexus.cli.analyze.analysis.'),
            (r'plexus\.cli\.batch\.batch_commands\.', 'plexus.cli.batch.operations.'),
            (r'plexus\.cli\.cost\.cost_commands\.', 'plexus.cli.cost.analysis.'),
            (r'plexus\.cli\.data\.data_commands\.', 'plexus.cli.data.data.'),
            (r'plexus\.cli\.dataset\.dataset_commands\.', 'plexus.cli.dataset.datasets.'),
            (r'plexus\.cli\.evaluation\.evaluation_commands\.', 'plexus.cli.evaluation.evaluations.'),
            (r'plexus\.cli\.feedback\.feedback_commands\.', 'plexus.cli.feedback.commands.'),
            (r'plexus\.cli\.item\.item_commands\.', 'plexus.cli.item.items.'),
            (r'plexus\.cli\.prediction\.prediction_commands\.', 'plexus.cli.prediction.predictions.'),
            (r'plexus\.cli\.result\.result_commands\.', 'plexus.cli.result.results.'),
            (r'plexus\.cli\.score\.score_commands\.', 'plexus.cli.score.scores.'),
            (r'plexus\.cli\.score_chat\.chat_commands\.', 'plexus.cli.score_chat.chat.'),
            (r'plexus\.cli\.scorecard\.scorecard_commands\.', 'plexus.cli.scorecard.scorecards.'),
            (r'plexus\.cli\.task\.task_commands\.', 'plexus.cli.task.tasks.'),
            (r'plexus\.cli\.training\.training_commands\.', 'plexus.cli.training.training.'),
            (r'plexus\.cli\.tuning\.tuning_commands\.', 'plexus.cli.tuning.tuning.'),
            (r'plexus\.cli\.data_lake\.lake_commands\.', 'plexus.cli.data_lake.lake.'),
        ]
        
        # Apply the fixes
        changed = False
        for pattern, replacement in REMAINING_IMPORT_FIXES:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                changed = True
        
        # Write back if changed
        if changed:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Fix remaining imports in all relevant files"""
    files_changed = 0
    
    # Find all Python files
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
    
    print(f"Checking {len(files_to_check)} files for remaining import issues...")
    
    for file_path in sorted(files_to_check):
        if fix_remaining_imports_in_file(file_path):
            print(f"Fixed remaining imports in: {file_path}")
            files_changed += 1
    
    print(f"Fixed remaining imports in {files_changed} files")

if __name__ == '__main__':
    main()