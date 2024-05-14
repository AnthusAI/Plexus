import os
import click
from plexus.DataCache import DataCache
from rich import print as rich_print
from rich.table import Table
from plexus.logging import logging
from rich.layout import Layout
from rich.panel import Panel
from rich.columns import Columns
from plexus.cli.console import console
from plexus.Registries import scorecard_registry

from plexus.scorecards.TermLifeAI import TermLifeAI

from dotenv import load_dotenv
response = load_dotenv('./.env')

@click.group()
def data():
    """Profiling the data available for each score in the scorecard."""
    pass

@data.command()
@click.option('--scorecard-name', required=True, help='The name of the scorecard to load data for')
@click.option('--question-name', required=False, help='The name of the question to analyze for answer breakdown')
@click.option('--all', 'all_questions', is_flag=True, help='Analyze all questions in the scorecard')
def analyze(scorecard_name, question_name, all_questions):
    logging.info(f"Analyzing data for scorecard [purple][b]{scorecard_name}[/b][/purple]")
    analyze_scorecard(scorecard_name, question_name, all_questions)

def analyze_scorecard(scorecard_name, question_name, all_questions):
    
    # First, find the scorecard class from the name.
    scorecard_type = scorecard_registry.get(scorecard_name)
    if scorecard_type is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return
    scorecard_id = scorecard_type.scorecard_id()

    scorecard_folder = os.path.join('.', 'scorecards', scorecard_name)
    scorecard_instance = scorecard_type(scorecard_folder_path=scorecard_folder)
    logging.info(f"Using scorecard key [purple][b]{scorecard_name}[/b][/purple] with class name [purple][b]{scorecard_instance.__class__.__name__}[/b][/purple]")

    data_cache = DataCache(os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME'],
                           os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME'],
                           os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME'])
    dataframe = data_cache.load_dataframe(scorecard_id=scorecard_id)

    print('')

    if (question_name or all_questions):
        grid = Table.grid(expand=True)
        grid.add_column()
        
        if question_name:
            columns = analyze_question(scorecard_id, question_name, dataframe)
            question_panel = Panel(columns, title=f"[royal_blue1][b]Question: {question_name}[/b][/royal_blue1]", border_style="magenta1")
            grid.add_row(question_panel)
        else:
            # This means --all
            for question_name in scorecard_instance.score_names():
                columns = analyze_question(scorecard_id, question_name, dataframe)
                question_panel = Panel(columns, title=f"[royal_blue1][b]Question: {question_name}[/b][/royal_blue1]", border_style="magenta1")
                grid.add_row(question_panel)

        outer_panel = Panel(grid,
            title=f"[royal_blue1][b]Scorecard: {scorecard_name}[/b][/royal_blue1]", border_style="magenta1")

        rich_print(outer_panel)
    else:
        dataframe_summary_title = "[royal_blue1][b]Dataframe Summary[/b][/royal_blue1]\nfor [purple][b]Scorecard ID: " + scorecard_id
        dataframe_summary_table = Table(
            title=dataframe_summary_title,
            header_style="sky_blue1",
            border_style="sky_blue1")
        dataframe_summary_table.add_column("Description", justify="right", style="royal_blue1", no_wrap=True)
        dataframe_summary_table.add_column("Value", style="magenta1", justify="right")
        dataframe_summary_table.add_row("Number of Rows", str(dataframe.shape[0]), style="magenta1 bold")
        dataframe_summary_table.add_row("Number of Columns", str(dataframe.shape[1]))
        dataframe_summary_table.add_row("Total Cells", str(dataframe.size))

        column_names_table = Table(
            title="[royal_blue1][b]Column Names[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1")
        column_names_table.add_column("Column Name", style="magenta1")
        for column_name in dataframe.columns:
            column_names_table.add_row(column_name)

        outer_panel = Panel(
            Columns([dataframe_summary_table, column_names_table]),
            title=f"[royal_blue1][b]Scorecard: {scorecard_name}[/b][/royal_blue1]", border_style="magenta1")

        rich_print(outer_panel)

def analyze_question(scorecard_id, question_name, dataframe):
    panels = []

    question_analysis_table = Table(
        title="[royal_blue1][b]Answer Breakdown[/b][/royal_blue1]",
        header_style="sky_blue1",
        border_style="sky_blue1")
    question_analysis_table.add_column("Answer", justify="right", style="royal_blue1", no_wrap=True)
    question_analysis_table.add_column("Count", style="magenta1", justify="right")
    question_analysis_table.add_column("Percentage", style="magenta1 bold", justify="right")

    answer_counts = dataframe[question_name].value_counts()
    total_responses = answer_counts.sum()
    for answer_value, count in answer_counts.items():
        percentage_of_total = (count / total_responses) * 100
        formatted_percentage = f"{percentage_of_total:.1f}%"
        question_analysis_table.add_row(str(answer_value), str(count), formatted_percentage)

    panels.append(Panel(question_analysis_table, border_style="royal_blue1"))

    dataframe_summary_title = "[royal_blue1][b]Dataframe Summary[/b][/royal_blue1]"
    dataframe_summary_table = Table(
        title=dataframe_summary_title,
        header_style="sky_blue1",
        border_style="sky_blue1")
    dataframe_summary_table.add_column("Description", justify="right", style="royal_blue1", no_wrap=True)
    dataframe_summary_table.add_column("Value", style="magenta1", justify="right")
    dataframe_summary_table.add_row("Number of Rows", str(dataframe.shape[0]), style="magenta1 bold")

    smallest_answer_count = answer_counts.min()
    total_kinds_of_non_null_answers = dataframe[question_name].nunique()
    total_balanced_count = smallest_answer_count * total_kinds_of_non_null_answers

    dataframe_summary_table.add_row("Smallest Count", str(smallest_answer_count))
    dataframe_summary_table.add_row("Total Balanced Count", str(total_balanced_count), style="magenta1 bold")

    panels.append(Panel(dataframe_summary_table, border_style="royal_blue1"))

    columns = Columns(panels)
    if question_name:   
        header_text = f"[bold royal_blue1]{question_name}[/bold royal_blue1]"
    else:
        header_text = f"[bold royal_blue1]{scorecard_name}[/bold royal_blue1]"

    return columns