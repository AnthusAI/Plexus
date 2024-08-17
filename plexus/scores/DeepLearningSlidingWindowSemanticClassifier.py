import os
import json
import numpy as np
import mlflow
import mlflow.keras
from pydantic import BaseModel, field_validator, ValidationError
from transformers import TFAutoModel
from tensorflow.keras.metrics import Precision, Recall, AUC
import tensorflow as tf
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import regularizers
import nltk
nltk.download('punkt')
from typing import Optional
from rich.progress import Progress
from plexus.CustomLogging import logging, console
from plexus.scores.Score import Score
from tensorflow.keras.utils import to_categorical
from tensorflow.keras import mixed_precision
from sklearn.preprocessing import LabelBinarizer
from plexus.scores import Score, DeepLearningSemanticClassifier
from plexus.scores.core.utils import ensure_model_directory_exists
import matplotlib.pyplot as plt
from tensorflow.keras import backend as keras_backend
keras_backend.clear_session()

# Set the environment variable to allow GPU memory growth
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'

# Use the CUDA asynchronous memory allocator to reduce memory fragmentation.
os.environ['TF_GPU_ALLOCATOR'] = 'cuda_malloc_async'

# Set the global policy for mixed precision
policy = mixed_precision.Policy('mixed_float16')
mixed_precision.set_global_policy(policy)

