import pandas as pd
import numpy as np
import mlflow
import mlflow.keras
from tqdm import tqdm
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

        # Check for missing or unexpected values
        print(f"Unique values in '{self.score_name}':", self.dataframe[self.score_name].unique())

        #############
        # Balance data

        # Check the distribution of labels
        print("\nDistribution of labels in the dataframe:")
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
        df_balanced = df_balanced.sample(frac=self.data_percentage / 100, random_state=42)

        # Check the distribution of labels
        print("\nDistribution of labels in the balanced dataframe:")
        print(df_balanced[self.score_name].value_counts())

        # Now you can use df_balanced for the rest of your code
        texts = df_balanced['Transcription'].tolist()
        labels = df_balanced[self.score_name].tolist()

        #############
        # Tokenization

        tokenizer = AutoTokenizer.from_pretrained(self.embeddings_model_name, do_lower_case=True)

        def split_into_sentences(text):
            return nltk.sent_tokenize(text)

        def encode_single_text(tokenizer, text, maximum_length):
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

        # Split the data into training and validation sets
        train_texts, val_texts, train_labels, val_labels = train_test_split(texts, labels, test_size=0.2, random_state=42)

        # Encode the training and validation texts
        print("Training:")
        self.train_encoded_texts = encode_texts_parallel(tokenizer, train_texts, self.maximum_number_of_tokens_analyzed)
        print("Validation:")
        self.val_encoded_texts = encode_texts_parallel(tokenizer, val_texts, self.maximum_number_of_tokens_analyzed)

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

        # One-hot encode the labels only if it's a multi-class classification
        if self.is_multi_class:
            num_classes = len(unique_labels)
            self.train_labels = to_categorical(self.train_labels_int, num_classes=num_classes)
            self.val_labels = to_categorical(self.val_labels_int, num_classes=num_classes)
        else:
            self.train_labels = self.train_labels_int
            self.val_labels = self.val_labels_int

        # Log the types and shapes of the labels
        print(f"train_labels type: {type(self.train_labels)}, shape: {self.train_labels.shape}")
        print(f"val_labels type: {type(self.val_labels)}, shape: {self.val_labels.shape}")
        print(f"train_labels sample: {self.train_labels[:5]}")
        print(f"val_labels sample: {self.val_labels[:5]}")

        # Check the distribution of labels in the training set
        print("Training set label breakdown:")
        if self.is_multi_class:
            train_label_counts = np.unique(np.argmax(self.train_labels, axis=1), return_counts=True)
            print(dict(zip(unique_labels, train_label_counts[1])))
        else:
            train_label_counts = np.unique(self.train_labels, return_counts=True)
            print(dict(zip(unique_labels, train_label_counts[1])))

        # Check the distribution of labels in the validation set
        print("Validation set label breakdown:")
        if self.is_multi_class:
            val_label_counts = np.unique(np.argmax(self.val_labels, axis=1), return_counts=True)
            print(dict(zip(unique_labels, val_label_counts[1])))
        else:
            val_label_counts = np.unique(self.val_labels, return_counts=True)
            print(dict(zip(unique_labels, val_label_counts[1])))
    
    def set_up_mlflow(self):
        """
        Set up MLflow for tracking the experiment, including the experiment name and parameters.
        """
        super().set_up_mlflow()

        # Log parameters
        mlflow.log_param("maximum_number_of_tokens_analyzed", self.maximum_number_of_tokens_analyzed)
        mlflow.log_param("epochs", self.epochs)
        mlflow.log_param("batch_size", self.batch_size)
        mlflow.log_param("warmup_start_learning_rate", self.warmup_start_learning_rate)
        mlflow.log_param("warmup_number_of_epochs", self.warmup_number_of_epochs)
        mlflow.log_param("plateau_learning_rate", self.plateau_learning_rate)
        mlflow.log_param("plateau_number_of_epochs", self.plateau_number_of_epochs)
        mlflow.log_param("learning_rate_decay", self.learning_rate_decay)
        mlflow.log_param("l2_regularization_strength", self.l2_regularization_strength)
        mlflow.log_param("dropout_rate", self.dropout_rate)
        mlflow.log_param("embeddings_model", self.embeddings_model_name)
        mlflow.log_param("data_percentage", self.data_percentage)

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
        
        #############
        # Model setup

        # Embeddings
        input_ids = tf.keras.layers.Input(shape=(self.maximum_number_of_tokens_analyzed,), dtype=tf.int32, name="input_ids")
        attention_mask = tf.keras.layers.Input(shape=(self.maximum_number_of_tokens_analyzed,), dtype=tf.int32, name="attention_mask")
        embeddings_model = TFAutoModel.from_pretrained(self.embeddings_model_name)

        # Set all layers to non-trainable first
        if hasattr(embeddings_model, 'bert'):
            for i in range(len(embeddings_model.bert.encoder.layer)):
                embeddings_model.bert.encoder.layer[i].trainable = False

            # Set only some layers to trainable, for fine-tuning.
            number_of_trainable_bert_layers = 1
            for i in range(-(number_of_trainable_bert_layers), 0, 1):
                embeddings_model.bert.encoder.layer[i].trainable = True

            # Verify the trainability of each layer
            for i, layer in enumerate(embeddings_model.bert.encoder.layer):
                print(f"Layer {i} trainable: {layer.trainable}")
        else:
            print("The model does not have a 'bert' attribute. Skipping layer trainability settings.")

        # Extract the pooled output from the BERT model
        pooled_output = embeddings_model(input_ids, attention_mask=attention_mask)[1]

        # Add a tanh activation layer
        tanh_output = tf.keras.layers.Dense(768, activation='tanh', name="tanh_amplifier")(pooled_output)

        # Apply dropout for regularization
        dropout = tf.keras.layers.Dropout(rate=self.dropout_rate, name="dropout")(tanh_output)

        # intermediate_size = 768

        # intermediate_dense = tf.keras.layers.Dense(
        #     intermediate_size,
        #     activation='relu',
        #     kernel_regularizer=regularizers.l2(l2_regularization_strength)
        # )(dropout)

        # intermediate_dropout = Dropout(rate=dropout_rate)(intermediate_dense)

        # Modify the output layer based on the classification type
        if self.is_multi_class:
            num_labels = len(np.unique(self.train_labels_int))
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

        self.model.summary()

        #############
        # Training

        print("Training the model...")

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

        self.history = self.model.fit(
            [self.train_input_ids, self.train_attention_mask], 
            self.train_labels, 
            validation_data=([self.val_input_ids, self.val_attention_mask], self.val_labels),
            epochs=self.epochs, 
            batch_size=self.batch_size,
            callbacks=[learning_rate_scheduler, early_stop, checkpoint],
            verbose=1
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