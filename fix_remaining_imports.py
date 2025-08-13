#!/usr/bin/env python3
"""
Fix remaining import issues after CLI restructuring
This script looks for specific import patterns that need to be updated
"""

import os
import re
import glob

def fix_imports_in_file(file_path):
    """Fix imports in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Import patterns that need fixing
        IMPORT_FIXES = [
            # CLI module imports that are now in shared/
            (r'from plexus\.cli\.client_utils import', 'from plexus.cli.shared.client_utils import'),
            (r'from plexus\.cli\.identifier_resolution import', 'from plexus.cli.shared.identifier_resolution import'),
            (r'from plexus\.cli\.console import', 'from plexus.cli.shared.console import'),
            (r'from plexus\.cli\.file_editor import', 'from plexus.cli.shared.file_editor import'),
            (r'from plexus\.cli\.shared import', 'from plexus.cli.shared.shared import'),
            (r'from plexus\.cli\.utils import', 'from plexus.cli.shared.utils import'),
            (r'from plexus\.cli\.dependency_discovery import', 'from plexus.cli.shared.dependency_discovery import'),
            (r'import plexus\.cli\.client_utils', 'import plexus.cli.shared.client_utils'),
            (r'import plexus\.cli\.identifier_resolution', 'import plexus.cli.shared.identifier_resolution'),
            (r'import plexus\.cli\.console', 'import plexus.cli.shared.console'),
            (r'import plexus\.cli\.file_editor', 'import plexus.cli.shared.file_editor'),
            (r'import plexus\.cli\.shared', 'import plexus.cli.shared.shared'),
            (r'import plexus\.cli\.utils', 'import plexus.cli.shared.utils'),
            (r'import plexus\.cli\.dependency_discovery', 'import plexus.cli.shared.dependency_discovery'),
            
            # Command class imports that are now in subdirectories
            (r'from plexus\.cli\.ScorecardCommands import', 'from plexus.cli.scorecard.scorecards import'),
            (r'from plexus\.cli\.ScoreCommands import', 'from plexus.cli.score.scores import'),
            (r'from plexus\.cli\.TaskCommands import', 'from plexus.cli.task.tasks import'),
            (r'from plexus\.cli\.ItemCommands import', 'from plexus.cli.item.items import'),
            (r'from plexus\.cli\.EvaluationCommands import', 'from plexus.cli.evaluation.evaluations import'),
            (r'from plexus\.cli\.PredictionCommands import', 'from plexus.cli.prediction.predictions import'),
            (r'from plexus\.cli\.ReportCommands import', 'from plexus.cli.report.reports import'),
            (r'from plexus\.cli\.FeedbackCommands import', 'from plexus.cli.feedback.commands import'),
            (r'from plexus\.cli\.CostCommands import', 'from plexus.cli.cost.costs import'),
            (r'from plexus\.cli\.DataCommands import', 'from plexus.cli.data.data import'),
            (r'from plexus\.cli\.DatasetCommands import', 'from plexus.cli.dataset.datasets import'),
            (r'from plexus\.cli\.AnalyzeCommands import', 'from plexus.cli.analyze.analysis import'),
            (r'from plexus\.cli\.BatchCommands import', 'from plexus.cli.batch.operations import'),
            (r'from plexus\.cli\.TrainingCommands import', 'from plexus.cli.training.training import'),
            (r'from plexus\.cli\.TuningCommands import', 'from plexus.cli.tuning.tuning import'),
            (r'from plexus\.cli\.ScoreChatCommands import', 'from plexus.cli.score_chat.chat import'),
            (r'from plexus\.cli\.ResultCommands import', 'from plexus.cli.result.results import'),
            (r'from plexus\.cli\.RecordCountCommands import', 'from plexus.cli.record_count.counts import'),
            (r'from plexus\.cli\.DataLakeCommands import', 'from plexus.cli.data_lake.lake import'),
            
            (r'import plexus\.cli\.ScorecardCommands', 'import plexus.cli.scorecard.scorecards'),
            (r'import plexus\.cli\.ScoreCommands', 'import plexus.cli.score.scores'),
            (r'import plexus\.cli\.TaskCommands', 'import plexus.cli.task.tasks'),
            (r'import plexus\.cli\.ItemCommands', 'import plexus.cli.item.items'),
            (r'import plexus\.cli\.EvaluationCommands', 'import plexus.cli.evaluation.evaluations'),
            (r'import plexus\.cli\.PredictionCommands', 'import plexus.cli.prediction.predictions'),
            (r'import plexus\.cli\.ReportCommands', 'import plexus.cli.report.reports'),
            (r'import plexus\.cli\.FeedbackCommands', 'import plexus.cli.feedback.commands'),
            (r'import plexus\.cli\.CostCommands', 'import plexus.cli.cost.costs'),
            (r'import plexus\.cli\.DataCommands', 'import plexus.cli.data.data'),
            (r'import plexus\.cli\.DatasetCommands', 'import plexus.cli.dataset.datasets'),
            (r'import plexus\.cli\.AnalyzeCommands', 'import plexus.cli.analyze.analysis'),
            (r'import plexus\.cli\.BatchCommands', 'import plexus.cli.batch.operations'),
            (r'import plexus\.cli\.TrainingCommands', 'import plexus.cli.training.training'),
            (r'import plexus\.cli\.TuningCommands', 'import plexus.cli.tuning.tuning'),
            (r'import plexus\.cli\.ScoreChatCommands', 'import plexus.cli.score_chat.chat'),
            (r'import plexus\.cli\.ResultCommands', 'import plexus.cli.result.results'),
            (r'import plexus\.cli\.RecordCountCommands', 'import plexus.cli.record_count.counts'),
            (r'import plexus\.cli\.DataLakeCommands', 'import plexus.cli.data_lake.lake'),
            
            # Patch targets for tests
            (r"'plexus\.cli\.client_utils\.", "'plexus.cli.shared.client_utils."),
            (r"'plexus\.cli\.identifier_resolution\.", "'plexus.cli.shared.identifier_resolution."),
            (r"'plexus\.cli\.console\.", "'plexus.cli.shared.console."),
            (r"'plexus\.cli\.file_editor\.", "'plexus.cli.shared.file_editor."),
            (r"'plexus\.cli\.shared\.", "'plexus.cli.shared.shared."),
            (r"'plexus\.cli\.utils\.", "'plexus.cli.shared.utils."),
            (r"'plexus\.cli\.dependency_discovery\.", "'plexus.cli.shared.dependency_discovery."),
            (r"'plexus\.cli\.ScorecardCommands\.", "'plexus.cli.scorecard.scorecards."),
            (r"'plexus\.cli\.ScoreCommands\.", "'plexus.cli.score.scores."),
            (r"'plexus\.cli\.TaskCommands\.", "'plexus.cli.task.tasks."),
            (r"'plexus\.cli\.ItemCommands\.", "'plexus.cli.item.items."),
            (r"'plexus\.cli\.EvaluationCommands\.", "'plexus.cli.evaluation.evaluations."),
            (r"'plexus\.cli\.PredictionCommands\.", "'plexus.cli.prediction.predictions."),
            (r"'plexus\.cli\.ReportCommands\.", "'plexus.cli.report.reports."),
            (r"'plexus\.cli\.FeedbackCommands\.", "'plexus.cli.feedback.commands."),
            (r"'plexus\.cli\.CostCommands\.", "'plexus.cli.cost.costs."),
            (r"'plexus\.cli\.DataCommands\.", "'plexus.cli.data.data."),
            (r"'plexus\.cli\.DatasetCommands\.", "'plexus.cli.dataset.datasets."),
            (r"'plexus\.cli\.AnalyzeCommands\.", "'plexus.cli.analyze.analysis."),
            (r"'plexus\.cli\.BatchCommands\.", "'plexus.cli.batch.operations."),
            (r"'plexus\.cli\.TrainingCommands\.", "'plexus.cli.training.training."),
            (r"'plexus\.cli\.TuningCommands\.", "'plexus.cli.tuning.tuning."),
            (r"'plexus\.cli\.ScoreChatCommands\.", "'plexus.cli.score_chat.chat."),
            (r"'plexus\.cli\.ResultCommands\.", "'plexus.cli.result.results."),
            (r"'plexus\.cli\.RecordCountCommands\.", "'plexus.cli.record_count.counts."),
            (r"'plexus\.cli\.DataLakeCommands\.", "'plexus.cli.data_lake.lake."),
        ]
        
        # Apply the fixes
        for pattern, replacement in IMPORT_FIXES:
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
    """Fix imports in all relevant files"""
    files_changed = 0
    
    # Find all Python files that might have imports to fix
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
    
    print(f"Checking {len(files_to_check)} files for import issues...")
    
    for file_path in sorted(files_to_check):
        if fix_imports_in_file(file_path):
            print(f"Fixed imports in: {file_path}")
            files_changed += 1
    
    print(f"Fixed imports in {files_changed} files")

if __name__ == '__main__':
    main()