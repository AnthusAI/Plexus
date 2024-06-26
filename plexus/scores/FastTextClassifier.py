import os
import numpy as np
import re
from pydantic import Field
from plexus.CustomLogging import logging
import fasttext
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
import mlflow
import mlflow.pyfunc

from plexus.scores.MLClassifier import MLClassifier

fasttext.FastText.eprint = lambda x: None

class FastTextClassifier(MLClassifier):

    class Parameters(MLClassifier.Parameters):
        ...
        learning_rate: float = 0.1
        dimension: int = 100
        window_size: int = 5
        number_of_epochs: int = 5
        minimum_word_count: int = 1
        minimum_label_count: int = 1
        minimum_character_ngram_length: int = 0
        maximum_character_ngram_length: int = 0
        number_of_negative_samples: int = 5
        word_ngram_count: int = 1
        loss_function: str = 'softmax'
        bucket_size: int = 2000000
        number_of_threads: int = 4
        learning_rate_update_rate: int = 100
        sampling_threshold: float = 0.0001

    def __init__(self, **parameters):
        super().__init__(**parameters)
        logging.info("Initializing [magenta1][b]FastTextClassifier[/b][/magenta1]")
        for name, value in parameters.items():
            logging.info(f"Setting [royal_blue1]{name}[/royal_blue1] to [magenta]{value}[/magenta]")
            setattr(self, name, value)
        # self.start_mlflow_experiment_run()
        self._is_multi_class = None
        self.model = None
        self.label_map = None

    def data_filename(self):
        def sanitize_string(input_string):
            sanitized_string = re.sub(r'\W+', '', input_string)
            sanitized_string = re.sub(r'\s+', '_', sanitized_string)
            return sanitized_string

        sanitized_scorecard_name = sanitize_string(self.scorecard_name)
        sanitized_score_name = sanitize_string(self.score_name)
        return os.path.join(
            "./tmp",
            self.name() + '_' + sanitized_scorecard_name + '_' + sanitized_score_name + '_' +
            "data.txt"
        )

    def _get_train_filename(self):
        return self.data_filename().replace('.txt', '_train.txt')

    def _get_test_filename(self):
        return self.data_filename().replace('.txt', '_test.txt')
    
    def process_data(self):
        super().process_data()

        test_size = 0.2
        logging.info(f"Processing data for FastTextClassifier with a test size of {round(test_size * 100)}%...")

        # Split the conversations into individual utterances and label each utterance
        fasttext_data = []
        for _, row in self.dataframe.iterrows():
            conversation = row['Transcription'].replace('\n', '__NEWLINE__')
            label = re.sub(r'\W+', '_', row[self.score_name])
            fasttext_data.append(f"__label__{label} {conversation}")

        # Split the data into training and test sets (80% training, 20% test)
        train_data, test_data = train_test_split(fasttext_data, test_size=0.2, random_state=42)

        # Log the sizes of the training and test sets
        logging.info(f"Number of training samples: {len(train_data)}")
        logging.info(f"Number of test samples: {len(test_data)}")

        # Write the training and test data to separate files
        train_filename = self._get_train_filename()
        test_filename = self._get_test_filename()

        with open(train_filename, 'w', encoding='utf-8') as file:
            file.write('\n'.join(train_data))
        with open(test_filename, 'w', encoding='utf-8') as file:
            file.write('\n'.join(test_data))

        logging.info("Data processed successfully!")

    def train_model(self):
        logging.info("Training FastText model...")

        # Train the fastText model using the saved training data file
        train_filename = self._get_train_filename()
        
        self.model = fasttext.train_supervised(
            input=train_filename,
            lr=self.parameters.learning_rate,
            dim=self.parameters.dimension,
            ws=self.parameters.window_size,
            epoch=self.parameters.number_of_epochs,
            minCount=self.parameters.minimum_word_count,
            minCountLabel=self.parameters.minimum_label_count,
            minn=self.parameters.minimum_character_ngram_length,
            maxn=self.parameters.maximum_character_ngram_length,
            neg=self.parameters.number_of_negative_samples,
            wordNgrams=self.parameters.word_ngram_count,
            loss=self.parameters.loss_function,
            bucket=self.parameters.bucket_size,
            thread=self.parameters.number_of_threads,
            lrUpdateRate=self.parameters.learning_rate_update_rate,
            t=self.parameters.sampling_threshold
        )

        logging.info("Model trained successfully!")

        # Report number of words and labels in the model
        logging.info(f"Model has {len(self.model.words)} words and {len(self.model.labels)} labels.")
        model_details = {
            'vocabulary_size_in_word_count': len(self.model.words),
            'number_of_labels': len(self.model.labels)
        }
        mlflow.log_metrics(model_details)
        # Report model's hyperparameters, if accessible
        if hasattr(self.model, 'f'):  # Check if the 'f' function (which gives access to model parameters) exists
            params = self.model.f.getArgs()
            hyperparameters = {
                'lr': params.lr,
                'dim': params.dim,
                'ws': params.ws,
                'epoch': params.epoch,
                'minCount': params.minCount,
                'minCountLabel': params.minCountLabel,
                'minn': params.minn,
                'maxn': params.maxn,
                'neg': params.neg,
                'wordNgrams': params.wordNgrams,
                'loss': params.loss,
                'bucket': params.bucket,
                'thread': params.thread,
                'lrUpdateRate': params.lrUpdateRate,
                't': params.t
            }
            model_details['hyperparameters'] = hyperparameters
            logging.info(f"Model hyperparameters: {hyperparameters}")
            mlflow.log_params(hyperparameters)
            mlflow.log_metrics(hyperparameters)
        else:
            logging.info("Model hyperparameters are not accessible.")

    def predict_validation(self):
        """
        Implement the prediction logic for the validation set.
        """
        self.val_predictions = self.model.predict(self.val_input_ids)

    def evaluate_model(self):
        test_filename = self._get_test_filename()
        results = self.model.test(test_filename)
        num_test_examples = results[0]
        precision_at_one = results[1]
        recall_at_one = results[2]

        test_data = []
        with open(test_filename, 'r', encoding='utf-8') as file:
            test_data = file.readlines()

        actual_labels = [line.split(' ', 1)[0].replace('__label__', '') for line in test_data]
        predicted_labels = [
            self.model.predict(line.split(' ', 1)[1].replace('\n', ' '))[0][0].replace('__label__', '')
            for line in test_data
        ]

        logging.info(f"Number of actual labels: {len(actual_labels)}")
        logging.info(f"Number of predicted labels: {len(predicted_labels)}")

        accuracy = sum(1 for a, p in zip(actual_labels, predicted_labels) if a == p) / len(actual_labels)

        f1_score = 0.0
        if precision_at_one + recall_at_one != 0:
            f1_score = 2 * (precision_at_one * recall_at_one) / (precision_at_one + recall_at_one)

        metrics = {
            "accuracy": accuracy,
            "precision": precision_at_one,
            "recall": recall_at_one,
            "f1_score": f1_score,
            "number_of_test_examples": num_test_examples
        }
        logging.info(f"Model evaluation results - {metrics}")
        self._record_metrics(metrics)
        self.log_evaluation_metrics(metrics)

        unique_labels = list(set(actual_labels + predicted_labels))
        self.label_map = {label: idx for idx, label in enumerate(unique_labels)}

        logging.debug(f"Label map: {self.label_map}")

        self.val_labels_int = np.array([self.label_map[label] for label in actual_labels])
        self.val_predictions_int = np.array([self.label_map[label] for label in predicted_labels])

        logging.info(f"Integer actual labels: {self.val_labels_int}")
        logging.info(f"Integer predicted labels: {self.val_predictions_int}")

        logging.info(f"Number of integer actual labels: {len(self.val_labels_int)}")
        logging.info(f"Number of integer predicted labels: {len(self.val_predictions_int)}")

        if self.is_multi_class:
            num_classes = len(unique_labels)
            self.val_labels = np.eye(num_classes)[self.val_labels_int]
            self.val_predictions = np.eye(num_classes)[self.val_predictions_int]
        else:
            self.val_labels = self.val_labels_int
            self.val_predictions = self.val_predictions_int

        cm = confusion_matrix(self.val_labels_int, self.val_predictions_int)
        logging.info(f"Confusion matrix: \n{cm}")

        self._generate_confusion_matrix()
        self._plot_roc_curve()
        self._plot_precision_recall_curve()

        return metrics

    def _log_parameters_recursively(self, params, parent_key=''):
        for key, value in params.items():
            if isinstance(value, dict):
                self._log_parameters_recursively(value, parent_key=f'{parent_key}{key}.')
            else:
                mlflow.log_param(f'{parent_key}{key}', value)

    def _model_name(self):
        """
        Constructs the model name based on the classifier's name.
        """
        return f"fasttext_model_{self.name()}"

    def _record_metrics(self, metrics):
        # Use the existing implementation from MLClassifier
        super()._record_metrics(metrics)

    # This visualization doesn't work for fastText, so leave it out.
    def _plot_training_history(self):
        pass

    def save_model_binary(self):
        if self.model is None:
            raise Exception("Model not trained yet!")
        model_binary_path = f"{self._model_name()}.bin"
        self.model.save_model(model_binary_path)
        logging.info(f"Model binary saved to {model_binary_path}")
        return model_binary_path

    def register_model(self):
        # Register the model with MLflow
        model_name = self._model_name()
        model_binary_path = f"{self._model_name()}.bin"
        mlflow.fasttext.log_model(self.model, model_name)
        logging.info(f"Model registered successfully with name: {model_name}")

    def save_model(self):
        model_binary_path = f"{self._model_name()}.bin"
        self.model.save_model(model_binary_path)
        logging.info(f"Model binary saved to {model_binary_path}")

    def load_model(self, model_path):
        self.model = fasttext.load_model(model_path)

    def load_context(self, context):
        # The context object will contain the path to the model binary
        # Ensure that the path is to a file, not a directory
        model_path = context["artifacts"]["model_path"]
        if model_path.endswith("/."):
            model_path = model_path[:-2]  # Remove the erroneous characters
        elif model_path.endswith("."):
            model_path = model_path[:-1]  # Remove the erroneous character

        self.model = fasttext.load_model(model_path)

    def get_model_artifact_path(self):
        # Retrieve the model path from MLflow
        # This is just a placeholder, you'll need to implement the logic to retrieve the actual path
        model_uri = f"models:/{self._model_name()}/Production"
        local_model_path = mlflow.pyfunc.get_model_uri(model_uri)
        return local_model_path

    def predict(self, model_input):
        # Check if the input is a DataFrame with a 'Transcription' column
        if isinstance(model_input, pd.DataFrame) and 'Transcription' in model_input.columns:
            # Extract the text column
            texts = model_input['Transcription'].tolist()
            logging.debug(f"Running inference on texts: {texts}")
        else:
            logging.error("Model input should be a DataFrame with a 'Transcription' column.")
            raise ValueError("Model input should be a DataFrame with a 'Transcription' column.")

        # Apply the FastText model's predict method to each text entry
        predictions = [self.model.predict(text)[0][0].replace('__label__', '') for text in texts]
        logging.debug(f"Predictions: {predictions}")

        # Return the predictions as a DataFrame
        return pd.DataFrame(predictions, columns=['prediction'])