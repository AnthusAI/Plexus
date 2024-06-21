import os
import json
import mlflow
import inspect
import pandas as pd
import numpy as np
from pydantic import BaseModel, validator, ValidationError
import matplotlib.pyplot as plt
import seaborn as sns
from tensorflow.keras.utils import plot_model
from sklearn.metrics import confusion_matrix
from abc import abstractmethod
from sklearn.metrics import roc_curve, auc, precision_recall_curve
from sklearn.metrics import confusion_matrix
from sklearn.metrics import accuracy_score, f1_score, recall_score, precision_score
import matplotlib.ticker as ticker
import matplotlib.pyplot as plt
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import print as rich_print
from rich.text import Text
from plexus.cli.console import console
from plexus.CustomLogging import logging
from plexus.classifiers.Score import Score
from sklearn.preprocessing import LabelBinarizer

class MLClassifier(Score):
    """
    Abstract class for a machine-learning classifier, with functions for the various states of ML model development.
    """

    class Parameters(Score.Parameters):
        ...
        data: dict

        @validator('data')
        def convert_data_percentage(cls, value):
            if 'percentage' in value:
                value['percentage'] = float(str(value['percentage']).strip().replace('%', ''))
            else:
                value['percentage'] = 100.0
            return value

    def __init__(self, **parameters):
        super().__init__(**parameters)
        logging.info("Initializing [magenta1][b]MLClassifier[/b][/magenta1]")
        self._is_multi_class = None
        self.start_mlflow_experiment_run()

    def log_stored_parameters(self):
        if hasattr(self, '_stored_parameters'):
            for name, value in self.parameters.items():
                mlflow.log_param(name, value)

    def name(self):
        # Get the name of the enclosing folder of the subclass
        subclass_file = inspect.getfile(self.__class__)
        folder_name = os.path.basename(os.path.dirname(subclass_file))
        # Concatenate the folder name and the class name to create the data_filename
        computed_name = folder_name + "_" + self.__class__.__name__
        logging.info(f"Classifier name: {computed_name}")
        return computed_name

    def start_mlflow_experiment_run(self):
        experiment_name = f"{self.parameters.scorecard_name} - {self.parameters.score_name}"
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
            logging.error(f"Error: {e}")
            logging.info("Attempting to end the previous run and start a new one.")
            mlflow.end_run()
            mlflow.start_run()

        mlflow.log_param("classifier_class", self.__class__.__name__)

        # Log common parameters
        mlflow.log_param("scorecard_name", self.parameters.scorecard_name)
        mlflow.log_param("score_name", self.parameters.score_name)

        self.log_stored_parameters()

    def log_evaluation_metrics(self, metrics):
        mlflow.log_metric("accuracy", metrics["accuracy"])
        mlflow.log_metric("precision", metrics["precision"])
        mlflow.log_metric("recall", metrics["recall"])
        mlflow.log_metric("f1_score", metrics["f1_score"])

    def load_data(self, *, queries=None, merge=None):
        """
        Load the specified queries from the training data lake, with caching, into a combined DataFrame in the class instance.
        """

        from plexus.DataCache import DataCache
        data_cache = DataCache(os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME'],
            os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME'],
            os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME'])
        if queries:
            self.dataframe = data_cache.load_dataframe_from_queries(queries=queries)
        else:
            self.dataframe = data_cache.load_dataframe_from_file(merge=merge)

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

        try:
            answer_counts = self.dataframe[self.parameters.score_name].value_counts()
            total_responses = answer_counts.sum()
            for answer_value, count in answer_counts.items():
                percentage_of_total = (count / total_responses) * 100
                formatted_percentage = f"{percentage_of_total:.1f}%"
                answer_breakdown_table.add_row(str(answer_value), str(count), formatted_percentage)
        except KeyError:
            pass

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

        if 'answer_counts' in locals():
            smallest_answer_count = answer_counts.min()
            total_kinds_of_non_null_answers = self.dataframe[self.parameters.score_name].nunique()
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
        header_text = f"[bold royal_blue1]{self.parameters.score_name}[/bold royal_blue1]"

        # Display the combined panels
        rich_print(Panel(columns, title=header_text, border_style="magenta1"))

    def process_data(self):
        """
        Handle any pre-processing of the training data, including the training/validation splits.
        """

        if 'processors' in self.parameters.data:
            console.print(Text("Running configured processors...", style="royal_blue1"))

            # Instantiate all processors once
            processors = []
            for processor in self.parameters.data['processors']:
                processor_class = processor['class']
                processor_parameters = processor.get('parameters', {})
                from plexus.processors import ProcessorFactory
                processor_instance = ProcessorFactory.create_processor(processor_class, **processor_parameters)
                processors.append(processor_instance)

            # Process the entire dataframe
            first_transcript_before = self.dataframe["Transcription"].iloc[0]

            for processor in processors:
                self.dataframe = processor.process(self.dataframe)

            first_transcript_after = self.dataframe["Transcription"].iloc[0]

            if first_transcript_before and first_transcript_after:
                first_transcript_before_truncated = first_transcript_before[:1000] + '...'
                first_transcript_after_truncated = first_transcript_after[:1000] + '...'

                transcript_comparison_table = Table(
                    title=f"[royal_blue1][b]Processors[/b][/royal_blue1]",
                    header_style="sky_blue1",
                    border_style="sky_blue1"
                )
                transcript_comparison_table.add_column("Before", style="magenta1", justify="left")
                transcript_comparison_table.add_column("After", style="magenta1", justify="left")
                transcript_comparison_table.add_row(first_transcript_before_truncated, first_transcript_after_truncated)

                console.print(Panel(transcript_comparison_table, border_style="royal_blue1"))

        console.print(Text("Processed dataframe:", style="royal_blue1"))
        self.analyze_dataset()

        #############
        # Subsample the data

        before_subsample_count = len(self.dataframe)
        self.dataframe = self.dataframe.sample(frac=self.parameters.data['percentage'] / 100, random_state=42)
        after_subsample_count = len(self.dataframe)

        subsample_comparison_table = Table(
            title=f"[royal_blue1][b]Subsampling {self.parameters.data['percentage']}% of the data[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        subsample_comparison_table.add_column("Before", style="magenta1", justify="left")
        subsample_comparison_table.add_column("After", style="magenta1", justify="left")
        subsample_comparison_table.add_row(str(before_subsample_count), str(after_subsample_count))

        console.print(Panel(subsample_comparison_table, border_style="royal_blue1"))

        #############
        # Balance data

        if 'balance' in self.parameters.data and not self.parameters.data['balance']:
            logging.info("data->balance: [red][b]false.[/b][/red]  Skipping data balancing.")
            return

        # Check the distribution of labels
        print("\nDistribution of labels in the dataframe:")
        print(self.dataframe[self.parameters.score_name].value_counts(dropna=False))

        # Get the unique labels
        unique_labels = self.dataframe[self.parameters.score_name].unique()

        # Create a dictionary to store the dataframes for each label
        label_dataframes = {label: self.dataframe[self.dataframe[self.parameters.score_name] == label] for label in unique_labels}

        # Determine the smallest class size
        smallest_class_size = min(len(df) for df in label_dataframes.values())

        # Sample from each class to match the number of instances in the smallest class
        balanced_dataframes = []
        for label, dataframe in label_dataframes.items():
            print(f"Sampling {smallest_class_size} instances from the '{label}' class...")
            balanced_dataframes.append(dataframe.sample(n=smallest_class_size, random_state=42))

        # Concatenate the balanced dataframes
        balanced_dataframe = pd.concat(balanced_dataframes)

        # Shuffle the data
        balanced_dataframe = balanced_dataframe.sample(frac=1, random_state=42)

        # Check the distribution of labels
        print("\nDistribution of labels in the balanced dataframe:")
        print(balanced_dataframe[self.parameters.score_name].value_counts())

        self.dataframe = balanced_dataframe

        console.print(Text("Final, balanced dataframe:", style="royal_blue1"))
        self.analyze_dataset()

    @abstractmethod
    def train_model(self):
        """
        Train the model on the training data.

        :return: The trained model.
        """
        pass

    @abstractmethod
    def predict_validation(self):
        """
        Abstract method for subclasses to implement the prediction logic on the validation set.
        """
        pass

    def evaluate_model(self):
        """
        Evaluate the model on the validation data.

        :return: The evaluation results.
        """
        print("Generating evaluation metrics...")

        # Call the subclass's prediction method
        self.predict_validation()

        logging.info(f"val_labels type: {type(self.val_labels)}, shape: {self.val_labels.shape}, sample: {self.val_labels[:5]}")
        logging.info(f"val_predictions type: {type(self.val_predictions)}, shape: {self.val_predictions.shape}, sample: {self.val_predictions[:5]}")
        
        if self.is_multi_class:
            if self.val_predictions.ndim > 1:
                self.val_predictions_labels = np.argmax(self.val_predictions, axis=1)
            else:
                self.val_predictions_labels = self.val_predictions  # Use predictions directly if they are already 1D
            
            if self.val_labels.ndim > 1 and self.val_labels.shape[1] > 1:
                self.val_labels = np.argmax(self.val_labels, axis=1)  # Convert one-hot encoded labels to integer labels
        else:
            self.val_predictions_labels = [1 if pred > 0.5 else 0 for pred in self.val_predictions]

        # Compute evaluation metrics
        accuracy = accuracy_score(self.val_labels, self.val_predictions_labels)
        f1 = f1_score(self.val_labels, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')
        recall = recall_score(self.val_labels, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')
        precision = precision_score(self.val_labels, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')

        # Log evaluation metrics to MLflow
        mlflow.log_metric("validation_f1_score", f1)
        mlflow.log_metric("validation_recall", recall)
        mlflow.log_metric("validation_precision", precision)

        print(f"Validation Accuracy: {accuracy:.4f}")
        print(f"Validation F1 Score: {f1:.4f}")
        print(f"Validation Recall: {recall:.4f}")
        print(f"Validation Precision: {precision:.4f}")

        print("Generating visualizations...")

        self._generate_confusion_matrix()

        self._plot_roc_curve()

        self._plot_precision_recall_curve()

        self._plot_training_history()

        metrics = {
            "validation_f1_score": f1,
            "validation_recall": recall,
            "validation_precision": precision
        }

        if hasattr(self, 'history') and hasattr(self.history, 'history'):
            metrics.update({
                "training_loss": self.history.history['loss'][-1],
                "training_accuracy": self.history.history['accuracy'][-1],
                "validation_loss": self.history.history['val_loss'][-1],
                "validation_accuracy": self.history.history['val_accuracy'][-1]
            })

        self._record_metrics(metrics)

        # End MLflow run
        mlflow.end_run()

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

    def _generate_model_diagram(self):
        file_name = self.report_file_name("model_diagram.png")
        plot_model(self.model, to_file=file_name, show_shapes=True, show_layer_names=True, rankdir='TB')
        mlflow.log_artifact(file_name)

    def _generate_confusion_matrix(self):
        file_name = self.report_file_name("confusion_matrix.png")

        # Ensure that both val_labels and val_predictions are in integer format
        if self.is_multi_class:
            if len(self.val_labels.shape) > 1 and self.val_labels.shape[1] > 1:
                val_labels_int = np.argmax(self.val_labels, axis=1)
            else:
                val_labels_int = self.val_labels

            if self.val_predictions.ndim > 1:
                val_predictions_int = np.argmax(self.val_predictions, axis=1)
            else:
                val_predictions_int = self.val_predictions  # Use predictions directly if they are already 1D

        else:
            val_labels_int = self.val_labels
            val_predictions_int = [1 if pred > 0.5 else 0 for pred in self.val_predictions]

        cm = confusion_matrix(val_labels_int, val_predictions_int)
        custom_colormap = sns.light_palette(self._fuchsia, as_cmap=True)
        sns.heatmap(cm, annot=True, fmt='d', cmap=custom_colormap, xticklabels=self.label_map.keys(), yticklabels=self.label_map.keys())
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.title('Confusion Matrix')

        plt.savefig(file_name)
        # plt.show()

        mlflow.log_artifact(file_name)
        
        # Log the confusion matrix as text
        cm_text = np.array2string(cm, separator=', ')
        logging.info(f"Confusion matrix: {cm_text}")

    def _plot_roc_curve(self):
        file_name = self.report_file_name("ROC_curve.png")

        plt.clf()
        plt.figure()

        if self.is_multi_class:
            lb = LabelBinarizer()
            val_labels_one_hot = lb.fit_transform(self.val_labels)
            val_predictions_one_hot = lb.transform(self.val_predictions)

            n_classes = val_labels_one_hot.shape[1]
            fpr = dict()
            tpr = dict()
            roc_auc = dict()
            for i in range(n_classes):
                fpr[i], tpr[i], _ = roc_curve(val_labels_one_hot[:, i], val_predictions_one_hot[:, i])
                roc_auc[i] = auc(fpr[i], tpr[i])
                plt.plot(fpr[i], tpr[i], lw=2, label=f'Class {i} (area = {roc_auc[i]:0.2f})')
        else:
            fpr, tpr, _ = roc_curve(self.val_labels, self.val_predictions)
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
        # plt.show()
        mlflow.log_artifact(file_name)

    def _plot_precision_recall_curve(self):
        file_name = self.report_file_name("precision_and_recall_curve.png")

        plt.figure()

        if self.is_multi_class:
            lb = LabelBinarizer()
            val_labels_one_hot = lb.fit_transform(self.val_labels)
            val_predictions_one_hot = lb.transform(self.val_predictions)

            n_classes = val_labels_one_hot.shape[1]
            precision = dict()
            recall = dict()
            pr_auc = dict()
            for i in range(n_classes):
                precision[i], recall[i], _ = precision_recall_curve(val_labels_one_hot[:, i], val_predictions_one_hot[:, i])
                pr_auc[i] = auc(recall[i], precision[i])
                plt.plot(recall[i], precision[i], lw=2, label=f'Class {i} (area = {pr_auc[i]:0.2f})')
        else:
            precision, recall, _ = precision_recall_curve(self.val_labels, self.val_predictions)
            pr_auc = auc(recall, precision)
            plt.plot(recall, precision, color=self._sky_blue, lw=2, label='PR curve (area = %0.2f)' % pr_auc)

        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall curve')
        plt.legend(loc="lower left")
        plt.savefig(file_name)
        # plt.show()
        mlflow.log_artifact(file_name)

    def _plot_training_history(self):
        file_name = self.report_file_name("training_history.png")

        plt.figure(figsize=(12, 9))  # Adjusted for a 4x3 aspect ratio with three subplots

        plt.suptitle(f"Training History\n{self.parameters.score_name}", fontsize=16, verticalalignment='top')

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

        # Add horizontal line and label for final validation accuracy
        final_val_accuracy = self.history.history['val_accuracy'][-1]
        plt.axhline(y=final_val_accuracy, color='gray', linestyle='--', lw=2)
        plt.text(len(self.history.history['val_accuracy']) - 1, final_val_accuracy, f'{final_val_accuracy:.3%}', 
                 color='black', ha='right', va='bottom')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(file_name)
        # plt.show()
        mlflow.log_artifact(file_name)

    def _record_metrics(self, metrics):
        """
        Record the provided metrics dictionary as a JSON file in the appropriate report folder for this model.

        :param metrics: Dictionary containing the metrics to be recorded.
        :type metrics: dict
        """
        file_name = self.report_file_name("metrics.json")

        with open(file_name, 'w') as json_file:
            json.dump(metrics, json_file, indent=4)

    @property
    def is_multi_class(self):
        if self._is_multi_class is None:
            unique_labels = self.dataframe[self.parameters.score_name].unique()
            self._is_multi_class = len(unique_labels) > 2
        return self._is_multi_class