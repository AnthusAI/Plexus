import os
import pandas as pd
import numpy as np
from plexus import logging
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

class ProcessWindowLayer(tf.keras.layers.Layer):
    def __init__(self, bert_model, **kwargs):
        super(ProcessWindowLayer, self).__init__(**kwargs)
        self.bert_model = bert_model

    def call(self, inputs):
        window_input_ids, window_attention_mask = inputs
        pooled_output = self.bert_model(window_input_ids, attention_mask=window_attention_mask)[1]
        return pooled_output

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

        # Determine if it's a binary or multi-class classification task
        logging.info(f"Is multi-class: [purple][bold]{self.is_multi_class}[/purple][/bold]")
        
        #############
        # Model setup

        from transformers import TFBertModel

        # Sliding Window Model Architecture
        input_ids = tf.keras.layers.Input(shape=(None, self.window_size), dtype=tf.int32)
        attention_mask = tf.keras.layers.Input(shape=(None, self.window_size), dtype=tf.int32)
        bert_model = TFBertModel.from_pretrained(self.bert_model_name)

        for i in range(len(bert_model.bert.encoder.layer)):
            bert_model.bert.encoder.layer[i].trainable = False

        number_of_trainable_bert_layers = self.number_of_trainable_bert_layers
        for i in range(-(number_of_trainable_bert_layers), 0, 1):
            bert_model.bert.encoder.layer[i].trainable = True

        process_window_layer = ProcessWindowLayer(bert_model)

        pooled_outputs = tf.keras.layers.TimeDistributed(process_window_layer)([input_ids, attention_mask])

        pooled_output = tf.keras.layers.GlobalAveragePooling1D()(pooled_outputs)
        tanh_output = tf.keras.layers.Dense(768, activation='tanh')(pooled_output)
        dropout = Dropout(rate=self.dropout_rate)(tanh_output)

        if self.is_multi_class:
            num_labels = len(np.unique(self.train_labels_int))
            out = tf.keras.layers.Dense(
                num_labels,
                activation='softmax',
                kernel_regularizer=regularizers.l2(self.l2_regularization_strength)
            )(dropout)
        else:
            out = tf.keras.layers.Dense(
                1,
                activation='sigmoid',
                kernel_regularizer=regularizers.l2(self.l2_regularization_strength)
            )(dropout)

        self.model = tf.keras.models.Model(inputs=[input_ids, attention_mask], outputs=out)

        if self.is_multi_class:
            loss_function = 'categorical_crossentropy'
        else:
            loss_function = 'binary_crossentropy'

        self.model.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss=loss_function,
            metrics=['accuracy']
        )

        self.model.summary()

        print("Training the model...")

        def custom_lr_scheduler(epoch, lr):
            initial_wait_epochs = self.learning_rate_scheduler_initial_wait_epochs
            decay_rate = self.learning_rate_scheduler_decay_rate
            decay_step = self.learning_rate_scheduler_decay_step
            if (epoch >= initial_wait_epochs) and (epoch % decay_step == 0):
                return lr * decay_rate
            return lr
        reduce_lr = tf.keras.callbacks.LearningRateScheduler(custom_lr_scheduler)

        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=self.early_stop_patience,
            verbose=1,
            restore_best_weights=True
        )

        checkpoint = tf.keras.callbacks.ModelCheckpoint(
            'tmp/best_model_weights.h5',
            monitor='val_loss',
            save_best_only=True,
            save_weights_only=True,
            mode='min',
            verbose=1
        )

        # Ensure input arrays are properly shaped and contain consistent data types
        self.train_input_ids = tf.keras.preprocessing.sequence.pad_sequences(self.train_input_ids, padding='post', dtype='int32')
        self.train_attention_mask = tf.keras.preprocessing.sequence.pad_sequences(self.train_attention_mask, padding='post', dtype='int32')
        self.train_labels = np.array(self.train_labels, dtype=np.float32 if not self.is_multi_class else np.int32)

        # Assuming self.train_input_ids and self.train_attention_mask are lists of batches
        print(f"Shape of a single batch of train_input_ids: {np.array(self.train_input_ids[0]).shape}")
        print(f"Shape of a single batch of train_attention_mask: {np.array(self.train_attention_mask[0]).shape}")

        # Print the number of windows per transcript
        num_windows_per_transcript = [len(seq) for seq in self.train_input_ids]
        print(f"Number of windows per transcript: {num_windows_per_transcript}")
        print(f"Max number of windows in a transcript: {max(num_windows_per_transcript)}")

        self.val_input_ids = tf.keras.preprocessing.sequence.pad_sequences(self.val_input_ids, padding='post', dtype='int32')
        self.val_attention_mask = tf.keras.preprocessing.sequence.pad_sequences(self.val_attention_mask, padding='post', dtype='int32')
        self.val_labels = np.array(self.val_labels, dtype=np.float32 if not self.is_multi_class else np.int32)

        train_input_ids_tensor = tf.convert_to_tensor(self.train_input_ids, dtype=tf.int32)
        train_attention_mask_tensor = tf.convert_to_tensor(self.train_attention_mask, dtype=tf.int32)
        train_labels_tensor = tf.convert_to_tensor(self.train_labels, dtype=tf.float32 if not self.is_multi_class else tf.int32)

        val_input_ids_tensor = tf.convert_to_tensor(self.val_input_ids, dtype=tf.int32)
        val_attention_mask_tensor = tf.convert_to_tensor(self.val_attention_mask, dtype=tf.int32)
        val_labels_tensor = tf.convert_to_tensor(self.val_labels, dtype=tf.float32 if not self.is_multi_class else tf.int32)

        self.history = self.model.fit(
            [train_input_ids_tensor, train_attention_mask_tensor], 
            train_labels_tensor, 
            validation_data=([val_input_ids_tensor, val_attention_mask_tensor], val_labels_tensor),
            epochs=self.epochs,
            batch_size=self.batch_size,
            callbacks=[reduce_lr, early_stop, checkpoint],
            verbose=1
        )

        print("Logging metrics and artifacts...")

        mlflow.log_metric("training_loss", self.model.history.history['loss'][-1])
        mlflow.log_metric("validation_loss", self.model.history.history['val_loss'][-1])
        mlflow.log_metric("training_accuracy", self.model.history.history['accuracy'][-1])
        mlflow.log_metric("validation_accuracy", self.model.history.history['val_accuracy'][-1])

        print("Training complete.")
            # Log the best model
            # print("Logging model weights...")
            # mlflow.keras.log_model(self.model, "best_model")

    def evaluate_model(self):
        """
        Evaluate the model on the validation data.

        :return: The evaluation results.
        """
        print("Generating evaluation metrics...")

        # Load the best model weights
        print("Loading model weights...")
        self.model.load_weights('tmp/best_model_weights.h5')

        # Predict on validation set
        self.val_predictions = self.model.predict([self.val_encoded_texts, self.val_attention_mask])

        if self.is_multi_class:
            self.val_predictions_labels = np.argmax(self.val_predictions, axis=1)
        else:
            self.val_predictions_labels = [1 if pred > 0.5 else 0 for pred in tqdm(self.val_predictions, desc="Processing Validation Predictions")]

        # Compute evaluation metrics
        accuracy = accuracy_score(self.val_labels_int, self.val_predictions_labels)
        f1 = f1_score(self.val_labels_int, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')
        recall = recall_score(self.val_labels_int, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')
        precision = precision_score(self.val_labels_int, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')

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