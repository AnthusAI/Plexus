import os
import mlflow
from plexus.classifiers import Score, MLClassifier
from pydantic import BaseModel, validator, ValidationError
import numpy as np
import pandas as pd
import nltk
import tensorflow as tf
from transformers import AutoTokenizer, TFAutoModel
from sklearn.model_selection import train_test_split
from collections import Counter
from rich.progress import Progress
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from plexus.CustomLogging import logging, console
import matplotlib.pyplot as plt

class DeepLearningEmbeddingsClassifier(MLClassifier):
    """
    A text classifier that uses HuggingFace transformer embeddings from language models like BERT.
    The model attaches a classification head to the embedding model.
    It includes a sliding-windows feature for breaking down long texts into smaller windows of text,
    where each sentence is entirely within one window, without being broken apart.
    The embeddings from each of the windows are aggregated into a single embedding for the entire text,
    that goes into the classification head to produce a prediction.
    The aggregation architecture consumes extra memory, and so the sliding-windows feature works better
    with smaller models, like DistilBERT.
    """

    class Parameters(MLClassifier.Parameters):
        ...
        embeddings_model: str
        embeddings_model_trainable_layers: int = 3
        maximum_tokens_per_window: int = 512
        multiple_windows: bool = False
        maximum_windows: int = 0
        number_of_epochs: int
        batch_size: int
        warmup_learning_rate: float
        warmup_epochs: int
        plateau_learning_rate: float
        number_of_plateau_epochs: int
        learning_rate_decay: float
        early_stop_patience: int
        l2_regularization_strength: float
        dropout_rate: float

    def __new__(cls, *args, **parameters):
        if cls is DeepLearningEmbeddingsClassifier:
            from plexus.classifiers.DeepLearningSlidingWindowEmbeddingsClassifier import DeepLearningSlidingWindowEmbeddingsClassifier
            
            # Validate parameters
            try:
                validated_parameters = cls.Parameters(**parameters).dict()
            except ValidationError as e:
                Classifier.log_validation_errors(e)
                raise

            logging.info(f"Sliding window: {validated_parameters.get('multiple_windows', False)}")
            if validated_parameters.get('multiple_windows', False):
                logging.info("Using sliding window embeddings")
                from plexus.classifiers.DeepLearningSlidingWindowEmbeddingsClassifier import DeepLearningSlidingWindowEmbeddingsClassifier
                return DeepLearningSlidingWindowEmbeddingsClassifier(*args, **validated_parameters)
            else:
                logging.info("Using one-step embeddings")
                from plexus.classifiers.DeepLearningOneStepEmbeddingsClassifier import DeepLearningOneStepEmbeddingsClassifier
                return DeepLearningOneStepEmbeddingsClassifier(*args, **validated_parameters)
        else:
            return super(DeepLearningEmbeddingsClassifier, cls).__new__(cls)

    class Parameters(Parameters):
        ...

    class EmbeddingsLayer(tf.keras.layers.Layer):
        def __init__(self, embeddings_model, **kwargs):
            super(DeepLearningEmbeddingsClassifier.EmbeddingsLayer, self).__init__(**kwargs)
            self.embeddings_model = embeddings_model

        def call(self, inputs):
            input_ids, attention_mask = inputs
            if isinstance(input_ids, tf.RaggedTensor):
                input_ids = input_ids.to_tensor(default_value=0)
            if isinstance(attention_mask, tf.RaggedTensor):
                attention_mask = attention_mask.to_tensor(default_value=0)
            
            logging.info(f"Input IDs shape: {input_ids.shape}")
            logging.info(f"Attention Mask shape: {attention_mask.shape}")

            outputs = self.embeddings_model(input_ids, attention_mask=attention_mask)
            last_hidden_state = outputs[0]
            return last_hidden_state

    def process_data(self):
        """
        This function breaks the input text apart into windows of text if the sliding-windows feature is enabled,
        or it will naively truncate the input text to a single window if the sliding-windows feature is disabled.
        It will then encode the text and compute the vector embeddings.
        The dimensionality of the training and validation data will differ, depending on the sliding-windows feature.
        With sliding windows, the training and validation data will be 3D tensors.
        With naive truncation, the training and validation data will be 2D tensors.
        """

        # Call the parent process_data method first, which will iterate over any processor classes
        # configured in the scorecard YAML file.
        super().process_data()

        #############
        # Tokenization

        tokenizer = AutoTokenizer.from_pretrained(self.parameters.embeddings_model, do_lower_case=True)

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

        def build_multiple_windowss(tokenizer, text, max_tokens_per_window, max_windows):
            """
            This function breaks long texts into smaller windows of text, where each sentence is
            entirely within one window, without being broken apart.
            The token count of the sentence is what determines if it fits into the window, because
            the maximum size of the windows is specified in a token count.  Because the goal is
            for the window to be small enough for the BERT model, or something like it, to process
            the window in one step.  BERT models typically have a maximum input length of 512
            tokens, so our windows need to fit within that, which we specify with the
            `self.parameters.maximum_tokens_per_window` parameter.
            """
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

                # Truncate to the maximum number of windows, but only if that is specified.
                if max_windows is not None and len(windows) >= max_windows:
                    break

            if current_window:
                should_we_keep_this_window = True
                if max_windows is not None:
                    should_we_keep_this_window = len(windows) < max_windows
                if should_we_keep_this_window:
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
        labels = self.dataframe[self.parameters.score_name].tolist()
        unique_labels = self.dataframe[self.parameters.score_name].unique()

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

        # Build sliding windows for training and validation texts
        train_windows, train_windows_tokens = zip(*[build_multiple_windowss(tokenizer, text, self.parameters.maximum_tokens_per_window, getattr(self, 'maximum_windows', None)) for text in tqdm(train_texts, desc="Building train sliding windows")])
        val_windows, val_windows_tokens = zip(*[build_multiple_windowss(tokenizer, text, self.parameters.maximum_tokens_per_window, getattr(self, 'maximum_windows', None)) for text in tqdm(val_texts, desc="Building validation sliding windows")])
        if self.parameters.maximum_windows != 0:
            # Limit the number of windows for each text
            train_windows = [windows[:self.parameters.maximum_windows] for windows in train_windows]
            val_windows = [windows[:self.parameters.maximum_windows] for windows in val_windows]

        # Log the lengths of the windows
        logging.info(f"Number of train_windows after building: {len(train_windows)}")
        logging.info(f"Number of val_windows after building: {len(val_windows)}")
        
        def generate_ascii_histogram(counter, bar_char='#', max_width=50):
            max_count = max(counter.values())
            scale = max_width / max_count
            histogram_lines = []
            for length, count in sorted(counter.items()):
                bar = bar_char * int(count * scale)
                histogram_lines.append(f"{length:>3}: {bar} ({count})")
            return "\n".join(histogram_lines)

        train_window_lengths = [len(w) for w in train_windows]
        val_window_lengths = [len(w) for w in val_windows]

        train_window_histogram = Counter(train_window_lengths)
        val_window_histogram = Counter(val_window_lengths)

        train_histogram_ascii = generate_ascii_histogram(train_window_histogram)
        val_histogram_ascii = generate_ascii_histogram(val_window_histogram)

        logging.info(f"Histogram of train_window lengths:\n{train_histogram_ascii}")
        logging.info(f"Histogram of val_window lengths:\n{val_histogram_ascii}")

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
        train_encoded_windows, train_attention_masks = encode_windows_parallel(tokenizer, train_windows, self.parameters.maximum_tokens_per_window)
        val_encoded_windows, val_attention_masks = encode_windows_parallel(tokenizer, val_windows, self.parameters.maximum_tokens_per_window)

        # Log the shapes of the encoded windows
        logging.info(f"Shape of train_encoded_windows after encoding: {train_encoded_windows.shape}")
        logging.info(f"Shape of val_encoded_windows after encoding: {val_encoded_windows.shape}")

        train_input_ids = tf.ragged.constant([tf.concat(window, axis=0).numpy() for window in tqdm(train_encoded_windows, desc="Processing train windows")], dtype=tf.int32)
        val_input_ids = tf.ragged.constant([tf.concat(window, axis=0).numpy() for window in tqdm(val_encoded_windows, desc="Processing validation windows")], dtype=tf.int32)
        train_attention_mask = tf.ragged.constant([tf.concat(mask, axis=0).numpy() for mask in tqdm(train_attention_masks, desc="Processing train attention masks")], dtype=tf.int32)
        val_attention_mask = tf.ragged.constant([tf.concat(mask, axis=0).numpy() for mask in tqdm(val_attention_masks, desc="Processing validation attention masks")], dtype=tf.int32)

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

        # unique_labels, label_counts = np.unique(train_labels, return_counts=True)
        # logging.info(f"Unique labels before one-hot encoding: {unique_labels}")
        # logging.info(f"Label counts before one-hot encoding: {label_counts}")

        # One-hot encode the labels only if it's a multi-class classification
        number_of_labels = len(unique_labels)
        if self.is_multi_class:
            train_labels = tf.ragged.map_flat_values(tf.one_hot, train_labels, depth=number_of_labels)
            val_labels = tf.ragged.map_flat_values(tf.one_hot, val_labels, depth=number_of_labels)
        else:
            train_labels = train_labels.reshape(-1, 1)
            val_labels = val_labels.reshape(-1, 1)

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
        
        if epoch < self.parameters.warmup_epochs:
            # Linear warmup
            progress = epoch / self.parameters.warmup_epochs
            new_lr = self.parameters.warmup_learning_rate + progress * (self.parameters.plateau_learning_rate - self.parameters.warmup_learning_rate)
        elif epoch < self.parameters.warmup_epochs + self.parameters.number_of_plateau_epochs:
            # Plateau
            new_lr = self.parameters.plateau_learning_rate
        else:
            # Decay
            decay_steps = epoch - (self.parameters.warmup_epochs + self.parameters.number_of_plateau_epochs)
            new_lr = self.parameters.plateau_learning_rate * (self.parameters.learning_rate_decay ** decay_steps)
        
        # Reduce learning rate if validation loss increased compared to the last epoch
        if len(self.validation_losses) > 1 and self.validation_losses[-1] > self.validation_losses[-2]:
            new_lr *= 0.5
        
        print(f"Epoch {epoch + 1}: Learning rate is {new_lr}, Validation Loss: {val_loss if val_loss is not None else 'N/A'}")
        return new_lr

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

    @Score.ensure_report_directory_exists
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
