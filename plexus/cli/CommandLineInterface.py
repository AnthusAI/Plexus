import click
from rich.console import Console
from collections import OrderedDict
from .DataCommands import data
from .EvaluationCommands import evaluate
from .TrainingCommands import train
from .ReportingCommands import report
from .PredictionCommands import predict
from  .console import console

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
