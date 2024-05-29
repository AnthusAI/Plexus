import os
import json
import mlflow
import inspect
import functools
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tensorflow.keras.utils import plot_model
from sklearn.metrics import confusion_matrix
from abc import ABC, abstractmethod
from sklearn.metrics import roc_curve, auc, precision_recall_curve
import matplotlib.ticker as ticker
import matplotlib.pyplot as plt
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import print as rich_print
from rich.text import Text
from matplotlib.colors import LinearSegmentedColormap
from plexus.cli.console import console
from plexus.CustomLogging import logging
from plexus.classifiers.Classifier import Classifier

class MLClassifier(Classifier):
    """
    Abstract class for a machine-learning classifier, with functions for the various states of ML model development.
    """

    def __init__(self, **parameters):
        super().__init__(**parameters)
        logging.info("Initializing [magenta1][b]MLClassifier[/b][/magenta1]")
        self.set_up_mlflow()
        self._is_multi_class = None

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

        mlflow.log_param("classifier_class", self.__class__.__name__)

    def load_data(self, *, queries):
        """
        Load the specified queries from the training data lake, with caching, into a combined DataFrame in the class instance.
        """

        from plexus.DataCache import DataCache
        data_cache = DataCache(os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME'],
                                os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME'],
                                os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME'])
        self.dataframe = data_cache.load_dataframe(queries=queries)

        console.print(Text("Loaded dataframe from training data lake:", style="royal_blue1"))
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

        console.print(Text("Filtered dataframe:", style="royal_blue1"))

        self.analyze_dataset()

        if 'processors' in self.configuration.get('data', {}):
            console.print(Text("Running configured processors...", style="royal_blue1"))
            for processor in self.configuration['data']['processors']:
                processor_class = processor['class']
                processor_parameters = processor.get('parameters', {})
                from plexus.processors import ProcessorFactory
                processor_instance = ProcessorFactory.create_processor(processor_class, **processor_parameters)
            
            first_transcript_before = None
            first_transcript_after = None
            
            for index, row in self.dataframe.iterrows():
                if first_transcript_before is None:
                    first_transcript_before = row["Transcription"]
                
                processed_transcript = processor_instance.process(transcript=row["Transcription"])
                self.dataframe.at[index, "Transcription"] = processed_transcript
                
                if first_transcript_after is None:
                    first_transcript_after = processed_transcript
            
            if first_transcript_before and first_transcript_after:
                first_transcript_before_truncated = first_transcript_before[:1000] + '...'
                first_transcript_after_truncated = first_transcript_after[:1000] + '...'
                
                transcript_comparison_table = Table(
                    title=f"[royal_blue1][b]{processor_class}[/b][/royal_blue1]",
                    header_style="sky_blue1",
                    border_style="sky_blue1"
                )
                transcript_comparison_table.add_column("Before", style="magenta1", justify="left")
                transcript_comparison_table.add_column("After", style="magenta1", justify="left")
                transcript_comparison_table.add_row(first_transcript_before_truncated, first_transcript_after_truncated)
                
                console.print(Panel(transcript_comparison_table, border_style="royal_blue1"))

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
    def save_model(self):
        """
        Save the model to the model registry.
        """
        pass

    def load_context(self, context):
        """
        Load the trained model and any necessary artifacts based on the MLflow context.
        """
        self.model = mlflow.keras.load_model(context.artifacts["model"])
        # Load any other necessary artifacts

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

    #############
    # Private stuff for visualizations.

    # Colors for visualizations.    
    _sky_blue = (0.012, 0.635, 0.996)
    _fuchsia = (0.815, 0.2, 0.51)
    _red = '#DD3333'
    _green = '#339933'

    @Classifier.ensure_report_directory_exists
    def _generate_model_diagram(self):
        directory_path = f"reports/{self.scorecard_name}/{self.score_name}/"
        file_name = os.path.join(directory_path, "model_diagram.png")
        plot_model(self.model, to_file=file_name, show_shapes=True, show_layer_names=True, rankdir='TB')
        mlflow.log_artifact(file_name)

    @Classifier.ensure_report_directory_exists
    def _generate_confusion_matrix(self):
        directory_path = f"reports/{self.scorecard_name}/{self.score_name}/"
        file_name = os.path.join(directory_path, "confusion_matrix.png")

        # Ensure that both val_labels and val_predictions are in integer format
        if self.is_multi_class:
            val_labels_int = np.argmax(self.val_labels, axis=1)
            val_predictions_int = np.argmax(self.val_predictions, axis=1)
        else:
            val_labels_int = self.val_labels_int
            val_predictions_int = [1 if pred > 0.5 else 0 for pred in self.val_predictions]

        cm = confusion_matrix(val_labels_int, val_predictions_int)
        custom_colormap = sns.light_palette(self._fuchsia, as_cmap=True)
        sns.heatmap(cm, annot=True, fmt='d', cmap=custom_colormap, xticklabels=self.label_map.keys(), yticklabels=self.label_map.keys())
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.title('Confusion Matrix')

        plt.savefig(file_name)
        plt.show()

        mlflow.log_artifact(file_name)

    @Classifier.ensure_report_directory_exists
    def _plot_roc_curve(self):
        directory_path = f"reports/{self.scorecard_name}/{self.score_name}/"
        file_name = os.path.join(directory_path, "ROC_curve.png")

        plt.figure()

        if self.is_multi_class:
            # Compute ROC curve and ROC area for each class
            val_labels_int = np.argmax(self.val_labels, axis=1)
            n_classes = len(np.unique(val_labels_int))
            fpr = dict()
            tpr = dict()
            roc_auc = dict()
            for i in range(n_classes):
                fpr[i], tpr[i], _ = roc_curve(self.val_labels[:, i], self.val_predictions[:, i])
                roc_auc[i] = auc(fpr[i], tpr[i])
                plt.plot(fpr[i], tpr[i], lw=2, label=f'Class {i} (area = {roc_auc[i]:0.2f})')
        else:
            fpr, tpr, _ = roc_curve(self.val_labels_int, self.val_predictions)
            roc_auc = auc(fpr, tpr)
            plt.plot(fpr, tpr, color=self._sky_blue, lw=2, label='ROC curve (area = %0.2f)' % roc_auc)

        plt.plot([0, 1], [0, 1], color=self._fuchsia, lw=2, linestyle='--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic')
        plt.legend(loc="lower right")
        plt.savefig(file_name)
        plt.show()
        mlflow.log_artifact(file_name)

    @Classifier.ensure_report_directory_exists
    def _plot_precision_recall_curve(self):
        directory_path = f"reports/{self.scorecard_name}/{self.score_name}/"
        file_name = os.path.join(directory_path, "precision_and_recall_curve.png")

        plt.figure()

        if self.is_multi_class:
            # Compute precision-recall curve and PR area for each class
            n_classes = self.val_labels.shape[1]
            precision = dict()
            recall = dict()
            pr_auc = dict()
            for i in range(n_classes):
                precision[i], recall[i], _ = precision_recall_curve(self.val_labels[:, i], self.val_predictions[:, i])
                pr_auc[i] = auc(recall[i], precision[i])
                plt.plot(recall[i], precision[i], lw=2, label=f'Class {i} (area = {pr_auc[i]:0.2f})')
        else:
            precision, recall, _ = precision_recall_curve(self.val_labels_int, self.val_predictions)
            pr_auc = auc(recall, precision)
            plt.plot(recall, precision, color=self._sky_blue, lw=2, label='PR curve (area = %0.2f)' % pr_auc)

        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall curve')
        plt.legend(loc="lower left")
        plt.savefig(file_name)
        plt.show()
        mlflow.log_artifact(file_name)

    @Classifier.ensure_report_directory_exists
    def _plot_training_history(self):
        directory_path = f"reports/{self.scorecard_name}/{self.score_name}/"
        file_name = os.path.join(directory_path, "training_history.png")

        plt.figure(figsize=(12, 9))  # Adjusted for a 4x3 aspect ratio with three subplots

        plt.suptitle(f"Training History\n{self.score_name}", fontsize=16, verticalalignment='top')

        # Learning Rate plot
        plt.subplot(1, 3, 1)  # First subplot for learning rate
        plt.plot(self.history.history['lr'], label='Learning Rate', color=self._fuchsia, lw=4)
        plt.title('Learning Rate')
        plt.ylabel('Learning Rate')
        plt.xlabel('Epoch')
        plt.legend(loc='upper right')
        plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        plt.gca().set_xticklabels(range(1, len(self.history.history['lr']) + 1))

        # Loss plot
        plt.subplot(1, 3, 2)  # Second subplot for loss
        plt.plot(self.history.history['loss'], label='Train Loss', color=self._sky_blue, lw=4)
        plt.plot(self.history.history['val_loss'], label='Validation Loss', color=self._fuchsia, lw=4)
        plt.title('Model Loss')
        plt.ylabel('Loss')
        plt.xlabel('Epoch')
        plt.yscale('log')  # Logarithmic scale for loss
        plt.legend(loc='upper right')
        plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        plt.gca().set_xticklabels(range(1, len(self.history.history['loss']) + 1))

        # Set the loss y-axis to have a fixed locator so it only shows specific ticks, and format them properly.
        plt.gca().yaxis.set_major_locator(ticker.FixedLocator(np.logspace(np.log10(plt.ylim()[0]), np.log10(plt.ylim()[1]), num=5)))
        plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: '{:.2g}'.format(y)))

        # Accuracy plot
        plt.subplot(1, 3, 3)  # Third subplot for accuracy
        plt.plot(self.history.history['accuracy'], label='Train Accuracy', color=self._sky_blue, lw=4)
        plt.plot(self.history.history['val_accuracy'], label='Validation Accuracy', color=self._fuchsia, lw=4)
        plt.title('Model Accuracy')
        plt.ylabel('Accuracy (%)')
        plt.xlabel('Epoch')
        plt.legend(loc='lower right')
        plt.ylim(0.45, 1.0)  # Adjust based on your model's accuracy range
        # Adjust y-axis to show percentages, and format them properly.
        plt.gca().yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0, decimals=0))
        plt.gca().set_xticklabels(range(1, len(self.history.history['accuracy']) + 1))

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(file_name)
        plt.show()
        mlflow.log_artifact(file_name)

    @Classifier.ensure_report_directory_exists
    def _record_metrics(self, metrics):
        """
        Record the provided metrics dictionary as a JSON file in the appropriate report folder for this model.

        :param metrics: Dictionary containing the metrics to be recorded.
        :type metrics: dict
        """
        directory_path = f"reports/{self.scorecard_name}/{self.score_name}/"
        file_name = os.path.join(directory_path, "metrics.json")

        with open(file_name, 'w') as json_file:
            json.dump(metrics, json_file, indent=4)

    @property
    def is_multi_class(self):
        if self._is_multi_class is None:
            unique_labels = np.unique(self.train_labels_int)
            self._is_multi_class = len(unique_labels) > 2
        return self._is_multi_class