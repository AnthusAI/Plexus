import os
import pandas as pd
import numpy as np
import mlflow
import mlflow.keras
from tqdm import tqdm
from rich.progress import Progress
from transformers import AutoTokenizer, TFAutoModel
from tensorflow.keras.metrics import Precision, Recall, AUC
import tensorflow as tf
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import regularizers
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, recall_score, precision_score
import nltk
nltk.download('punkt')
from concurrent.futures import ThreadPoolExecutor
from rich.progress import Progress
from plexus.CustomLogging import logging, console
from plexus.classifiers.MLClassifier import MLClassifier
from tensorflow.keras.utils import to_categorical
from tensorflow.keras import mixed_precision
from sklearn.preprocessing import LabelBinarizer
from plexus.classifiers.Classifier import Classifier
import matplotlib.pyplot as plt

policy = mixed_precision.Policy('mixed_float16')
mixed_precision.set_global_policy(policy)

class EmbeddingsLayer(tf.keras.layers.Layer):
    def __init__(self, embeddings_model_name, **kwargs):
        super(EmbeddingsLayer, self).__init__(**kwargs)
        self.embeddings_model = TFAutoModel.from_pretrained(embeddings_model_name)

    def call(self, inputs):
        input_ids, attention_mask = inputs
        if isinstance(input_ids, tf.RaggedTensor):
            input_ids = input_ids.to_tensor(default_value=0)
        if isinstance(attention_mask, tf.RaggedTensor):
            attention_mask = attention_mask.to_tensor(default_value=0)
        outputs = self.embeddings_model(input_ids, attention_mask=attention_mask)
        last_hidden_state = outputs[0]
        return last_hidden_state

class RaggedEmbeddingsLayer(tf.keras.layers.Layer):
    def __init__(self, embeddings_model_name):
        super(RaggedEmbeddingsLayer, self).__init__()
        self.embeddings_model = EmbeddingsLayer(embeddings_model_name)

    def call(self, inputs):
        input_ids, attention_mask = inputs
        # Ensure that the embeddings model processes each element of the input tensors individually
        # and the output is concatenated back into a ragged tensor with the same structure.
        def embed_single_instance(args):
            single_input_id, single_attention_mask = args
            return self.embeddings_model([single_input_id, single_attention_mask])

        # Apply the embedding model to each element of the ragged tensor individually
        ragged_embeddings = tf.ragged.map_flat_values(
            embed_single_instance,
            (input_ids, attention_mask)
        )
        # Flatten the ragged tensor to reduce unnecessary dimensions
        return ragged_embeddings.flat_values

