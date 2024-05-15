import os
import pandas as pd
import numpy as np
import logging
import datetime
from dotenv import load_dotenv
load_dotenv()
import mlflow
import mlflow.keras
from tqdm import tqdm
from transformers import BertTokenizer, TFBertModel
from transformers import MobileBertTokenizer, TFMobileBertModel
import tensorflow as tf
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import regularizers
from tensorflow.keras.layers import Dropout
from tensorflow.keras.callbacks import ReduceLROnPlateau
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
from imblearn.over_sampling import SMOTE
import nltk
nltk.download('punkt')

from plexus.CustomLogging import logging
from plexus.classifiers.Classifier import Classifier
from plexus.classifiers.MLClassifier import MLClassifier

class BERTForSequenceClassificationForControlFreaks(MLClassifier):

    def __init__(self, **parameters):
        logging.info("Initializing [magenta1][b]BERTForSequenceClassificationForControlFreaks[/b][/magenta1]")
        for name, value in parameters.items():
            logging.info(f"Setting [royal_blue1]{name}[/royal_blue1] to [magenta]{value}[/magenta]")
            setattr(self, name, value)
        self.set_up_mlflow()

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
        
        # Log parameters
        mlflow.log_param("max_len", self.max_len)
        mlflow.log_param("epochs", self.epochs)
        mlflow.log_param("batch_size", self.batch_size)
        mlflow.log_param("learning_rate", self.learning_rate)
        mlflow.log_param("learning_rate_scheduler_initial_wait_epochs", self.learning_rate_scheduler_initial_wait_epochs)
        mlflow.log_param("learning_rate_scheduler_decay_rate", self.learning_rate_scheduler_decay_rate)
        mlflow.log_param("learning_rate_scheduler_decay_step", self.learning_rate_scheduler_decay_step)
        mlflow.log_param("l2_regularization_strength", self.l2_regularization_strength)
        mlflow.log_param("dropout_rate", self.dropout_rate)
        mlflow.log_param("bert_model", self.bert_model_name)
        mlflow.log_param("data_percentage", self.data_percentage)
        mlflow.log_param("number_of_sentences", self.number_of_sentences)

    def process_data(self, *, queries):
        """
        Handle any pre-processing of the training data, including the training/validation splits.
        """

        # Load the dataframe using Plexus, from the data lake, with caching.
        from plexus.DataCache import DataCache
        data_cache = DataCache(os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME'],
                                os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME'],
                                os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME'])
        df = data_cache.load_dataframe(queries=queries)

        number_of_rows_in_data = len(df)
        print("Number of rows in the dataset:", number_of_rows_in_data)

        # Check for missing or unexpected values
        print(f"Unique values in '{self.score_name}':", df[self.score_name].unique())

        # Step 2: Balance data

        # Check the distribution of labels
        print("\nDistribution of labels:")
        print(df[self.score_name].value_counts(dropna=False))

        # Separate 'Yes' and 'No' instances
        df_yes = df[df[self.score_name] == 'Yes']
        df_no = df[df[self.score_name] == 'No']

        # Determine the smaller class size
        smaller_class_size = min(len(df_yes), len(df_no))

        # Sample from the larger class to match the number of instances in the smaller class
        if len(df_yes) > len(df_no):
            print(f"Sampling {smaller_class_size} instances from the 'Yes' class...")
            df_yes = df_yes.sample(n=smaller_class_size, random_state=42)
        else:
            print(f"Sampling {smaller_class_size} instances from the 'No' class...")
            df_no = df_no.sample(n=smaller_class_size, random_state=42)

        # Concatenate 'Yes' and 'No' instances
        df_balanced = pd.concat([df_yes, df_no])

        # Shuffle the data
        df_balanced = df_balanced.sample(frac=1, random_state=42)

        # Sample a certain percentage of the data
        df_balanced = df_balanced.sample(frac=self.data_percentage, random_state=42)

        # Check the distribution of labels
        print("\nDistribution of labels:")
        print(df_balanced[self.score_name].value_counts())

        # Now you can use df_balanced for the rest of your code
        texts = df_balanced['Transcription'].tolist()
        labels = df_balanced[self.score_name].apply(lambda x: 1 if x == 'Yes' else 0).tolist()

    def train_model(self):
        """
        Train the model on the training data.

        :return: The trained model.
        """
        pass

    def evaluate_model(self):
        """
        Evaluate the model on the validation data.

        :return: The evaluation results.
        """
        pass

    def register_model(self):
        """
        Register the model with the model registry.
        """
        pass

    def predict(self, context, model_input):
        """
        Make predictions on the test data.

        :param context: MLflow context for the prediction.
        :param model_input: The input data for making predictions.
        :return: The predictions.
        """
        pass