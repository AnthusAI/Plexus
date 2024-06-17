import os
import numpy as np
import mlflow
import mlflow.keras
from pydantic import BaseModel, validator, ValidationError
from transformers import TFAutoModel
from tensorflow.keras.metrics import Precision, Recall, AUC
import tensorflow as tf
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import regularizers
import nltk
nltk.download('punkt')
from rich.progress import Progress
from plexus.CustomLogging import logging, console
from plexus.classifiers.MLClassifier import MLClassifier
from tensorflow.keras.utils import to_categorical
from tensorflow.keras import mixed_precision
from sklearn.preprocessing import LabelBinarizer
from plexus.classifiers import Score, DeepLearningSemanticClassifier
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

class DeepLearningSlidingWindowEmbeddingsClassifier(DeepLearningSemanticClassifier):
    """
    This sub-class implements the sliding-windows variant of the DeepLearningSemanticClassifier.
    """

    class Parameters(DeepLearningSemanticClassifier.Parameters):
        ...
        multiple_windows_aggregation: str = 'max'

        @validator('multiple_windows_aggregation')
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
            super(DeepLearningSlidingWindowEmbeddingsClassifier.RaggedEmbeddingsLayer, self).__init__()
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

    def train_model(self):
        """
        Train the model on the training data.

        :return: The trained model.
        """

        # Determine if it's a binary or multi-class classification task
        logging.info(f"Is multi-class: [purple][bold]{self.is_multi_class}[/purple][/bold]")

        logging.info(f"train_input_ids shape: {self.train_input_ids.shape}")
        logging.info(f"train_attention_mask shape: {self.train_attention_mask.shape}")
        logging.info(f"train_labels shape: {self.train_labels.shape}")
        logging.info(f"val_input_ids shape: {self.val_input_ids.shape}")
        logging.info(f"val_attention_mask shape: {self.val_attention_mask.shape}")
        logging.info(f"val_labels shape: {self.val_labels.shape}")

        #############
        # Model setup

        logging.info("Model setup: Sliding window")

        input_ids = tf.keras.layers.Input(shape=(None, None,), ragged=True, dtype=tf.int32, name="input_ids")
        attention_mask = tf.keras.layers.Input(shape=(None, None,), ragged=True, dtype=tf.int32, name="attention_mask")
        
        self.embeddings_model = TFAutoModel.from_pretrained(self.parameters.embeddings_model)

        # # Set all layers of the embeddings model to non-trainable first
        for layer in self.embeddings_model.layers:
            layer.trainable = False

        # # Set only the top few layers to trainable, for fine-tuning
        trainable_layers = self.embeddings_model.layers[-self.parameters.embeddings_model_trainable_layers:]
        for layer in trainable_layers:
            layer.trainable = True

        # # Verify the trainability of each layer
        for i, layer in enumerate(self.embeddings_model.layers):
            logging.info(f"Layer {i} ({layer.name}) trainable: {layer.trainable}")

        # Create an instance of the custom layer
        ragged_embeddings_layer = DeepLearningSlidingWindowEmbeddingsClassifier.RaggedEmbeddingsLayer(self.embeddings_model, aggregation=self.parameters.multiple_windows_aggregation)

        # Pass the ragged tensors directly to the custom layer
        last_hidden_state = ragged_embeddings_layer([input_ids, attention_mask])
        logging.info(f"Shape of last_hidden_state: {last_hidden_state.shape}")

        # Get the hidden size from the pre-loaded model
        hidden_size = self.embeddings_model.config.hidden_size

        # Use the TimeDistributed layer to apply the dense layer to each window embedding
        window_level_output = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(hidden_size, activation='relu'))(last_hidden_state)
        logging.info(f"Shape of window_level_output: {window_level_output.shape}")

        # Perform max pooling over the window dimension
        aggregated_output = tf.reduce_max(window_level_output, axis=-2)
        logging.info(f"Shape of aggregated_output: {aggregated_output.shape}")

        tanh_output = tf.keras.layers.Dense(hidden_size, activation='tanh', name="tanh_amplifier_1")(aggregated_output)
        logging.info(f"Shape of tanh_output: {tanh_output.shape}")

        dropout = tf.keras.layers.Dropout(rate=self.parameters.dropout_rate, name="dropout")(tanh_output)
        logging.info(f"Shape of dropout: {dropout.shape}")

        # Add the final output layer
        if self.is_multi_class:
            number_of_labels = tf.shape(self.train_labels)[1]
            logging.info(f"Multi-class -- Number of labels: {number_of_labels}")
            out = tf.keras.layers.Dense(
                number_of_labels,
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
        logging.info(f"Shape of final output: {out.shape}")

        self.model = tf.keras.models.Model(inputs=[input_ids, attention_mask], outputs=out)

        # Monitor the gradients during training
        for layer in self.model.layers:
            if hasattr(layer, 'kernel'):
                layer.kernel.assign(tf.debugging.assert_all_finite(layer.kernel, message=f"Infinite or NaN values in {layer.name}.kernel"))
            if hasattr(layer, 'bias'):
                layer.bias.assign(tf.debugging.assert_all_finite(layer.bias, message=f"Infinite or NaN values in {layer.name}.bias"))

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
            'tmp/best_model_weights.h5',
            monitor='val_loss',
            save_best_only=True,
            save_weights_only=True,  # Save only the model weights
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

        # Load the best model weights
        print("Loading model weights...")
        self.model.load_weights('tmp/best_model_weights.h5')

        # Log the best model
        # print("Logging model weights...")
        # mlflow.keras.log_model(self.model, "best_model")