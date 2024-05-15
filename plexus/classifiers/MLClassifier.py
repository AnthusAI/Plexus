import os
import inspect
import pandas as pd
from abc import ABC, abstractmethod
import mlflow.pyfunc
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import print as rich_print

from plexus.CustomLogging import logging
from plexus.classifiers.Classifier import Classifier

class MLClassifier(Classifier, mlflow.pyfunc.PythonModel):
    """
    Abstract class for a machine-learning classifier, with functions for the various states of ML model development.
    """

    def __init__(self, **parameters):
        logging.info("Initializing [magenta1][b]BERTForSequenceClassificationForControlFreaks[/b][/magenta1]")
        for name, value in parameters.items():
            logging.info(f"Setting [royal_blue1]{name}[/royal_blue1] to [magenta]{value}[/magenta]")
            setattr(self, name, value)
        self.set_up_mlflow()

    def name(self):
        # Get the name of the enclosing folder of the subclass
        subclass_file = inspect.getfile(self.__class__)
        folder_name = os.path.basename(os.path.dirname(subclass_file))
        # Concatenate the folder name and the class name to create the data_filename
        computed_name = folder_name + "_" + self.__class__.__name__
        logging.info(f"Classifier name: {computed_name}")
        return computed_name

    def set_up_mlflow(self):
        experiment_name = f"{self.scorecard_name} - {self.score_name}"
        if os.getenv('MLFLOW_EXPERIMENT_NAME'):
            experiment_name = experiment_name + " - " + os.getenv('MLFLOW_EXPERIMENT_NAME')
        logging.info(f"Setting MLFLow experiment name to [magenta1][b]{experiment_name}[/b][/magenta1]")
        mlflow.set_experiment(experiment_name)

        mlflow_tracking_uri = os.getenv('MLFLOW_TRACKING_URI')
        if mlflow_tracking_uri:
            logging.info(f"Using MLFlow tracking URL: {mlflow_tracking_uri}")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        else:
            mlflow.set_tracking_uri(f'file:///{os.path.abspath("./mlruns")}')

        try:
            mlflow.start_run()
        except Exception as e:
            logging.error("Error: ", e)
            logging.info("Attempting to end the previous run and start a new one.")
            mlflow.end_run()
            mlflow.start_run()

    def load_data(self, *, queries):
        """
        Load the specified queries from the training data lake, with caching, into a combined DataFrame in the class instance.
        """

        from plexus.DataCache import DataCache
        data_cache = DataCache(os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME'],
                                os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME'],
                                os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME'])
        self.dataframe = data_cache.load_dataframe(queries=queries)
        self.analyze_dataset()

    def analyze_dataset(self):
        panels = []

        # Answer Breakdown Table
        answer_breakdown_table = Table(
            title="[royal_blue1][b]Answer Breakdown[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        answer_breakdown_table.add_column("Answer", justify="right", style="royal_blue1", no_wrap=True)
        answer_breakdown_table.add_column("Count", style="magenta1", justify="right")
        answer_breakdown_table.add_column("Percentage", style="magenta1 bold", justify="right")

        answer_counts = self.dataframe[self.score_name].value_counts()
        total_responses = answer_counts.sum()
        for answer_value, count in answer_counts.items():
            percentage_of_total = (count / total_responses) * 100
            formatted_percentage = f"{percentage_of_total:.1f}%"
            answer_breakdown_table.add_row(str(answer_value), str(count), formatted_percentage)

        panels.append(Panel(answer_breakdown_table, border_style="royal_blue1"))

        # Dataframe Summary Table
        dataframe_summary_title = "[royal_blue1][b]Dataframe Summary[/b][/royal_blue1]"
        dataframe_summary_table = Table(
            title=dataframe_summary_title,
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        dataframe_summary_table.add_column("Description", justify="right", style="royal_blue1", no_wrap=True)
        dataframe_summary_table.add_column("Value", style="magenta1", justify="right")
        dataframe_summary_table.add_row("Number of Rows", str(self.dataframe.shape[0]), style="magenta1 bold")
        dataframe_summary_table.add_row("Number of Columns", str(self.dataframe.shape[1]))
        dataframe_summary_table.add_row("Total Cells", str(self.dataframe.size))

        smallest_answer_count = answer_counts.min()
        total_kinds_of_non_null_answers = self.dataframe[self.score_name].nunique()
        total_balanced_count = smallest_answer_count * total_kinds_of_non_null_answers

        dataframe_summary_table.add_row("Smallest Count", str(smallest_answer_count))
        dataframe_summary_table.add_row("Total Balanced Count", str(total_balanced_count), style="magenta1 bold")

        panels.append(Panel(dataframe_summary_table, border_style="royal_blue1"))

        # Column Names Table
        column_names_table = Table(
            title="[royal_blue1][b]Column Names[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        column_names_table.add_column("Column Name", style="magenta1")
        for column_name in self.dataframe.columns:
            column_names_table.add_row(column_name)

        panels.append(Panel(column_names_table, border_style="royal_blue1"))

        # Combine all panels into columns
        columns = Columns(panels)
        header_text = f"[bold royal_blue1]{self.score_name}[/bold royal_blue1]"

        # Display the combined panels
        rich_print(Panel(columns, title=header_text, border_style="magenta1"))

    def process_data(self):
        """
        Handle any pre-processing of the training data, including the training/validation splits.
        """
        
        filtered_dataframe = self.dataframe[[self.score_name, "Transcription"]]
        self.dataframe = filtered_dataframe

        self.analyze_dataset()

    @abstractmethod
    def train_model(self):
        """
        Train the model on the training data.

        :return: The trained model.
        """
        pass

    @abstractmethod
    def evaluate_model(self):
        """
        Evaluate the model on the validation data.

        :return: The evaluation results.
        """
        pass

    @abstractmethod
    def register_model(self):
        """
        Register the model with the model registry.
        """
        pass

    @abstractmethod
    def predict(self, context, model_input):
        """
        Make predictions on the test data.

        :param context: MLflow context for the prediction.
        :param model_input: The input data for making predictions.
        :return: The predictions.
        """
        pass

    def is_relevant(self, text):
        """
        Implement the is_relevant method using the predict method for ML classifiers.
        """
        # Ensure text is a single line by replacing newlines and stripping whitespace
        clean_text = text.replace('\n', ' ').strip()
        # Create a DataFrame with the cleaned text
        model_input = pd.DataFrame([clean_text], columns=['text'])
        # Call the predict method with the model_input DataFrame
        prediction = self.predict(model_input)['prediction'].iloc[0]
        return prediction == '__label__relevant'

