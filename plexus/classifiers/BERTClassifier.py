import numpy as np
import pandas as pd
from tqdm import tqdm
import tensorflow as tf
import nltk
from sklearn.model_selection import train_test_split
from transformers import BertTokenizer, TFBertModel
from plexus.classifiers.MLClassifier import MLClassifier
from tensorflow.keras.utils import to_categorical
from plexus.logging import console, logging
from rich import print
from rich.console import Console
from rich.table import Table
import random

class BERTClassifier(MLClassifier):
    """
    This is a base class for classifiers based on BERT embeddings that must pre-propcess data in the same way by tokenizing it with the BERT model.
    """

    def process_data(self):
        """
        Handle any pre-processing of the training data, including the training/validation splits.
        """

        # Call the parent process_data method first, which will iterate over any processor classes
        # configured in the scorecard YAML file.
        super().process_data()

        # Check for missing or unexpected values
        logging.info(f"Unique values in '{self.score_name}': {self.dataframe[self.score_name].unique()}")

        #############
        # Balance data

        # Check the distribution of labels
        logging.info("\nDistribution of labels:")
        logging.info(self.dataframe[self.score_name].value_counts(dropna=False))

        # Get the unique labels
        unique_labels = self.dataframe[self.score_name].unique()

        # Create a dictionary to store the dataframes for each label
        label_dataframes = {label: self.dataframe[self.dataframe[self.score_name] == label] for label in unique_labels}

        # Determine the smallest class size
        smallest_class_size = min(len(df) for df in label_dataframes.values())

        # Sample from each class to match the number of instances in the smallest class
        balanced_dataframes = []
        for label, dataframe in label_dataframes.items():
            logging.info(f"Sampling {smallest_class_size} instances from the '{label}' class...")
            balanced_dataframes.append(dataframe.sample(n=smallest_class_size, random_state=42))

        logging.info(f"Balanced dataframes: {balanced_dataframes}")

        # Concatenate the balanced dataframes
        df_balanced = pd.concat(balanced_dataframes)

        # Shuffle the data
        df_balanced = df_balanced.sample(frac=1, random_state=42)

        # Sample a certain percentage of the data
        df_balanced = df_balanced.sample(frac=self.data_percentage, random_state=42)

        # Check the distribution of labels
        logging.info("\nDistribution of labels:")
        logging.info(df_balanced[self.score_name].value_counts())

        # Now you can use df_balanced for the rest of your code
        texts = df_balanced['Transcription'].tolist()
        labels = df_balanced[self.score_name].tolist()

        #############
        # Tokenization

        tokenizer = BertTokenizer.from_pretrained(self.bert_model_name, do_lower_case=True)

        def split_into_sentences(text):
            return nltk.sent_tokenize(text)

        def encode_texts(tokenizer, texts, labels, max_tokens_per_window):
            all_encoded_texts = []
            all_encoded_labels = []

            random_index = random.randint(0, len(texts) - 1)
            random_text = texts[random_index]
            random_label = labels[random_index]
            random_text_windows = []

            logging.info(f"[bold]Random Transcript:[/bold] {random_text}")
            logging.info(f"[bold]Label:[/bold] {random_label}")

            for text, label in tqdm(zip(texts, labels), desc="Encoding texts"):
                sentences = split_into_sentences(text)
                current_windows = []
                current_length = 0
                current_window = []
                current_sentences = []

                for sentence in sentences:
                    if text == random_text:
                        logging.info(f"[bold]Encoding sentence:[/bold] {sentence}")
                    encoded_sentence = tokenizer.encode(sentence, add_special_tokens=False)
                    if current_length + len(encoded_sentence) > max_tokens_per_window:
                        if current_window:
                            current_windows.append(current_window)
                            if text == random_text:
                                logging.info("Creating new window.")
                                random_text_windows.append(current_sentences)
                                logging.info(f"[bold]Window Sentences:[/bold] {current_sentences}")
                                logging.info(f"[bold]Window Tokens:[/bold] {current_window}")
                        current_window = encoded_sentence
                        current_length = len(encoded_sentence)
                        current_sentences = [sentence]
                    else:
                        current_window.extend(encoded_sentence)
                        current_length += len(encoded_sentence)
                        current_sentences.append(sentence)

                if current_window:
                    current_windows.append(current_window)
                    if text == random_text:
                        logging.info("Logging last window.")
                        random_text_windows.append(current_sentences)
                        logging.info(f"[bold]Window Sentences:[/bold] {current_sentences}")
                        logging.info(f"[bold]Window Tokens:[/bold] {current_window}")

                if text == random_text:
                    logging.info(f"[bold]Windows of original random text:[/bold] {random_text_windows}")

                # Pad windows to the maximum length
                current_windows = tf.keras.preprocessing.sequence.pad_sequences(current_windows, maxlen=max_tokens_per_window, padding='post')
                all_encoded_texts.append(current_windows)
                all_encoded_labels.append(label)

            # logging.info(f"Encoded texts content: {all_encoded_texts}")
            # logging.info(f"Encoded labels content: {all_encoded_labels}")

            return all_encoded_texts, all_encoded_labels

        # Split the data into training and validation sets
        train_texts, val_texts, train_labels, val_labels = train_test_split(texts, labels, test_size=0.2, random_state=42)

        # Encode the training and validation texts
        logging.info("Training:")
        train_encoded_texts, train_labels = encode_texts(tokenizer, train_texts, train_labels, self.window_size)
        logging.info("Validation:")
        val_encoded_texts, val_labels = encode_texts(tokenizer, val_texts, val_labels, self.window_size)

        # Convert lists to arrays
        self.train_input_ids = np.array([np.array(text_windows) for text_windows in train_encoded_texts], dtype=object)
        self.train_labels_int = np.array(train_labels)
        self.val_input_ids = np.array([np.array(text_windows) for text_windows in val_encoded_texts], dtype=object)
        self.val_labels_int = np.array(val_labels)

        # Create attention masks
        self.train_attention_mask = np.array([[np.where(window != 0, 1, 0) for window in text_windows] for text_windows in self.train_input_ids], dtype=object)
        self.val_attention_mask = np.array([[np.where(window != 0, 1, 0) for window in text_windows] for text_windows in self.val_input_ids], dtype=object)

        # Convert labels to integers
        self.label_map = {label: i for i, label in enumerate(unique_labels)}
        self.train_labels_int = np.array([self.label_map[label] for label in self.train_labels_int])
        self.val_labels_int = np.array([self.label_map[label] for label in self.val_labels_int])

        logging.info("\nLabel mapping:")
        for label, index in self.label_map.items():
            logging.info(f"{label}: {index}")

        logging.info("\nSample of encoded training data:")
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Index", style="dim", width=6)
        table.add_column("Input IDs", min_width=20)
        table.add_column("Attention Mask", min_width=20)
        table.add_column("Label", min_width=12)

        for i in range(min(5, len(self.train_input_ids))):
            table.add_row(
                str(i),
                str(self.train_input_ids[i]),
                str(self.train_attention_mask[i]),
                str(self.train_labels_int[i])
            )
        console.print(table)

        # Determine if it's a binary or multi-class classification task
        logging.info(f"Is multi-class: {self.is_multi_class}")

        # One-hot encode the labels
        num_classes = len(unique_labels)
        self.train_labels = to_categorical(self.train_labels_int, num_classes=num_classes)
        self.val_labels = to_categorical(self.val_labels_int, num_classes=num_classes)

        # Check the distribution of labels in the training set
        logging.info("Training set label breakdown:")
        train_label_counts = np.unique(np.argmax(self.train_labels, axis=1), return_counts=True)
        logging.info(dict(zip(unique_labels, train_label_counts[1])))

        # Check the distribution of labels in the validation set
        logging.info("Validation set label breakdown:")
        val_label_counts = np.unique(np.argmax(self.val_labels, axis=1), return_counts=True)
        logging.info(dict(zip(unique_labels, val_label_counts[1])))