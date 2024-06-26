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
        test_filename = self._get_test_filename()

        with open(test_filename, 'r', encoding='utf-8') as file:
            test_data = file.readlines()

        actual_labels = [line.split(' ', 1)[0].replace('__label__', '') for line in test_data]

        predicted_labels_and_confidences = [
            self.model.predict(line.split(' ', 1)[1].replace('\n', ' '), k=1)
            for line in test_data
        ]
        predicted_labels = [
            pred[0][0].replace('__label__', '') for pred, _ in predicted_labels_and_confidences
        ]
        confidence_scores = [
            conf[0] for _, conf in predicted_labels_and_confidences
        ]

        # Convert string labels to numeric values
        unique_labels = sorted(set(actual_labels))
        self.label_map = {label: i for i, label in enumerate(unique_labels)}
        
        self.val_labels = np.array([self.label_map[label] for label in actual_labels])
        self.val_predictions = np.array(confidence_scores)  # Use confidence scores directly
        self.val_confidence_scores = np.array(confidence_scores)

        # Store the string predictions for later use if needed
        self.val_predictions_str = np.array(predicted_labels)

        # Log the types and shapes of the arrays
        logging.info(f"val_labels type: {type(self.val_labels)}, shape: {self.val_labels.shape}, sample: {self.val_labels[:5]}")
        logging.info(f"val_predictions type: {type(self.val_predictions)}, shape: {self.val_predictions.shape}, sample: {self.val_predictions[:5]}")
        logging.info(f"val_confidence_scores type: {type(self.val_confidence_scores)}, shape: {self.val_confidence_scores.shape}, sample: {self.val_confidence_scores[:5]}")
        logging.info(f"val_predictions_str type: {type(self.val_predictions_str)}, shape: {self.val_predictions_str.shape}, sample: {self.val_predictions_str[:5]}")

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
        if isinstance(model_input, pd.DataFrame) and 'Transcription' in model_input.columns:
            texts = model_input['Transcription'].tolist()
            logging.debug(f"Running inference on texts: {texts}")
        else:
            logging.error("Model input should be a DataFrame with a 'Transcription' column.")
            raise ValueError("Model input should be a DataFrame with a 'Transcription' column.")

        predictions = []
        confidence_scores = []

        for text in texts:
            prediction, confidence = self.model.predict(text)
            predictions.append(self.label_map[prediction[0].replace('__label__', '')])
            confidence_scores.append(confidence[0])

        logging.debug(f"Predictions: {predictions}")
        logging.debug(f"Confidence scores: {confidence_scores}")

        return np.array(predictions), np.array(confidence_scores)