import numpy as np
import pandas as pd
from tqdm import tqdm
import tensorflow as tf
import nltk
from sklearn.model_selection import train_test_split
from transformers import BertTokenizer, TFBertModel
from plexus.classifiers.MLClassifier import MLClassifier

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

        # Separate 'Yes' and 'No' instances
        df_yes = self.dataframe[self.dataframe[self.score_name] == 'Yes']
        df_no = self.dataframe[self.dataframe[self.score_name] == 'No']

        # Determine the smaller class size
        smaller_class_size = min(len(df_yes), len(df_no))

        # Sample from the larger class to match the number of instances in the smaller class
        if len(df_yes) > len(df_no):
            print(f"Sampling {smaller_class_size} instances from the 'Yes' class...")
            df_yes = df_yes.sample(n=smaller_class_size, random_state=42)
        else:
            print(f"Sampling {smaller_class_size} instances from the 'No' class...")
            df_no = df_no.sample(n=smaller_class_size, random_state=42)

        # Concatenate 'Yes' and 'No' instances
        df_balanced = pd.concat([df_yes, df_no])

        # Shuffle the data
        df_balanced = df_balanced.sample(frac=1, random_state=42)

        # Sample a certain percentage of the data
        df_balanced = df_balanced.sample(frac=self.data_percentage, random_state=42)

        # Check the distribution of labels
        print("\nDistribution of labels:")
        print(df_balanced[self.score_name].value_counts())

        # Now you can use df_balanced for the rest of your code
        texts = df_balanced['Transcription'].tolist()
        labels = df_balanced[self.score_name].apply(lambda x: 1 if x == 'Yes' else 0).tolist()

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

        # Convert labels to numpy arrays
        self.train_labels = np.array(train_labels)
        self.val_labels = np.array(val_labels)

        # Check the distribution of labels in the training set
        print("Training set label breakdown:")
        print(np.bincount(self.train_labels))

        # Check the distribution of labels in the validation set
        print("Validation set label breakdown:")
        print(np.bincount(self.val_labels))