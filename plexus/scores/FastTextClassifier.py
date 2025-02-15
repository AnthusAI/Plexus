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

from plexus.scores.Score import Score

fasttext.FastText.eprint = lambda x: None

class FastTextClassifier(Score):

    class Parameters(Score.Parameters):
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
            self.__class__.__name__ + '_' + sanitized_scorecard_name + '_' + sanitized_score_name + '_' +
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
            conversation = row['text'].replace('\n', '__NEWLINE__')
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
        
        # Log a few lines from the training file
        with open(train_filename, 'r', encoding='utf-8') as f:
            sample_lines = f.readlines()[:5]
        logging.info(f"Sample lines from training file:\n{''.join(sample_lines)}")

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

        # Log the labels the model was trained on
        logging.info(f"Model labels: {self.model.labels}")

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
        test_filename = self._get_test_filename()

        with open(test_filename, 'r', encoding='utf-8') as file:
            test_data = file.readlines()

        actual_labels = [line.split(' ', 1)[0].replace('__label__', '') for line in test_data]

        # Create label_map first
        unique_labels = sorted(set(actual_labels) | set(label.replace('__label__', '') for label in self.model.labels))
        self.setup_label_map(unique_labels)

        predicted_labels = []
        confidence_scores = []

        for i, line in enumerate(test_data):
            text = line.split(' ', 1)[1].replace('\n', ' ')
            prediction = self.model.predict(text, k=len(self.model.labels))
            labels, confs = prediction

            # Store only the confidence score for the top prediction
            predicted_label = labels[0].replace('__label__', '')
            predicted_labels.append(predicted_label)
            confidence_scores.append(confs[0])

            if i < 5:  # Log details for the first 5 predictions
                logging.info(f"Sample {i+1}:")
                logging.info(f"  Text: {text[:100]}...")  # Log first 100 characters
                logging.info(f"  Actual label: {actual_labels[i]}")
                logging.info(f"  Predicted: {predicted_label}")
                logging.info(f"  Confidence score: {confs[0]}")

        # Keep labels as strings
        self.val_labels = np.array(actual_labels)
        self.val_predictions = np.array(predicted_labels)
        self.val_confidence_scores = np.array(confidence_scores)

        logging.info(f"Unique actual labels: {set(actual_labels)}")
        logging.info(f"Unique predicted labels: {set(predicted_labels)}")
        logging.info(f"label_map: {self.label_map}")

        self._is_multi_class = len(self.label_map) > 2

        # Log additional information
        logging.info(f"Shape of val_confidence_scores: {self.val_confidence_scores.shape}")
        logging.info(f"Shape of val_predictions: {self.val_predictions.shape}")
        logging.info(f"Shape of val_labels: {self.val_labels.shape}")
        logging.info(f"Number of unique labels in label_map: {len(self.label_map)}")
        logging.info(f"Number of unique predicted labels: {len(set(predicted_labels))}")
        logging.info(f"Sample of val_confidence_scores: {self.val_confidence_scores[:5]}")

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
        # Use the existing implementation from Score
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

    def predict(self, context: mlflow.pyfunc.PythonModelContext, model_input: list[Score.Input]) -> list[Score.Result]:
        """
        Make predictions on a batch of input data.

        Parameters
        ----------
        context : mlflow.pyfunc.PythonModelContext
            The MLflow context containing model artifacts and configuration
        model_input : list[Score.Input]
            A list of input instances to make predictions on

        Returns
        -------
        list[Score.Result]
            A list of prediction results
        """
        predictions = []
        confidence_scores = []

        for input_instance in model_input:
            text = input_instance.text
            prediction = self.model.predict(text, k=len(self.model.labels))
            labels, confs = prediction

            if self._is_multi_class:
                conf_scores = np.zeros(len(self.label_map))
                for label, conf in zip(labels, confs):
                    label_index = self.label_map[label.replace('__label__', '')]
                    conf_scores[label_index] = conf
                confidence = np.max(conf_scores)
                predicted_label = self.label_map[labels[0].replace('__label__', '')]
            else:
                confidence = confs[0]  # Only keep the positive class confidence
                predicted_label = labels[0].replace('__label__', '')

            predictions.append(
                Score.Result(
                    parameters=self.parameters,
                    value=predicted_label,
                    metadata={'confidence': float(confidence)}
                )
            )

        return predictions