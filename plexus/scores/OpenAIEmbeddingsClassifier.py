import numpy as np
import os
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder
from plexus.scores import Score
from openai import OpenAI
from tqdm import tqdm
import logging
import pandas as pd

class OpenAIEmbeddingsClassifier(Score):
    class Parameters(Score.Parameters):
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

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.model = LogisticRegression(
            C=1/self.parameters.l2_regularization_strength,
            max_iter=self.parameters.number_of_epochs * 100  # Adjust as needed
        )

    def _compute_embeddings(self, texts):
        embeddings = []
        for i in tqdm(range(0, len(texts), self.parameters.batch_size), desc="Computing OpenAI embeddings"):
            batch = texts[i:i+self.parameters.batch_size]
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.parameters.embeddings_model
                )
                embeddings.extend([data.embedding for data in response.data])
            except Exception as e:
                logging.error(f"Error computing embeddings for batch: {e}")
                embeddings.extend([None] * len(batch))
        return embeddings

    def _apply_sliding_window(self, text):
        words = text.split()
        windows = []
        for i in range(0, len(words), self.parameters.maximum_tokens_per_window // 2):
            window = ' '.join(words[i:i + self.parameters.maximum_tokens_per_window])
            windows.append(window)
            if len(windows) == self.parameters.maximum_windows:
                break
        return windows

    def process_data(self, data=None):
        if data is None:
            if not hasattr(self, 'dataframe') or self.dataframe is None:
                raise ValueError("No data provided and no dataframe found in the instance.")
            data = self.dataframe
        
        super().process_data()
        
        processed_data = data
        processed_data[self.parameters.score_name] = processed_data[self.parameters.score_name].fillna('Unknown')
        
        if self.parameters.multiple_windows:
            processed_data['windows'] = processed_data['text'].apply(self._apply_sliding_window)
            all_windows = [window for windows in processed_data['windows'] for window in windows]
            all_embeddings = self._compute_embeddings(all_windows)
            processed_data['embeddings'] = processed_data['windows'].apply(
                lambda windows: np.mean([all_embeddings[i] for i in range(len(all_embeddings)) if i < len(windows)], axis=0)
            )
        else:
            processed_data['truncated_text'] = processed_data['text'].apply(
                lambda x: ' '.join(x.split()[:self.parameters.maximum_tokens_per_window])
            )
            processed_data['embeddings'] = self._compute_embeddings(processed_data['truncated_text'])
        
        self.label_encoder = LabelEncoder()
        processed_data['encoded_labels'] = self.label_encoder.fit_transform(processed_data[self.parameters.score_name])
        
        train_data, val_data = train_test_split(processed_data, test_size=0.2, random_state=42)
        
        self.train_data = train_data
        self.val_data = val_data
        self.dataframe = processed_data
        self.val_labels = val_data['encoded_labels'].values
        self.train_labels_str = train_data[self.parameters.score_name].values
        self.val_labels_str = val_data[self.parameters.score_name].values
        
        logging.info(f"Processed {len(processed_data)} samples")
        logging.info(f"Training set: {len(train_data)} samples")
        logging.info(f"Validation set: {len(val_data)} samples")
        logging.info(f"Unique labels: {np.unique(processed_data['encoded_labels'])}")
        
        return processed_data

    def train_model(self):
        X_train = np.array(self.train_data['embeddings'].tolist())
        y_train = self.train_data['encoded_labels']
        
        self.model.fit(X_train, y_train)
        
        train_accuracy = self.model.score(X_train, y_train)
        logging.info(f"Training accuracy: {train_accuracy}")

        self.predict_validation()

    def predict_validation(self):
        X_val = np.array(self.val_data['embeddings'].tolist())
        
        self.val_predictions = self.model.predict(X_val)
        self.val_predictions_labels = self.label_encoder.inverse_transform(self.val_predictions)
        
        self.val_confidence_scores = self.model.predict_proba(X_val)
        
        val_accuracy = accuracy_score(self.val_labels, self.val_predictions)
        logging.info(f"Validation accuracy: {val_accuracy}")

    def predict(self, context, model_input):
        if self.parameters.multiple_windows:
            windows = self._apply_sliding_window(model_input.text)
            embeddings = self._compute_embeddings(windows)
            embedding = np.mean(embeddings, axis=0)
        else:
            truncated_text = ' '.join(model_input.text.split()[:self.parameters.maximum_tokens_per_window])
            embedding = self._compute_embeddings([truncated_text])[0]
        
        prediction = self.model.predict([embedding])[0]
        predicted_label = self.label_encoder.inverse_transform([prediction])[0]
        confidence_score = np.max(self.model.predict_proba([embedding])[0])
        
        return self.Result(
            name=self.parameters.score_name,
            value=predicted_label,
            confidence=confidence_score
        )

    def evaluate_model(self):
        val_predictions_str = self.label_encoder.inverse_transform(self.val_predictions)
        val_labels_str = self.val_labels_str

        val_predictions_str = np.array([str(label) if pd.notna(label) else 'Unknown' for label in val_predictions_str])
        val_labels_str = np.array([str(label) if pd.notna(label) else 'Unknown' for label in val_labels_str])

        accuracy = accuracy_score(val_labels_str, val_predictions_str)
        logging.info(f"Validation Accuracy: {accuracy}")