class DeepLearningSlidingWindowSemanticClassifier(DeepLearningSemanticClassifier):
    """
    This sub-class implements the sliding-windows variant of the DeepLearningSemanticClassifier.
    """

    class Parameters(DeepLearningSemanticClassifier.Parameters):
        ...
        multiple_windows_aggregation: str = 'max'
        number_of_classes: Optional[int] = 2

        @field_validator('multiple_windows_aggregation')
        def validate_multiple_windows_aggregation(cls, value):
            allowed_values = ['max', 'mean']
            if value not in allowed_values:
                raise ValueError(f"multiple_windows_aggregation must be one of {allowed_values}")
            return value

    def __init__(self, *args, **parameters):
        super().__init__(*args, **parameters)
        self.validation_losses = []

    class RaggedEmbeddingsLayer(tf.keras.layers.Layer):
        def __init__(self, embeddings_model, aggregation='max'):
            super(DeepLearningSlidingWindowSemanticClassifier.RaggedEmbeddingsLayer, self).__init__()
            self.embeddings_model = DeepLearningSemanticClassifier.EmbeddingsLayer(embeddings_model)
            self.aggregation = aggregation

        def call(self, inputs):
            input_ids, attention_mask = inputs
            def embed_single_instance(args):
                single_input_id, single_attention_mask = args
                single_embedding = self.embeddings_model([single_input_id, single_attention_mask])
                if self.aggregation == 'mean':
                    aggregated_embedding = tf.reduce_mean(single_embedding, axis=0)
                elif self.aggregation == 'max':
                    aggregated_embedding = tf.reduce_max(single_embedding, axis=0)
                else:
                    raise ValueError(f"Unsupported aggregation method: {self.aggregation}")
                return aggregated_embedding

            sample_embeddings = tf.map_fn(
                embed_single_instance,
                (input_ids, attention_mask),
                fn_output_signature=tf.float32
            )

            logging.info(f"Shape of sample_embeddings: {sample_embeddings.shape}")

            return sample_embeddings

    def create_model(self):
        """
        Create and return the model architecture.

        :return: The created model.
        """
        input_ids = tf.keras.layers.Input(shape=(None, None,), ragged=True, dtype=tf.int32, name="input_ids")
        attention_mask = tf.keras.layers.Input(shape=(None, None,), ragged=True, dtype=tf.int32, name="attention_mask")
        
        self.embeddings_model = TFAutoModel.from_pretrained(self.parameters.embeddings_model)

        # Set all layers of the embeddings model to non-trainable first
        for layer in self.embeddings_model.layers:
            layer.trainable = False

        # Set only the top few layers to trainable, for fine-tuning
        trainable_layers = self.embeddings_model.layers[-self.parameters.embeddings_model_trainable_layers:]
        for layer in trainable_layers:
            layer.trainable = True

        # Create an instance of the custom layer
        ragged_embeddings_layer = self.RaggedEmbeddingsLayer(self.embeddings_model, aggregation=self.parameters.multiple_windows_aggregation)

        # Pass the ragged tensors directly to the custom layer
        last_hidden_state = ragged_embeddings_layer([input_ids, attention_mask])

        # Get the hidden size from the pre-loaded model
        hidden_size = self.embeddings_model.config.hidden_size

        # Use the TimeDistributed layer to apply the dense layer to each window embedding
        window_level_output = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(hidden_size, activation='relu'))(last_hidden_state)

        # Perform max pooling over the window dimension
        aggregated_output = tf.reduce_max(window_level_output, axis=-2)

        tanh_output = tf.keras.layers.Dense(hidden_size, activation='tanh', name="tanh_amplifier_1")(aggregated_output)

        dropout = tf.keras.layers.Dropout(rate=self.parameters.dropout_rate, name="dropout")(tanh_output)

        # Add the final output layer
        if self.parameters.number_of_classes > 2:
            out = tf.keras.layers.Dense(
                self.parameters.number_of_classes,
                activation='softmax',
                kernel_regularizer=regularizers.l2(self.parameters.l2_regularization_strength),
                name="softmax_multiclass_classifier"
            )(dropout)
        else:
            out = tf.keras.layers.Dense(
                1,
                activation='sigmoid',
                kernel_regularizer=regularizers.l2(self.parameters.l2_regularization_strength),
                name="sigmoid_binary_classifier"
            )(dropout)

        model = tf.keras.models.Model(inputs=[input_ids, attention_mask], outputs=out)

        return model

    @ensure_model_directory_exists
    def train_model(self):
        """
        Train the model on the training data.

        :return: The trained model.
        """

        # Determine if it's a binary or multi-class classification task
        logging.info(f"Is multi-class: [purple][bold]{self.is_multi_class}[/purple][/bold]")

        # Check the number of classes
        actual_number_of_classes = self.number_of_classes
        
        if self.parameters.number_of_classes != actual_number_of_classes:
            raise ValueError(f"Mismatch in number of classes.  Please set \"number_of_classes: {actual_number_of_classes}\" in the configuration to "
                             f"Configured: {self.parameters.number_of_classes}, "
                             f"Actual: {actual_number_of_classes}")
        else:
            logging.info(f"Number of classes matches configuration: {self.parameters.number_of_classes}")

        # Create the model
        self.model = self.create_model()

        # Compile the model with the appropriate loss function
        if self.is_multi_class:
            loss_function = tf.keras.losses.CategoricalCrossentropy(reduction='auto')
        else:
            loss_function = 'binary_crossentropy'

        self.model.compile(
            optimizer=Adam(learning_rate=self.parameters.plateau_learning_rate),
            loss=loss_function,
            metrics=['accuracy', Precision(name='precision'), Recall(name='recall'), AUC(name='auc')]
        )

        # During training, after the model is defined
        self.model.summary(print_fn=lambda x: logging.info(x))

        self._generate_model_diagram()

        #############
        # Training

        learning_rate_scheduler = tf.keras.callbacks.LearningRateScheduler(
            lambda epoch, lr: self.custom_lr_scheduler(epoch, lr)
        )

        # Stop training if the validation loss doesn't improve after a certain number of number_of_epochs.
        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=5,  # Increase patience to allow more number_of_epochs for improvement
            verbose=1,
            restore_best_weights=True  # Restore the best model weights
        )

        # Save the best model weights
        checkpoint = tf.keras.callbacks.ModelCheckpoint(
            os.path.join(self.model_directory_path(), 'best_model_weights.h5'),
            monitor='val_loss',
            save_best_only=True,
            save_weights_only=True,
            mode='min',
            verbose=1
        )

        logging.info(f"Training the model...")
        logging.info(f"train_input_ids shape: {self.train_input_ids.shape}")
        logging.info(f"train_attention_mask shape: {self.train_attention_mask.shape}")
        logging.info(f"train_labels shape: {self.train_labels.shape}")

        # Ensure the shapes are compatible
        # assert self.train_input_ids.shape[0] == self.train_attention_mask.shape[0] == self.train_labels.shape[0], "Incompatible shapes"

        self.history = self.model.fit(
            x=[self.train_input_ids, self.train_attention_mask],
            y=self.train_labels,
            validation_data=([self.val_input_ids, self.val_attention_mask], self.val_labels),
            epochs=self.parameters.number_of_epochs,
            batch_size=self.parameters.batch_size,
            callbacks=[early_stop, checkpoint, learning_rate_scheduler],
        )

        print("Logging metrics and artifacts...")

        # Log metrics to MLflow
        mlflow.log_metric("training_loss", self.model.history.history['loss'][-1])
        mlflow.log_metric("training_accuracy", self.model.history.history['accuracy'][-1])
        mlflow.log_metric("validation_loss", self.model.history.history['val_loss'][-1])
        mlflow.log_metric("validation_accuracy", self.model.history.history['val_accuracy'][-1])

        # After training is complete:
        inverse_label_map = {int(k): v for k, v in self.inverse_label_map.items()}
        inverse_label_map_path = os.path.join(self.model_directory_path(), 'inverse_label_map.json')
        with open(inverse_label_map_path, 'w') as f:
            json.dump(inverse_label_map, f)

        logging.info(f"Best model weights saved to tmp/best_model_weights.h5")
        logging.info(f"Inverse label map saved to {inverse_label_map_path}")
