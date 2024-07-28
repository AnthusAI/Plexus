import os
import mlflow
from plexus.scores import Score
from pydantic import BaseModel, validator, ValidationError
import numpy as np
import pandas as pd
import nltk
from nltk.tokenize import PunktSentenceTokenizer
import tensorflow as tf
from transformers import AutoTokenizer, TFAutoModel
from sklearn.model_selection import train_test_split
from collections import Counter
from rich.table import Table
from rich.progress import Progress
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from plexus.CustomLogging import logging, console
from plexus.scores.core.utils import ensure_report_directory_exists
import matplotlib.pyplot as plt
import traceback

class DeepLearningSemanticClassifier(Score):
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

    class Parameters(Score.Parameters):
        ...
        embeddings_model: str
        embeddings_model_trainable_layers: int = 3
        maximum_tokens_per_window: int = 512
        multiple_windows: bool = False
        maximum_windows: int = 0
        start_from_end: bool = False
        number_of_epochs: int
        batch_size: int
        warmup_learning_rate: float
        number_of_warmup_epochs: int
        plateau_learning_rate: float
        number_of_plateau_epochs: int
        learning_rate_decay: float
        early_stop_patience: int
        l2_regularization_strength: float
        dropout_rate: float

    def __new__(cls, *args, **parameters):
        if cls is DeepLearningSemanticClassifier:
            from plexus.scores.DeepLearningSlidingWindowSemanticClassifier import DeepLearningSlidingWindowSemanticClassifier
            
            # Validate parameters
            try:
                validated_parameters = cls.Parameters(**parameters).dict()
            except ValidationError as e:
                Score.log_validation_errors(e)
                raise

            logging.info(f"Sliding window: {validated_parameters.get('multiple_windows', False)}")
            if validated_parameters.get('multiple_windows', False):
                logging.info("Using sliding window embeddings")
                from plexus.scores.DeepLearningSlidingWindowSemanticClassifier import DeepLearningSlidingWindowSemanticClassifier
                return DeepLearningSlidingWindowSemanticClassifier(*args, **validated_parameters)
            else:
                logging.info("Using one-step embeddings")
                from plexus.scores.DeepLearningOneStepSemanticClassifier import DeepLearningOneStepSemanticClassifier
                return DeepLearningOneStepSemanticClassifier(*args, **validated_parameters)
        else:
            return super(DeepLearningSemanticClassifier, cls).__new__(cls)

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.tokenizer = AutoTokenizer.from_pretrained(self.parameters.embeddings_model)

    class Parameters(Parameters):
        ...

    def encode_input(self, texts):
        def encode_single_text(text, maximum_length):
            return self.tokenizer.encode(text, padding='max_length', truncation=True, max_length=maximum_length, return_tensors='tf')

        def encode_texts_parallel(texts, maximum_length):
            encoded_texts = []
            with ThreadPoolExecutor() as executor:
                with Progress() as progress:
                    task = progress.add_task("Encoding texts...", total=len(texts))
                    futures = [executor.submit(encode_single_text, text, maximum_length) for text in texts]
                    for future in futures:
                        encoded_texts.append(future.result())
                        progress.advance(task)
            return tf.concat(encoded_texts, axis=0)

        encoded_texts = encode_texts_parallel(texts, self.parameters.maximum_tokens_per_window)
        attention_masks = tf.where(encoded_texts != 0, 1, 0)
 
        return {
            'input_ids': encoded_texts,
            'attention_mask': attention_masks
        }

    class EmbeddingsLayer(tf.keras.layers.Layer):
        def __init__(self, embeddings_model, **kwargs):
            super(DeepLearningSemanticClassifier.EmbeddingsLayer, self).__init__(**kwargs)
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
            # Download the punkt tokenizer if not already available
            try:
                nltk.data.find('tokenizers/punkt')
            except LookupError:
                nltk.download('punkt')

            # Create a PunktSentenceTokenizer instance
            tokenizer = PunktSentenceTokenizer()

            # Tokenize the text into sentences
            sentences = tokenizer.tokenize(text)

            # Post-process sentences (remove empty ones and strip whitespace)
            processed_sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

            return processed_sentences

        def tokenize_sentence(tokenizer, sentence):
            return tokenizer.tokenize(sentence)

        def build_multiple_windows(tokenizer, text, max_tokens_per_window, max_windows, start_from_end=False):
            """
            This function breaks long texts into smaller windows of text, where each sentence is
            entirely within one window, without being broken apart.
            The token count of the sentence is what determines if it fits into the window, because
            the maximum size of the windows is specified in a token count.

            Args:
            tokenizer: The tokenizer to use for tokenizing words.
            text: The input text to be split into windows.
            max_tokens_per_window: Maximum number of tokens allowed per window.
            max_windows: Maximum number of windows to create (0 for no limit).
            reverse: If True, build windows from the end of the text.

            Returns:
            windows: List of windows, where each window is a list of sentences.
            windows_tokens: List of tokenized windows.
            """
            windows = []
            windows_tokens = []
            current_window = []
            current_window_tokens = []

            # Use the split_into_sentences function
            sentences = split_into_sentences(text)

            if start_from_end:
                sentences = sentences[::-1]
            
            for i, sentence in enumerate(sentences):
                sentence_tokens = tokenizer.tokenize(sentence)
                if len(current_window_tokens) + len(sentence_tokens) <= max_tokens_per_window:
                    if start_from_end:
                        current_window.insert(0, sentence)
                        current_window_tokens = sentence_tokens + current_window_tokens
                    else:
                        current_window.append(sentence)
                        current_window_tokens.extend(sentence_tokens)
                else:
                    if current_window:
                        windows.append(current_window)
                        windows_tokens.append(current_window_tokens)
                    current_window = [sentence]
                    current_window_tokens = sentence_tokens

                # Truncate to the maximum number of windows, but only if that is specified.
                if max_windows and len(windows) >= max_windows:
                    break

            if current_window:
                should_we_keep_this_window = max_windows == 0 or len(windows) < max_windows
                if should_we_keep_this_window:
                    windows.append(current_window)
                    windows_tokens.append(current_window_tokens)

            if start_from_end:
                windows = windows[::-1]
                windows_tokens = windows_tokens[::-1]

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

        texts = self.dataframe['text'].tolist()
        labels = self.dataframe[self.parameters.score_name].tolist()
        unique_labels = self.dataframe[self.parameters.score_name].unique()

        # Split the data into training and validation sets
        train_texts, val_texts, train_labels, val_labels = train_test_split(texts, labels, test_size=0.2, random_state=42)

        logging.info(f"Unique labels: {unique_labels}")
        logging.info(f"Number of unique labels: {len(unique_labels)}")
        logging.info(f"Is multi-class: {self.is_multi_class}")
    
        logging.info(f"Original shape of train_texts: {np.shape(train_texts)}")
        logging.info(f"Original shape of val_texts: {np.shape(val_texts)}")
        logging.info(f"Original shape of train_labels: {np.shape(train_labels)}")
        logging.info(f"Original shape of val_labels: {np.shape(val_labels)}")

        # Handle nan values in labels
        train_labels = [str(label) if pd.notna(label) else 'Unknown' for label in train_labels]
        val_labels = [str(label) if pd.notna(label) else 'Unknown' for label in val_labels]

        # Create label_map and inverse_label_map
        unique_labels = sorted(set(train_labels + val_labels))
        self.label_map = {label: i for i, label in enumerate(unique_labels)}
        self.inverse_label_map = {i: label for label, i in self.label_map.items()}

        # Convert labels to integers
        train_labels_int = np.array([self.label_map[label] for label in train_labels])
        val_labels_int = np.array([self.label_map[label] for label in val_labels])

        logging.info(f"Label map: {self.label_map}")
        logging.info(f"Inverse label map: {self.inverse_label_map}")

        # Store both integer and string versions of labels
        self.train_labels = train_labels_int
        self.val_labels = val_labels_int
        self.train_labels_str = np.array(train_labels)
        self.val_labels_str = np.array(val_labels)

        logging.info(f"train_labels type: {type(self.train_labels)}, shape: {self.train_labels.shape}")
        logging.info(f"val_labels type: {type(self.val_labels)}, shape: {self.val_labels.shape}")
        logging.info(f"train_labels_str type: {type(self.train_labels_str)}, shape: {self.train_labels_str.shape}")
        logging.info(f"val_labels_str type: {type(self.val_labels_str)}, shape: {self.val_labels_str.shape}")

        # Use the existing is_multi_class property
        logging.info(f"Is multi-class classification: {self.is_multi_class}")

        # One-hot encode the labels only for multi-class problems
        number_of_labels = len(self.label_map)
        if self.is_multi_class:
            self.train_labels = tf.one_hot(self.train_labels, depth=number_of_labels)
            self.val_labels = tf.one_hot(self.val_labels, depth=number_of_labels)
            logging.info("Labels one-hot encoded for multi-class classification.")
        else:
            # For binary classification, ensure labels are in the correct shape
            self.train_labels = tf.reshape(self.train_labels, (-1, 1))
            self.val_labels = tf.reshape(self.val_labels, (-1, 1))
            logging.info("Labels reshaped for binary classification.")

        logging.info(f"Final train_labels shape: {self.train_labels.shape}")
        logging.info(f"Final val_labels shape: {self.val_labels.shape}")

        # Build sliding windows for training and validation texts
        train_windows, train_windows_tokens = zip(*[
            build_multiple_windows(
                tokenizer=tokenizer, 
                text=text, 
                max_tokens_per_window=self.parameters.maximum_tokens_per_window, 
                max_windows=self.parameters.maximum_windows,
                start_from_end=self.parameters.start_from_end
            ) for text in tqdm(train_texts, desc="Building train sliding windows")
        ])
        
        val_windows, val_windows_tokens = zip(*[
            build_multiple_windows(
                tokenizer=tokenizer, 
                text=text, 
                max_tokens_per_window=self.parameters.maximum_tokens_per_window, 
                max_windows=self.parameters.maximum_windows,
                start_from_end=self.parameters.start_from_end
            ) for text in tqdm(val_texts, desc="Building validation sliding windows")
        ])
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
        logging.info(f"train_attention_mask type: {type(train_attention_mask)}, shape: {train_attention_mask.shape}")
        logging.info(f"train_labels type: {type(self.train_labels)}, shape: {self.train_labels.shape}")

        logging.info(f"val_input_ids type: {type(val_input_ids)}, shape: {val_input_ids.shape}")
        logging.info(f"val_attention_mask type: {type(val_attention_mask)}, shape: {val_attention_mask.shape}")
        logging.info(f"val_labels type: {type(self.val_labels)}, shape: {self.val_labels.shape}")

        # Check the distribution of labels in the training set for the sliding window scenario
        print("Training set label breakdown (sliding window):")
        train_label_counts = np.unique(self.train_labels_str, return_counts=True)
        print(dict(zip(train_label_counts[0], train_label_counts[1])))

        # Check the distribution of labels in the validation set for the sliding window scenario
        print("Validation set label breakdown (sliding window):")
        val_label_counts = np.unique(self.val_labels_str, return_counts=True)
        print(dict(zip(val_label_counts[0], val_label_counts[1])))

        logging.info(f"train_input_ids type: {type(train_input_ids)}, shape: {train_input_ids.shape}")
        logging.info(f"train_attention_mask type: {type(train_attention_mask)}, shape: {train_attention_mask.shape}")

        # Remember the important stuff for later.
        self.train_input_ids = train_input_ids
        self.val_input_ids = val_input_ids
        self.train_attention_mask = train_attention_mask
        self.val_attention_mask = val_attention_mask
        self.train_texts = train_texts
        self.val_texts = val_texts

    def custom_lr_scheduler(self, epoch, lr):
        # Record validation loss if available
        if hasattr(self, 'model') and hasattr(self.model, 'history') and 'val_loss' in self.model.history.history:
            val_loss = self.model.history.history['val_loss'][-1]
            self.validation_losses.append(val_loss)
        else:
            val_loss = None
        
        if epoch < self.parameters.number_of_warmup_epochs:
            # Linear warmup
            progress = epoch / self.parameters.number_of_warmup_epochs
            new_lr = self.parameters.warmup_learning_rate + progress * (self.parameters.plateau_learning_rate - self.parameters.warmup_learning_rate)
        elif epoch < self.parameters.number_of_warmup_epochs + self.parameters.number_of_plateau_epochs:
            # Plateau
            new_lr = self.parameters.plateau_learning_rate
        else:
            # Decay
            decay_steps = epoch - (self.parameters.number_of_warmup_epochs + self.parameters.number_of_plateau_epochs)
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

    class Result(Score.Result):
        """
        This Score has an additional output attribute, confidence, which is a float
        """
        confidence: float

    def predict(self, context, model_input: Score.Input):
        logging.info(f"Received input: {model_input}")

        text = model_input.text
        logging.info(f"Processing text (first 100 chars): {text[:100]}...")

        try:
            encoded_input = self.encode_input([text])
            logging.info(f"Encoded input shapes: input_ids={encoded_input['input_ids'].shape}, attention_mask={encoded_input['attention_mask'].shape}")

            predictions = self.model.predict([encoded_input['input_ids'], encoded_input['attention_mask']])
            logging.info(f"Raw prediction shape: {predictions.shape}")
            logging.info(f"Raw predictions: {predictions}")
            logging.info(f"Prediction type: {type(predictions)}")
            logging.info(f"Prediction dtype: {predictions.dtype}")

            if self.is_multi_class:
                logging.info("Handling multi-class prediction")
                confidence_score = float(np.max(predictions[0]))
                predicted_class = int(np.argmax(predictions[0]))
            else:
                logging.info("Handling binary prediction")
                confidence_score = float(predictions[0][0])
                predicted_class = int(predictions[0][0] > 0.5)

            logging.info(f"Predicted class (before conversion): {predicted_class}")
            logging.info(f"Confidence score: {confidence_score}")

            predicted_label = self.inverse_label_map[predicted_class]
            logging.info(f"Predicted label: {predicted_label}")

            return self.Result(
                name =       self.parameters.score_name,
                value =      predicted_label,
                confidence = confidence_score
            )
        except Exception as e:
            logging.error(f"Error during prediction: {str(e)}")
            logging.error(f"Error type: {type(e)}")
            logging.error(f"Traceback: {traceback.format_exc()}")
            raise

    def predict_validation(self):
        logging.info("Starting predict_validation")
        self.val_predictions = []
        self.val_confidence_scores = []

        for i, text in enumerate(self.val_texts):
            logging.info(f"Processing validation sample {i+1}/{len(self.val_texts)}")
            
            model_input = self.Input(text=text)
            result = self.predict(None, model_input)
            
            self.val_predictions.append(result.score)
            self.val_confidence_scores.append(result.confidence)

        self.val_predictions = np.array(self.val_predictions)
        self.val_confidence_scores = np.array(self.val_confidence_scores)

        # Convert predictions and labels to string format
        self.val_predictions = np.array([str(pred) for pred in self.val_predictions])
        self.val_labels = np.array([str(label) for label in self.val_labels_str])

        logging.info(f"Completed predict_validation. Predictions shape: {self.val_predictions.shape}, Confidence scores shape: {self.val_confidence_scores.shape}")
        logging.info(f"val_predictions type: {type(self.val_predictions)}, shape: {self.val_predictions.shape}, sample: {self.val_predictions[:5]}")
        logging.info(f"val_labels type: {type(self.val_labels)}, shape: {self.val_labels.shape}, sample: {self.val_labels[:5]}")
        
    @ensure_report_directory_exists
    def _generate_window_count_histogram(self, windows):
        """
        Generates a PNG artifact of a histogram showing the distribution of the lengths of the inner lists in the provided dataset.
        """
        directory_path = self.report_directory_path()
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
