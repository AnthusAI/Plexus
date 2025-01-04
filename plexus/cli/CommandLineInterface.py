import os
import sys
import click
import importlib
import builtins
from rich.console import Console
from collections import OrderedDict
from .DataCommands import data
from .EvaluationCommands import evaluate
from .TrainingCommands import train
from .ReportingCommands import report
from .PredictionCommands import predict
from .TuningCommands import tuning
from .AnalyzeCommands import analyze
from .console import console
from .BatchCommands import batch
from .ActionCommands import action

from dotenv import load_dotenv
load_dotenv()

class OrderCommands(click.Group):
  def list_commands(self, ctx: click.Context) -> list[str]:
    return list(self.commands)

@click.group(cls=OrderCommands)
def main():
    """
    Plexus is an orchestration system for AI/ML content classification.

    For machine-learning scores that require data preparation, the `data` command includes subcommands for data analysis and preparation.

    For classifiers that require training, the `train` command includes subcommands for training and evaluating models, using MLFlow for logging experiment results.

    For evaluating LLM-based classifiers for prompt engineering, the `evaluate` command includes subcommands for evaluating prompts.

    For scoring content at inference time, the `score` command includes subcommands for scoring content.  The scoring reports will not include accuracy metrics.

    For reporting on training and evaluation results, the `report` command includes subcommands for generating reports.

    For more information, please visit https://plexus.anth.us
    """
    pass

main.add_command(data)
main.add_command(evaluate)
main.add_command(train)
main.add_command(report)
main.add_command(predict)
main.add_command(tuning)
main.add_command(analyze)
main.add_command(batch)
main.add_command(action)

def load_plexus_extensions():
    print("Loading Plexus extensions...")
    # Define the path to the `plexus_extensions` directory
    extensions_path = os.path.join(os.getcwd(), 'plexus_extensions')
    
    # Add the `plexus_extensions` path to `sys.path` if it exists
    if os.path.isdir(extensions_path):
        sys.path.insert(0, extensions_path)
        sys.path.insert(0, os.path.join(os.getcwd(), '.'))

        # Walk through the `plexus_extensions` directory
        for root, _, files in os.walk(extensions_path):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    print(f"Loading extension: {file}")
                    # Construct the module name from the file path
                    module_name = file[:-3]  # Remove `.py` from the filename
                    
                    # Import the module and print debug info
                    imported_module = importlib.import_module(module_name)
                    print(f"Loaded extension module: {module_name}")
                    
                    # Register each class in the module by adding it to builtins
                    for attr_name in dir(imported_module):
                        attr = getattr(imported_module, attr_name)
                        if isinstance(attr, type):  # Check if attr is a class
                            setattr(builtins, attr_name, attr)  # Register in builtins
                            print(f"Registered class {attr_name} globally in builtins")
    else:
        print("No extensions folder found.")

# Call this function during CLI initialization
load_plexus_extensions()