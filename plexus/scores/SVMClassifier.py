import os
import pandas as pd
import numpy as np
import logging
import datetime
from dotenv import load_dotenv
load_dotenv('.env', override=True)
# import mlflow
# import mlflow.keras
from tqdm import tqdm
from transformers import BertTokenizer, TFBertModel
from transformers import MobileBertTokenizer, TFMobileBertModel
import tensorflow as tf
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
from sklearn.linear_model import SGDClassifier
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
from imblearn.over_sampling import SMOTE

from plexus.CustomLogging import logging
from plexus.scores.Score import Score
from plexus.scores.DeepLearningSlidingWindowEmbeddingsClassifier import BERTClassifier

from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report, precision_score, recall_score, f1_score
import numpy as np

class SVMClassifier(BERTClassifier):

    def start_mlflow_experiment_run(self):
        """
        Set up MLflow for tracking the experiment, including the experiment name and parameters.
        """
        super().start_mlflow_experiment_run()

    def train_model(self):
        """
        Train the model on the training data using incremental learning with SGDClassifier.

        :return: The trained model.
        """
        
        #############
        # Model setup

        from transformers import TFBertModel

        # BERT Model
        bert_model = TFBertModel.from_pretrained(self.bert_model_name)

        # Create the LinearSVC classifier
        svm_classifier = LinearSVC(random_state=42)

        # Define the chunk size for out-of-core learning
        chunk_size = 1000

        # Train the classifier incrementally
        for i in range(0, len(self.train_input_ids), chunk_size):
            # Extract the BERT embeddings for the current chunk
            chunk_input_ids = self.train_input_ids[i:i+chunk_size]
            chunk_attention_mask = self.train_attention_mask[i:i+chunk_size]
            chunk_embeddings = bert_model(chunk_input_ids, attention_mask=chunk_attention_mask)[1].numpy()
            
            # Train the classifier on the current chunk
            chunk_labels = self.train_labels[i:i+chunk_size]
            svm_classifier.fit(chunk_embeddings, chunk_labels)

        # Extract the BERT embeddings for the validation data
        val_embeddings = bert_model(self.val_input_ids, attention_mask=self.val_attention_mask)[1].numpy()

        # Make predictions on the validation set
        val_predictions = svm_classifier.predict(val_embeddings)

        # Calculate evaluation metrics
        val_accuracy = svm_classifier.score(val_embeddings, self.val_labels)
        val_precision = precision_score(self.val_labels, val_predictions)
        val_recall = recall_score(self.val_labels, val_predictions)
        val_f1 = f1_score(self.val_labels, val_predictions)

        # Log metrics to MLflow
        # mlflow.log_metric("validation_accuracy", val_accuracy)
        # mlflow.log_metric("validation_precision", val_precision)
        # mlflow.log_metric("validation_recall", val_recall)
        # mlflow.log_metric("validation_f1", val_f1)

        # Print classification report
        print("Classification Report:")
        print(classification_report(self.val_labels, val_predictions))

        # Log the trained SVM model
        # mlflow.sklearn.log_model(svm_classifier, "svm_model")

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