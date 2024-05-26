import numpy as np
import pandas as pd
from tqdm import tqdm
import tensorflow as tf
import nltk
from sklearn.model_selection import train_test_split
from transformers import BertTokenizer, TFBertModel
from plexus.classifiers.MLClassifier import MLClassifier
from tensorflow.keras.utils import to_categorical

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
        print(f"Unique values in '{self.score_name}':", self.dataframe[self.score_name].unique())

        #############
        # Balance data

        # Check the distribution of labels
        print("\nDistribution of labels:")
        print(self.dataframe[self.score_name].value_counts(dropna=False))

        # Get the unique labels
        unique_labels = self.dataframe[self.score_name].unique()

        # Create a dictionary to store the dataframes for each label
        label_dataframes = {label: self.dataframe[self.dataframe[self.score_name] == label] for label in unique_labels}

        # Determine the smallest class size
        smallest_class_size = min(len(df) for df in label_dataframes.values())

        # Sample from each class to match the number of instances in the smallest class
        balanced_dataframes = []
        for label, dataframe in label_dataframes.items():
            print(f"Sampling {smallest_class_size} instances from the '{label}' class...")
            balanced_dataframes.append(dataframe.sample(n=smallest_class_size, random_state=42))

        # Concatenate the balanced dataframes
        df_balanced = pd.concat(balanced_dataframes)

        # Shuffle the data
        df_balanced = df_balanced.sample(frac=1, random_state=42)

        # Sample a certain percentage of the data
        df_balanced = df_balanced.sample(frac=self.data_percentage, random_state=42)

        # Check the distribution of labels
        print("\nDistribution of labels:")
        print(df_balanced[self.score_name].value_counts())

        # Now you can use df_balanced for the rest of your code
        texts = df_balanced['Transcription'].tolist()
        labels = df_balanced[self.score_name].tolist()

        #############
        # Tokenization

        tokenizer = BertTokenizer.from_pretrained(self.bert_model_name, do_lower_case=True)

        def split_into_sentences(text):
            return nltk.sent_tokenize(text)

        def encode_texts(tokenizer, texts, max_len):
            encoded_texts = []
            for text in tqdm(texts, desc="Encoding texts"):
                encoded_text = tokenizer.encode(text, padding='max_length', truncation=True, max_length=max_len, return_tensors='tf')
                encoded_texts.append(encoded_text)
            return tf.concat(encoded_texts, axis=0)

        # Split the data into training and validation sets
        train_texts, val_texts, train_labels, val_labels = train_test_split(texts, labels, test_size=0.2, random_state=42)

        # Encode the training and validation texts
        print("Training:")
        self.train_encoded_texts = encode_texts(tokenizer, train_texts, self.max_len)
        print("Validation:")
        self.val_encoded_texts = encode_texts(tokenizer, val_texts, self.max_len)

        # Extract input_ids
        self.train_input_ids = self.train_encoded_texts
        self.val_input_ids = self.val_encoded_texts

        # Create attention masks
        self.train_attention_mask = tf.where(self.train_input_ids != 0, 1, 0)
        self.val_attention_mask = tf.where(self.val_input_ids != 0, 1, 0)

        # Convert labels to integers
        self.label_map = {label: i for i, label in enumerate(unique_labels)}
        self.train_labels_int = np.array([self.label_map[label] for label in train_labels])
        self.val_labels_int = np.array([self.label_map[label] for label in val_labels])

        # Determine if it's a binary or multi-class classification task
        print(f"Is multi-class: {self.is_multi_class}")

        # One-hot encode the labels
        num_classes = len(unique_labels)
        self.train_labels = to_categorical(self.train_labels_int, num_classes=num_classes)
        self.val_labels = to_categorical(self.val_labels_int, num_classes=num_classes)

        # Check the distribution of labels in the training set
        print("Training set label breakdown:")
        train_label_counts = np.unique(np.argmax(self.train_labels, axis=1), return_counts=True)
        print(dict(zip(unique_labels, train_label_counts[1])))

        # Check the distribution of labels in the validation set
        print("Validation set label breakdown:")
        val_label_counts = np.unique(np.argmax(self.val_labels, axis=1), return_counts=True)
        print(dict(zip(unique_labels, val_label_counts[1])))
