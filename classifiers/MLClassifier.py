import os
import inspect
import pandas as pd
from abc import ABC, abstractmethod
import mlflow.pyfunc

from plexus.CustomLogging import logging
from plexus.classifiers.Classifier import Classifier

class MLClassifier(Classifier, mlflow.pyfunc.PythonModel):
    """
    Abstract class for a machine-learning classifier, with functions for the various states of ML model development.
    """

    def __init__(self):
        pass

    def name(self):
        # Get the name of the enclosing folder of the subclass
        subclass_file = inspect.getfile(self.__class__)
        folder_name = os.path.basename(os.path.dirname(subclass_file))
        # Concatenate the folder name and the class name to create the data_filename
        computed_name = folder_name + "_" + self.__class__.__name__
        logging.info(f"Classifier name: {computed_name}")
        return computed_name

    @abstractmethod
    def process_data(self):
        """
        Handle any pre-processing of the training data, including the training/validation splits.
        """
        pass

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