class EmbeddingsDNNClassifier(MLClassifier):
    """
    This is a base class for classifiers based on BERT embeddings that must pre-propcess data in the same way by tokenizing it with the BERT model.
    """

    def __init__(self, *args, **parameters):
        super().__init__(*args, **parameters)
        self.validation_losses = []
        self.data_percentage = float(str(self.data_percentage).strip().replace('%', ''))

    def process_data(self):
        """
        Handle any pre-processing of the training data, including the training/validation splits.
        """

        # Call the parent process_data method first, which will iterate over any processor classes
        # configured in the scorecard YAML file.
        super().process_data()

        #############
        # Tokenization

        tokenizer = AutoTokenizer.from_pretrained(self.embeddings_model_name, do_lower_case=True)

        train_texts = {}
        train_labels = {}
        train_windows = {}
        val_texts = {}
        val_labels = {}
        val_windows = {}
        label_map = {}

        def split_into_sentences(text):
            return nltk.sent_tokenize(text)

        def tokenize_sentence(tokenizer, sentence):
            return tokenizer.tokenize(sentence)

        def build_sliding_windows(tokenizer, text, max_tokens_per_window, max_windows):
            windows = []
            windows_tokens = []
            current_window = []
            current_window_tokens = []

            sentences = split_into_sentences(text.replace('\n', ' '))

            for sentence in sentences:
                sentence_tokens = tokenize_sentence(tokenizer, sentence)
                if len(current_window_tokens) + len(sentence_tokens) <= max_tokens_per_window:
                    current_window.append(sentence)
                    current_window_tokens.extend(sentence_tokens)
                else:
                    windows.append(current_window)
                    windows_tokens.append(current_window_tokens)
                    current_window = [sentence]
                    current_window_tokens = sentence_tokens

                if len(windows) >= max_windows:
                    break

            if current_window and len(windows) < max_windows:
                windows.append(current_window)
                windows_tokens.append(current_window_tokens)

            return windows, windows_tokens

        def encode_single_text(tokenizer, text, maximum_length):
            """
            A "single text" could be either a single string or a list of strings, because of the sliding-windows feature.
            """
            if isinstance(text, list):
                text = ' '.join(text)
            return tokenizer.encode(text, padding='max_length', truncation=True, max_length=maximum_length, return_tensors='tf')

        def encode_texts_parallel(tokenizer, texts, maximum_length):
            encoded_texts = []
            with ThreadPoolExecutor() as executor:
                with Progress() as progress:
                    task = progress.add_task("Encoding texts...", total=len(texts))
                    futures = [executor.submit(encode_single_text, tokenizer, text, maximum_length) for text in texts]
                    for future in futures:
                        encoded_texts.append(future.result())
                        progress.advance(task)
            return tf.concat(encoded_texts, axis=0)

        def encode_windows_parallel(tokenizer, windows, maximum_length):
            flat_windows = [text for window in windows for text in window]
            encoded_flat_windows = encode_texts_parallel(tokenizer, flat_windows, maximum_length)
            
            window_lengths = [len(window) for window in windows]
            encoded_windows_ragged = tf.RaggedTensor.from_row_lengths(encoded_flat_windows, window_lengths)
            
            # Create attention masks for the flattened windows
            attention_masks_flat = tf.where(encoded_flat_windows != 0, 1, 0)
            
            # Create ragged attention masks using the same window lengths
            attention_masks_ragged = tf.RaggedTensor.from_row_lengths(attention_masks_flat, window_lengths)

            # Log detailed information for the first window only
            if len(windows) > 0:
                logging.info(f"First window encoded ragged tensor: {encoded_windows_ragged[0]}")
                logging.info(f"First window attention mask ragged tensor: {attention_masks_ragged[0]}")

            return encoded_windows_ragged, attention_masks_ragged

        texts = self.dataframe['Transcription'].tolist()
        labels = self.dataframe[self.score_name].tolist()
        unique_labels = self.dataframe[self.score_name].unique()

        # Split the data into training and validation sets
        train_texts, val_texts, train_labels, val_labels = train_test_split(texts, labels, test_size=0.2, random_state=42)

        logging.info(f"Original shape of train_texts: {np.shape(train_texts)}")
        logging.info(f"Original shape of val_texts: {np.shape(val_texts)}")
        logging.info(f"Original shape of train_labels: {np.shape(train_labels)}")
        logging.info(f"Original shape of val_labels: {np.shape(val_labels)}")

        # Convert labels to integers
        label_map = {label: i for i, label in enumerate(unique_labels)}
        train_labels = np.array([label_map[label] for label in train_labels])
        val_labels = np.array([label_map[label] for label in val_labels])

        if hasattr(self, 'sliding_window') and self.sliding_window:

            # Build sliding windows for training and validation texts
            train_windows, train_windows_tokens = zip(*[build_sliding_windows(tokenizer, text, self.maximum_number_of_tokens_analyzed, self.sliding_window_maximum_number_of_windows) for text in train_texts])
            val_windows, val_windows_tokens = zip(*[build_sliding_windows(tokenizer, text, self.maximum_number_of_tokens_analyzed, self.sliding_window_maximum_number_of_windows) for text in val_texts])

            if hasattr(self, 'sliding_window_maximum_number_of_windows'):
                # Limit the number of windows for each text
                train_windows = [windows[:self.sliding_window_maximum_number_of_windows] for windows in train_windows]
                val_windows = [windows[:self.sliding_window_maximum_number_of_windows] for windows in val_windows]

            # Log the lengths of the windows
            logging.info(f"Number of train_windows after building: {len(train_windows)}")
            logging.info(f"Number of val_windows after building: {len(val_windows)}")
            logging.info(f"Lengths of individual train_windows: {[len(w) for w in train_windows]}")
            logging.info(f"Lengths of individual val_windows: {[len(w) for w in val_windows]}")

            # Log the number of windows for each text
            logging.debug(f"Number of training windows per sample: {[len(windows) for windows in train_windows]}")
            logging.debug(f"Number of validation windows per sample: {[len(windows) for windows in val_windows]}")

            combined_windows = train_windows + val_windows
            self._generate_window_count_histogram(combined_windows)

            # Log a random labeled sample as it gets broken into windows
            random_index = np.random.randint(len(train_texts))
            random_text = train_texts[random_index]
            random_label = train_labels[random_index]
            random_windows = train_windows[random_index]

            print(f"Random labeled sample (label: {random_label}):")
            print(random_text)
            print("Sliding windows:")
            for i, window in enumerate(random_windows):
                print(f"Window {i + 1}:")
                print(" ".join(window))

            # Encode the training and validation windows
            train_encoded_windows, train_attention_masks = encode_windows_parallel(tokenizer, train_windows, self.maximum_number_of_tokens_analyzed)
            val_encoded_windows, val_attention_masks = encode_windows_parallel(tokenizer, val_windows, self.maximum_number_of_tokens_analyzed)

            # Log the shapes of the encoded windows
            logging.info(f"Shape of train_encoded_windows after encoding: {train_encoded_windows.shape}")
            logging.info(f"Shape of val_encoded_windows after encoding: {val_encoded_windows.shape}")
 
            def create_attention_masks(encoded_windows):
                attention_masks = []
                for window in encoded_windows:
                    # Apply tf.where to each tensor within the ragged tensor
                    mask = tf.ragged.map_flat_values(tf.where, window != 0, 1, 0)
                    attention_masks.append(mask)
                return attention_masks

            train_input_ids = tf.ragged.constant([tf.concat(window, axis=0).numpy() for window in train_encoded_windows], dtype=tf.int32)
            val_input_ids = tf.ragged.constant([tf.concat(window, axis=0).numpy() for window in val_encoded_windows], dtype=tf.int32)
            train_attention_mask = tf.ragged.constant([tf.concat(mask, axis=0).numpy() for mask in train_attention_masks], dtype=tf.int32)
            val_attention_mask = tf.ragged.constant([tf.concat(mask, axis=0).numpy() for mask in val_attention_masks], dtype=tf.int32)

            # Log the lengths before expansion
            logging.info(f"Number of train labels: {len(train_labels)}")
            logging.info(f"Number of train windows: {len(train_windows)}")
            logging.info(f"Number of val labels: {len(val_labels)}")
            logging.info(f"Number of val windows: {len(val_windows)}")

            logging.info(f"train_input_ids type: {type(train_input_ids)}, shape: {train_input_ids.shape}")
            logging.debug(f"train_input_ids sample: {train_input_ids[:5]}")

            logging.info(f"train_attention_mask type: {type(train_attention_mask)}, shape: {train_attention_mask.shape}")
            logging.debug(f"train_attention_mask sample: {train_attention_mask[:5]}")

            logging.info(f"train_labels type: {type(train_labels)}, shape: {train_labels.shape}")
            logging.debug(f"train_labels sample: {train_labels[:5]}")

            # Check the distribution of labels in the training set for the sliding window scenario
            print("Training set label breakdown (sliding window):")
            if self.is_multi_class:
                train_label_counts = np.unique(train_labels, return_counts=True)
                print(dict(zip(unique_labels, train_label_counts[1])))
            else:
                train_label_counts = np.unique(train_labels, return_counts=True)
                print(dict(zip(unique_labels, train_label_counts[1])))

            # Check the distribution of labels in the validation set for the sliding window scenario
            print("Validation set label breakdown (sliding window):")
            if self.is_multi_class:
                val_label_counts = np.unique(val_labels, return_counts=True)
                print(dict(zip(unique_labels, val_label_counts[1])))
            else:
                val_label_counts = np.unique(val_labels, return_counts=True)
                print(dict(zip(unique_labels, val_label_counts[1])))
            
            logging.info(f"train_input_ids type: {type(train_input_ids)}, shape: {train_input_ids.shape}")
            logging.debug(f"train_input_ids sample: {train_input_ids[:5]}")

            logging.info(f"train_attention_mask type: {type(train_attention_mask)}, shape: {train_attention_mask.shape}")
            logging.debug(f"train_attention_mask sample: {train_attention_mask[:5]}")

        else:

            # Encode the training and validation texts
            print("Training:")
            train_input_ids = encode_texts_parallel(tokenizer, train_texts, self.maximum_number_of_tokens_analyzed)
            print("Validation:")
            val_input_ids = encode_texts_parallel(tokenizer, val_texts, self.maximum_number_of_tokens_analyzed)

            # Create attention masks
            train_attention_mask = tf.where(train_input_ids != 0, 1, 0)
            val_attention_mask = tf.where(val_input_ids != 0, 1, 0)

            # Log the types and shapes of the labels for the non-sliding window scenario
            logging.info(f"train_labels type: {type(train_labels)}, length: {len(train_labels)}")
            logging.info(f"val_labels type: {type(val_labels)}, length: {len(val_labels)}")
            logging.debug(f"train_labels sample: {train_labels[:5]}")
            logging.debug(f"val_labels sample: {val_labels[:5]}")

        # unique_labels, label_counts = np.unique(train_labels, return_counts=True)
        # logging.info(f"Unique labels before one-hot encoding: {unique_labels}")
        # logging.info(f"Label counts before one-hot encoding: {label_counts}")

        # One-hot encode the labels only if it's a multi-class classification
        if self.is_multi_class:
            lb = LabelBinarizer()
            if hasattr(self, 'sliding_window') and self.sliding_window:
                train_labels = tf.ragged.constant(lb.fit_transform(train_labels.flat_values))
                val_labels = tf.ragged.constant(lb.transform(val_labels.flat_values))
            else:
                train_labels = lb.fit_transform(train_labels)
                val_labels = lb.transform(val_labels)
        else:
            if not (hasattr(self, 'sliding_window') and self.sliding_window):
                train_labels = train_labels.reshape(-1, 1)
                val_labels = val_labels.reshape(-1, 1)

        # unique_labels_onehot, label_counts_onehot = np.unique(train_labels, axis=0, return_counts=True)
        # logging.info(f"Unique labels after one-hot encoding: {unique_labels_onehot}")
        # logging.info(f"Label counts after one-hot encoding: {label_counts_onehot}")

        # Logging for debugging
        logging.info(f"train_labels type: {type(train_labels)}, shape: {train_labels.shape}")
        logging.info(f"train_labels sample: {train_labels[:5]}")
        logging.info(f"val_labels type: {type(val_labels)}, shape: {val_labels.shape}")
        logging.info(f"val_labels sample: {val_labels[:5]}")
    
        # Remember the important stuff for later.
        self.train_input_ids = train_input_ids
        self.val_input_ids = val_input_ids
        self.train_attention_mask = train_attention_mask
        self.val_attention_mask = val_attention_mask
        self.train_labels = train_labels
        self.val_labels = val_labels
        self.label_map = label_map

    def custom_lr_scheduler(self, epoch, lr):
        # Record validation loss if available
        if hasattr(self, 'model') and hasattr(self.model, 'history') and 'val_loss' in self.model.history.history:
            val_loss = self.model.history.history['val_loss'][-1]
            self.validation_losses.append(val_loss)
        else:
            val_loss = None
        
        if epoch < self.warmup_number_of_epochs:
            # Linear warmup
            progress = epoch / self.warmup_number_of_epochs
            new_lr = self.warmup_start_learning_rate + progress * (self.plateau_learning_rate - self.warmup_start_learning_rate)
        elif epoch < self.warmup_number_of_epochs + self.plateau_number_of_epochs:
            # Plateau
            new_lr = self.plateau_learning_rate
        else:
            # Decay
            decay_steps = epoch - (self.warmup_number_of_epochs + self.plateau_number_of_epochs)
            new_lr = self.plateau_learning_rate * (self.learning_rate_decay ** decay_steps)
        
        # Reduce learning rate if validation loss increased compared to the last epoch
        if len(self.validation_losses) > 1 and self.validation_losses[-1] > self.validation_losses[-2]:
            new_lr *= 0.5
        
        print(f"Epoch {epoch + 1}: Learning rate is {new_lr}, Validation Loss: {val_loss if val_loss is not None else 'N/A'}")
        return new_lr
    
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

        if hasattr(self, 'sliding_window') and self.sliding_window:

            logging.info("Model setup: Sliding window")

            input_ids = tf.keras.layers.Input(shape=(None, None,), ragged=True, dtype=tf.int32, name="input_ids")
            attention_mask = tf.keras.layers.Input(shape=(None, None,), ragged=True, dtype=tf.int32, name="attention_mask")
            
            embeddings_layer = EmbeddingsLayer(self.embeddings_model_name)
            # Set all layers of the embeddings model to non-trainable first
            for layer in embeddings_layer.embeddings_model.layers:
                layer.trainable = False

            # Set only the top few layers to trainable, for fine-tuning
            trainable_layers = embeddings_layer.embeddings_model.layers[-self.number_of_trainable_embeddings_model_layers:]
            for layer in trainable_layers:
                layer.trainable = True

            # Verify the trainability of each layer
            for i, layer in enumerate(embeddings_layer.embeddings_model.layers):
                logging.info(f"Layer {i} ({layer.name}) trainable: {layer.trainable}")

            # Create an instance of the custom layer
            ragged_embeddings_layer = RaggedEmbeddingsLayer(self.embeddings_model_name)

            # Pass the ragged tensors directly to the custom layer
            last_hidden_state = ragged_embeddings_layer([input_ids, attention_mask])
            logging.info(f"Shape of last_hidden_state: {last_hidden_state.shape}")

            # Use the TimeDistributed layer to apply the dense layer to each window embedding
            window_level_output = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(768, activation='relu'))(last_hidden_state)
            logging.info(f"Shape of window_level_output: {window_level_output.shape}")

            # Flatten the ragged dimensions
            # flat_output = tf.keras.layers.Lambda(lambda x: tf.reshape(x, [-1, 768]))(window_level_output)
            # logging.info(f"Shape of flat_output: {flat_output.shape}")

            # Aggregate the window-level representations based on the sliding_window_aggregation parameter
            if self.sliding_window_aggregation == 'attention':
                # Apply a Dense layer to compute attention scores over the last dimension of the ragged tensor
                attention_scores = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(1, activation='tanh'))(window_level_output)

                # Use a softmax layer to compute attention weights, handling the ragged tensor directly
                attention_weights = tf.keras.layers.TimeDistributed(tf.keras.layers.Softmax(axis=-1))(attention_scores)

                logging.info(f"Attention weights shape: {attention_weights.shape}")

                # Compute the weighted sum using the attention weights, this requires custom handling for ragged tensors
                # Multiply the weights by the original window_level_output and then sum over the appropriate axis
                aggregated_output = tf.reduce_sum(attention_weights * window_level_output, axis=-2)
            elif self.sliding_window_aggregation == 'max':
                aggregated_output = tf.keras.layers.GlobalMaxPooling1D()(window_level_output)
            else:
                aggregated_output = tf.keras.layers.GlobalAveragePooling1D()(window_level_output)

            # Define a custom reshaping function using Lambda layer
            reshape_func = tf.keras.layers.Lambda(lambda x: tf.reshape(x, (-1, tf.shape(x)[-1])))

            # Apply the custom reshaping function to the aggregated_output tensor
            aggregated_output = reshape_func(aggregated_output)

            # Log the intermediate representations
            logging.info(f"Embedding output shape: {last_hidden_state.shape}")
            logging.info(f"Window-level output shape: {window_level_output.shape}")
            logging.info(f"Aggregated output shape: {aggregated_output.shape}")

            tanh_output = tf.keras.layers.Dense(768, activation='tanh', name="tanh_amplifier")(aggregated_output)
            dropout = tf.keras.layers.Dropout(rate=self.dropout_rate, name="dropout")(tanh_output)
            logging.info(f"Shape of dropout: {dropout.shape}")

            # Add the final output layer
            if self.is_multi_class:
                num_labels = self.train_labels.shape[1]
                logging.info(f"Multi-class -- Number of labels: {num_labels}")
                out = tf.keras.layers.Dense(
                    num_labels,
                    activation='softmax',
                    kernel_regularizer=regularizers.l2(self.l2_regularization_strength),
                    name="softmax_multiclass_classifier"
                )(dropout)
            else:
                out = tf.keras.layers.Dense(
                    1,
                    activation='sigmoid',
                    kernel_regularizer=regularizers.l2(self.l2_regularization_strength),
                    name="sigmoid_binary_classifier"
                )(dropout)
            logging.info(f"Shape of final output: {out.shape}")

        else:

            input_ids = tf.keras.layers.Input(shape=(None,), dtype=tf.int32, name="input_ids")
            attention_mask = tf.keras.layers.Input(shape=(None,), dtype=tf.int32, name="attention_mask")

            embeddings_model = TFAutoModel.from_pretrained(self.embeddings_model_name)

            # Set all layers to non-trainable first
            for layer in embeddings_model.layers:
                layer.trainable = False

            # Set only the top few layers to trainable, for fine-tuning
            trainable_layers = embeddings_model.layers[-self.number_of_trainable_embeddings_model_layers:]
            for layer in trainable_layers:
                layer.trainable = True

            # Verify the trainability of each layer
            for i, layer in enumerate(embeddings_model.layers):
                print(f"Layer {i} ({layer.name}) trainable: {layer.trainable}")

            last_hidden_state = embeddings_model(input_ids, attention_mask=attention_mask)[0]
            pooled_output = tf.reduce_mean(last_hidden_state, axis=1)
            tanh_output = tf.keras.layers.Dense(768, activation='tanh', name="tanh_amplifier")(pooled_output)
            dropout = tf.keras.layers.Dropout(rate=self.dropout_rate, name="dropout")(tanh_output)

            # Add the final output layer
            if self.is_multi_class:
                num_labels = self.train_labels.shape[1]
                logging.info(f"Multi-class -- Number of labels: {num_labels}")
                out = tf.keras.layers.Dense(
                    num_labels,
                    activation='softmax',
                    kernel_regularizer=regularizers.l2(self.l2_regularization_strength),
                    name="softmax_multiclass_classifier"
                )(dropout)
            else:
                out = tf.keras.layers.Dense(
                    1,
                    activation='sigmoid',
                    kernel_regularizer=regularizers.l2(self.l2_regularization_strength),
                    name="sigmoid_binary_classifier"
                )(dropout)

        self.model = tf.keras.models.Model(inputs=[input_ids, attention_mask], outputs=out)

        # Monitor the gradients during training
        for layer in self.model.layers:
            if hasattr(layer, 'kernel'):
                layer.kernel.assign(tf.debugging.assert_all_finite(layer.kernel, message=f"Infinite or NaN values in {layer.name}.kernel"))
            if hasattr(layer, 'bias'):
                layer.bias.assign(tf.debugging.assert_all_finite(layer.bias, message=f"Infinite or NaN values in {layer.name}.bias"))

        # Compile the model with the appropriate loss function
        if self.is_multi_class:
            loss_function = 'categorical_crossentropy'
        else:
            loss_function = 'binary_crossentropy'

        self.model.compile(
            optimizer=Adam(learning_rate=self.plateau_learning_rate),
            loss=loss_function,
            metrics=['accuracy', Precision(name='precision'), Recall(name='recall'), AUC(name='auc')]
        )

        # During training, after the model is defined
        self.model.summary(print_fn=lambda x: logging.info(x))

        # logging.info("Before predicting")
        # logging.info(f"val_input_ids shape: {self.val_input_ids.shape}")
        # logging.info(f"val_attention_mask shape: {self.val_attention_mask.shape}")
        # val_predictions = self.model.predict([self.val_input_ids, self.val_attention_mask])
        # logging.info(f"val_predictions shape: {val_predictions.shape}")

        self._generate_model_diagram()

        #############
        # Training

        learning_rate_scheduler = tf.keras.callbacks.LearningRateScheduler(
            lambda epoch, lr: self.custom_lr_scheduler(epoch, lr)
        )

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
            epochs=self.epochs,
            batch_size=self.batch_size,
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

    def evaluate_model(self):
        """
        Evaluate the model on the validation data.

        :return: The evaluation results.
        """
        print("Generating evaluation metrics...")

        logging.info(f"val_labels shape: {self.val_labels.shape}")

        # Predict on validation set
        self.val_predictions = self.model.predict([self.val_input_ids, self.val_attention_mask])

        logging.info(f"val_predictions shape: {self.val_predictions.shape}")

        if self.is_multi_class:
            self.val_predictions_labels = np.argmax(self.val_predictions, axis=1)
            if len(self.val_labels.shape) > 1 and self.val_labels.shape[1] > 1:
                self.val_labels = np.argmax(self.val_labels, axis=1)  # Convert one-hot encoded labels to integer labels
        else:
            self.val_predictions_labels = [1 if pred > 0.5 else 0 for pred in self.val_predictions]

        # Compute evaluation metrics
        accuracy = accuracy_score(self.val_labels, self.val_predictions_labels)
        f1 = f1_score(self.val_labels, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')
        recall = recall_score(self.val_labels, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')
        precision = precision_score(self.val_labels, self.val_predictions_labels, average='weighted' if self.is_multi_class else 'binary')

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

    def save_model(self):
        """
        Save the model to the model registry.
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
        pass

    @Classifier.ensure_report_directory_exists
    def _generate_window_count_histogram(self, windows):
        """
        Generates a PNG artifact of a histogram showing the distribution of the lengths of the inner lists in the provided dataset.
        """
        directory_path = self._report_directory_path()
        file_name = os.path.join(directory_path, "window_count_histogram.png")

        # Calculate the lengths of the inner lists
        window_lengths = [len(window) for window in windows]

        # Plot the histogram
        plt.figure(figsize=(10, 6))
        plt.hist(window_lengths, bins=30, color=self._fuchsia, edgecolor='black')
        plt.xlabel('Number of Windows per Sample')
        plt.ylabel('Frequency')
        plt.title('Distribution of Window Counts per Sample')
        plt.gca().xaxis.set_major_locator(plt.MaxNLocator(integer=True))

        plt.savefig(file_name)
        plt.show()

        mlflow.log_artifact(file_name)
