from plexus.CustomLogging import logging
import fasttext
import pandas as pd
from sklearn.model_selection import train_test_split
import mlflow
import mlflow.pyfunc

from plexus.classifiers.Classifier import Classifier
from plexus.classifiers.LLMGenerator import LLMGenerator

fasttext.FastText.eprint = lambda x: None

class FastTextClassifier(Classifier):

    def __init__(self, **parameters):
        super().__init__(**parameters)
        logging.info("Initializing [magenta1][b]FastTextClassifier[/b][/magenta1]")
        for name, value in parameters.items():
            logging.info(f"Setting [royal_blue1]{name}[/royal_blue1] to [magenta]{value}[/magenta]")
            setattr(self, name, value)
        # self.set_up_mlflow()
        self._is_multi_class = None
        self.model = None

    def data_filename(self):
        return self.name() + "_data.txt"

    def generate_data(self, *, sample_count: int = 13000):

        logging.info(f"Generating {sample_count} samples of synthetic data for FastTextClassifier...")

        data_filename = self.data_filename()
        logging.info(f"Data file name: {data_filename}")

        # Instantiate the LLMGenerator
        generator = LLMGenerator()

        # Use the generator to create data
        generator.generate_data(
            context=self.context,
            relevant_examples=self.relevant_examples,
            irrelevant_examples=self.irrelevant_examples,
            filename=data_filename,
            sample_count=sample_count)

        logging.info("Data generated successfully!")

    def _get_train_filename(self):
        return self.data_filename().replace('.txt', '_train.txt')

    def _get_test_filename(self):
        return self.data_filename().replace('.txt', '_test.txt')
    
    def process_data(self):
        test_size = 0.2
        logging.info(f"Processing data for FastTextClassifier with a test size of {round(test_size * 100)}%...")

        # Load the data
        with open(self.data_filename(), 'r', encoding='utf-8') as file:
            lines = file.readlines()

        # Split the data into training and test sets (80% training, 20% test)
        train_data, test_data = train_test_split(lines, test_size=0.2, random_state=42)

        # Write the training and test data to separate files
        train_filename = self._get_train_filename()
        test_filename = self._get_test_filename()

        with open(train_filename, 'w', encoding='utf-8') as file:
            file.writelines(train_data)
        with open(test_filename, 'w', encoding='utf-8') as file:
            file.writelines(test_data)

        logging.info("Data processed successfully!")

    def train_model(self):
        logging.info("Training FastText model...")
        
        # Train the fastText model using the saved training data file
        train_filename = self._get_train_filename()
        self.model = fasttext.train_supervised(input=train_filename)

        logging.info("Model trained successfully!")
        self.report_model_details()

    def report_model_details(self):
        model_details = {}
        if self.model is None:
            logging.info("Model has not been trained yet.")
        else:
            # Report number of words and labels in the model
            logging.info(f"Model has {len(self.model.words)} words and {len(self.model.labels)} labels.")
            model_details['words'] = len(self.model.words)
            model_details['labels'] = len(self.model.labels)
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
            else:
                logging.info("Model hyperparameters are not accessible.")
        return model_details

    def evaluate_model(self):
        # Evaluate the model using the test data and log the results: accuracy, precision, recall, F1-score
        test_filename = self._get_test_filename()
        results = self.model.test(test_filename)
        accuracy = results[1]
        precision = results[1]
        recall = results[2]
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        evaluation_metrics = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score
        }
        logging.info(f"Model evaluation results - {evaluation_metrics}")
        return evaluation_metrics
    
    def run_experiment(self):
        # Set the experiment name
        mlflow.set_experiment(self.name())

        with mlflow.start_run() as run:
            # Run the entire model development process and log it in MLFlow
            self.train_model()
            model_details = self.report_model_details()
            model_evaluation_metrics = self.evaluate_model()

            # Log the model details and evaluation metrics in MLFlow
            self._log_parameters_recursively(model_details)
            mlflow.log_metrics(model_evaluation_metrics)

            # Save the fastText binary file for logging as an artifact
            fasttext_binary_path = self.save_model_binary()
            
            # Log the fastText binary file as an artifact
            mlflow.log_artifact(fasttext_binary_path, "model")

            # End the MLFlow run
            mlflow.end_run()

        # Return the run ID
        return run.info

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

    def save_model(self):
        """
        Save the model to the model registry.
        """
        pass

    def save_model_binary(self):
        if self.model is None:
            raise Exception("Model not trained yet!")
        model_binary_path = f"{self._model_name()}.bin"
        self.model.save_model(model_binary_path)
        logging.info(f"Model binary saved to {model_binary_path}")
        return model_binary_path

    def register_model(self, run_id, stage='Production'):
        # Register the model with MLflow
        model_name = self._model_name()
        model_binary_path = f"{self._model_name()}.bin"
        model_uri = f"runs:/{run_id}/{model_binary_path}"
        mlflow_model = mlflow.register_model(
            model_uri=model_uri,
            name=model_name
        )
        logging.info(f"Model registered successfully with name: {model_name}")

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
        # Attempt to load the model JIT if it hasn't been loaded yet
        if self.model is None:
            logging.info("Model not loaded. Attempting to load the model JIT.")
            # Construct the context with the necessary information to load the model
            # This should be the same structure as the context provided by MLflow when serving the model
            model_binary_path = f"{self._model_name()}.bin"
            context = {
                'artifacts': {
                    'model_path': model_binary_path
                }
            }
            # Call load_context with the constructed context
            self.load_context(context)

        # If the model is still None after attempting to load, report an error
        if self.model is None:
            logging.error("No model is registered for this classifier.")
            raise Exception("No model is registered for this classifier.")

        # Check if the input is a DataFrame with a single column
        if isinstance(model_input, pd.DataFrame) and model_input.shape[1] == 1:
            # Extract the text column (assuming it's the first column)
            texts = model_input.iloc[:, 0].tolist()
            logging.debug(f"Running inference on texts: {texts}")
        else:
            logging.error("Model input should be a DataFrame with a single text column.")
            raise ValueError("Model input should be a DataFrame with a single text column.")

        # Apply the FastText model's predict method to each text entry
        predictions = [self.model.predict(text)[0][0] for text in texts]
        logging.debug(f"Predictions: {predictions}")

        # Return the predictions as a DataFrame
        return pd.DataFrame(predictions, columns=['prediction'])