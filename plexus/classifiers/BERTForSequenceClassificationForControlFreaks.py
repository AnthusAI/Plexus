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
from sklearn.metrics import accuracy_score, f1_score, recall_score, precision_score
from imblearn.over_sampling import SMOTE
import nltk
nltk.download('punkt')

from plexus.CustomLogging import logging
from plexus.classifiers.MLClassifier import MLClassifier
from plexus.classifiers.BERTClassifier import BERTClassifier

class BERTForSequenceClassificationForControlFreaks(BERTClassifier):

    def set_up_mlflow(self):
        """
        Set up MLflow for tracking the experiment, including the experiment name and parameters.
        """
        super().set_up_mlflow()

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

    def train_model(self):
        """
        Train the model on the training data.

        :return: The trained model.
        """
        
        #############
        # Model setup

        from transformers import TFBertModel

        # BERT Model
        input_ids = tf.keras.layers.Input(shape=(self.max_len,), dtype=tf.int32)
        attention_mask = tf.keras.layers.Input(shape=(self.max_len,), dtype=tf.int32)
        bert_model = TFBertModel.from_pretrained(self.bert_model_name)

        # Set all layers to non-trainable first
        for i in range(len(bert_model.bert.encoder.layer)):
            bert_model.bert.encoder.layer[i].trainable = False

        # Set only some layers to trainable, for fine-tuning.
        number_of_trainable_bert_layers = 1
        for i in range(-(number_of_trainable_bert_layers), 0, 1):
            bert_model.bert.encoder.layer[i].trainable = True

        # Verify the trainability of each layer
        for i, layer in enumerate(bert_model.bert.encoder.layer):
            print(f"Layer {i} trainable: {layer.trainable}")

        # Extract the pooled output from the BERT model
        pooled_output = bert_model.bert(input_ids, attention_mask=attention_mask)[1]

        # Add a tanh activation layer
        tanh_output = tf.keras.layers.Dense(768, activation='tanh')(pooled_output)

        # Apply dropout for regularization
        dropout = Dropout(rate=self.dropout_rate)(tanh_output)

        # intermediate_size = 768

        # intermediate_dense = tf.keras.layers.Dense(
        #     intermediate_size,
        #     activation='relu',
        #     kernel_regularizer=regularizers.l2(l2_regularization_strength)
        # )(dropout)

        # intermediate_dropout = Dropout(rate=dropout_rate)(intermediate_dense)

        out = tf.keras.layers.Dense(
            1,
            activation='sigmoid',
            kernel_regularizer=regularizers.l2(self.l2_regularization_strength)
        )(dropout)

        self.model = tf.keras.models.Model(inputs=[input_ids, attention_mask], outputs=out)

        # Compile the model
        self.model.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )

        self.model.summary()

        #############
        # Training

        print("Training the model...")

        # Reduces the learning rate when the validation loss metric has stopped improving.
        def custom_lr_scheduler(epoch, lr):
            initial_wait_epochs = self.learning_rate_scheduler_initial_wait_epochs
            decay_rate = self.learning_rate_scheduler_decay_rate
            decay_step = self.learning_rate_scheduler_decay_step
            if (epoch >= initial_wait_epochs) and (epoch % decay_step == 0):
                return lr * decay_rate
            return lr
        reduce_lr = tf.keras.callbacks.LearningRateScheduler(custom_lr_scheduler)

        # Stop training if the validation loss doesn't improve after a certain number of epochs.
        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=5,  # Increase patience to allow more epochs for improvement
            verbose=1,
            restore_best_weights=True  # Restore the best model weights
        )

        # Save the best model weights
        checkpoint = tf.keras.callbacks.ModelCheckpoint(
            'tmp/best_model_weights.h5',
            monitor='val_loss',
            save_best_only=True,
            save_weights_only=True,  # Save only the model weights
            mode='min',
            verbose=1
        )

        self.history = self.model.fit(
            [self.train_input_ids, self.train_attention_mask], 
            self.train_labels, 
            validation_data=([self.val_input_ids, self.val_attention_mask], self.val_labels),
            epochs=self.epochs, 
            batch_size=self.batch_size,
            callbacks=[reduce_lr, early_stop, checkpoint],
            verbose=1
        )

        print("Logging metrics and artifacts...")

        # Log metrics to MLflow
        mlflow.log_metric("training_loss", self.model.history.history['loss'][-1])
        mlflow.log_metric("training_accuracy", self.model.history.history['accuracy'][-1])
        mlflow.log_metric("validation_loss", self.model.history.history['val_loss'][-1])
        mlflow.log_metric("validation_accuracy", self.model.history.history['val_accuracy'][-1])

        # Load the best model weights
        print("Loading model weights...")
        self.model.load_weights('tmp/best_model_weights.h5')

        # Log the best model
        # print("Logging model weights...")
        # mlflow.keras.log_model(self.model, "best_model")

    def evaluate_model(self):
        """
        Evaluate the model on the validation data.

        :return: The evaluation results.
        """
        print("Generating evaluation metrics...")

        # Predict on validation set
        self.val_predictions = self.model.predict([self.val_encoded_texts, self.val_attention_mask])
        self.val_predictions = [1 if pred > 0.5 else 0 for pred in tqdm(self.val_predictions, desc="Processing Validation Predictions")]

        # Compute evaluation metrics
        accuracy = accuracy_score(self.val_labels, self.val_predictions)
        f1 = f1_score(self.val_labels, self.val_predictions)
        recall = recall_score(self.val_labels, self.val_predictions)
        precision = precision_score(self.val_labels, self.val_predictions)

        # Log evaluation metrics to MLflow
        mlflow.log_metric("validation_f1_score", f1)
        mlflow.log_metric("validation_recall", recall)
        mlflow.log_metric("validation_precision", precision)

        print(f"Validation Accuracy: {accuracy:.4f}")
        print(f"Validation F1 Score: {f1:.4f}")
        print(f"Validation Recall: {recall:.4f}")
        print(f"Validation Precision: {precision:.4f}")

        # # Calculate the difference between the final training and validation accuracy
        # accuracy_diff = train_accuracy[-1] - val_accuracy[-1]

        # # Calculate the difference between the final training and validation loss
        # loss_diff = train_loss[-1] - val_loss[-1]

        # print(f"Difference in Accuracy: {accuracy_diff}")
        # print(f"Difference in Loss: {loss_diff}")

        # mlflow.log_metric("difference_in_accuracy", accuracy_diff)
        # mlflow.log_metric("difference_in_loss", loss_diff)

        print("Generating visualizations...")

        self._generate_confusion_matrix()

        self._plot_roc_curve()

        self._plot_precision_recall_curve()

        self._plot_training_history()

        metrics = {
            "training_loss": self.history.history['loss'][-1],
            "training_accuracy": self.history.history['accuracy'][-1],
            "validation_loss": self.history.history['val_loss'][-1],
            "validation_accuracy": self.history.history['val_accuracy'][-1],
            "validation_f1_score": f1,
            "validation_recall": recall,
            "validation_precision": precision
        }

        self._record_metrics(metrics)

        # End MLflow run
        mlflow.end_run()

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