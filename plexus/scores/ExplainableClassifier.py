import os
import pandas as pd
from plexus.scores.Score import Score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.pipeline import Pipeline
from imblearn.over_sampling import RandomOverSampler, SMOTE
from xgboost import XGBClassifier
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import numpy as np
from plexus.CustomLogging import logging
from plexus.scores.Score import Score
from plexus.scores.core.utils import ensure_report_directory_exists
import xgboost as xgb
import rich
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
import scipy.sparse
import re

class ExplainableClassifier(Score):
    """
    A classifier based on XGBoost that uses n-gram vectorization and
    produces a ranked list of features for a target class, by importance.
    """

    class Parameters(Score.Parameters):
        ...
        top_n_features: int = 10000
        leaderboard_n_features: int = 10
        target_score_name: str
        target_score_value: str
        ngram_range: str = "2,3"
        decision_threshold: float = 0.5
        scale_pos_weight_index: float = 0
        include_explanations: bool = False
        keywords: list = None

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.shap_values = None
        self.val_labels = None
        self.val_input_ids = None
        self.val_attention_mask = None

        # Convert the ngram_range string to a tuple
        if ',' in self.parameters.ngram_range:
            start, end = map(int, self.parameters.ngram_range.split(','))
            self.ngram_range = (start, end)
        else:
            value = int(self.parameters.ngram_range)
            self.ngram_range = (value, value)

    def train_model(self):
        logging.info("Vectorizing text data using TF-IDF...")

        # Extract the text data and target labels from the sampled dataframe
        self.original_text_data = self.dataframe['text'].tolist()
        text_data = self.original_text_data  # We'll use this for vectorization
        y = self.dataframe[self.parameters.score_name]
        logging.info(f"Number of examples: {len(text_data)}")

        # Create a TF-IDF representation
        logging.info(f"Creating TF-IDF representation with ngram range: {self.parameters.ngram_range}")
        self.vectorizer = TfidfVectorizer(ngram_range=self.ngram_range)
        X = self.vectorizer.fit_transform(text_data)
        logging.info(f"Vectorized training data shape: {X.shape}")
        logging.info(f"Sample of vectorized training data:\n{X[:5].toarray()}")

        logging.info(f"Number of features before selection: {X.shape[1]}")

        # Select top N features based on ANOVA F-value with f_classif
        selection_function = mutual_info_classif

        logging.info(f"Selecting top {self.parameters.top_n_features} features...")
        self.selector = SelectKBest(score_func=f_classif, k=self.parameters.top_n_features)
        self.selector.fit(X, y)

        self.feature_names = self.vectorizer.get_feature_names_out()[self.selector.get_support()]
        logging.info(f"Selected {len(self.feature_names)} feature names: {self.feature_names[:10]}")

        # Transform the data using the selected features
        X_selected = self.selector.transform(X)
        logging.info(f"Selected features shape: {X_selected.shape}")
        logging.info(f"Sample of selected features:\n{X_selected[:5].toarray()}")

        logging.info(f"Number of features after selection: {X_selected.shape[1]}")

        # Split the data into training and testing sets using the selected features
        logging.info("Splitting data into training and testing sets...")
        test_size_proportion = 0.2
        indices = np.arange(X_selected.shape[0])
        self.X_train, self.X_test, self.y_train, self.y_test, self.train_indices, self.test_indices = train_test_split(
            X_selected, y, indices, test_size=test_size_proportion, random_state=42)

        logging.info(f"Train indices: {self.train_indices[:5]} ... (showing first 5)")
        logging.info(f"Test indices: {self.test_indices[:5]} ... (showing first 5)")

        # Log the shape and distribution of the training and testing sets
        logging.info(f"Training set shape: {self.X_train.shape}, Testing set shape: {self.X_test.shape}")
        logging.info(f"Training set class distribution: {self.y_train.value_counts(normalize=True)}")
        logging.info(f"Testing set class distribution: {self.y_test.value_counts(normalize=True)}")

        # Calculate the negative and positive counts before applying SMOTE
        target_score_value = self.parameters.target_score_value
        self.y_train_binary = (self.y_train == target_score_value)
        negative_count = (~self.y_train_binary).sum()
        positive_count = self.y_train_binary.sum()

        # Oversampling using SMOTE (Synthetic Minority Over-sampling Technique)
        smote = SMOTE(random_state=42)
        self.X_train, self.y_train = smote.fit_resample(self.X_train, self.y_train)

        logging.info(f"Data type of y_train: {self.y_train.dtype}")
        logging.info(f"Unique values in y_train: {np.unique(self.y_train)}")

        print("Class distribution in training set:")
        print(self.y_train.value_counts(normalize=True))
        print("Class distribution in testing set:")
        print(self.y_test.value_counts(normalize=True))

        print("Unique values before encoding:", np.unique(y))
        # Encode the target variable if it's not already encoded
        if self.y_train.dtype == 'object':
            self.label_encoder = LabelEncoder()
            self.y_train_encoded = self.label_encoder.fit_transform(self.y_train)
            self.y_test_encoded = self.label_encoder.transform(self.y_test)
        else:
            self.y_train_encoded = self.y_train
            self.y_test_encoded = self.y_test
            self.label_encoder = LabelEncoder()
            self.label_encoder.classes_ = np.array(['No', 'Yes'])  # Assuming 0 is 'No' and 1 is 'Yes'

        # Set up the label map using the standardized method
        self.setup_label_map(self.label_encoder.classes_)
        logging.info(f"Label map in train_model(): {self.label_map}")
        
        print("Unique values after encoding:", np.unique(self.y_train_encoded), np.unique(self.y_test_encoded))

        # Check if it's a binary or multi-class classification problem
        if len(np.unique(self.y_train_encoded)) == 2:
            # Binary classification
            logging.info("Training XGBoost Classifier for binary classification...")

            # Calculate the automatic scale_pos_weight value
            auto_scale_pos_weight = negative_count / positive_count
            logging.info(f"Negative count: {negative_count}")
            logging.info(f"Positive count: {positive_count}")
            logging.info(f"Auto scale pos weight: {auto_scale_pos_weight}")
            
            # Calculate the final scale_pos_weight value based on the index
            scale_pos_weight = 1 + (auto_scale_pos_weight - 1) * self.parameters.scale_pos_weight_index
            logging.info(f"Scale pos weight: {scale_pos_weight}")
            
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss',
                scale_pos_weight=scale_pos_weight,
            )
        else:
            # Multi-class classification
            logging.info("Training XGBoost Classifier for multi-class classification...")
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                random_state=42,
                use_label_encoder=False,
                eval_metric='mlogloss')

        logging.info("Fitting the model...")
        self.model.fit(self.X_train, self.y_train_encoded)

    @ensure_report_directory_exists
    def explain_model(self):
        logging.info("Explaining model using SHAP values...")
        target_class_index = list(self.label_encoder.classes_).index(self.parameters.target_score_value)

        model = self.model
        vectorizer = self.vectorizer
        selector = self.selector

        logging.info("Creating SHAP TreeExplainer...")
        explainer = shap.TreeExplainer(model)

        logging.info("Calculating SHAP values...")
        shap_values = explainer(self.X_train)
        logging.info(f"SHAP values calculated: {type(shap_values)}; Shape: {getattr(shap_values, 'shape', 'No shape attribute')}")

        # Get the index of the answer value in the label encoder's classes
        answer_index = list(self.label_encoder.classes_).index(self.parameters.target_score_value)
        logging.info(f"Index of the answer value '{self.parameters.target_score_value}' in label encoder's classes: {answer_index}")

        # Extract the SHAP values for the desired answer index
        shap_values_answer = None
        if len(self.label_encoder.classes_) == 2:
            # For binary classification, shap_values.values has shape (n_instances, n_features)
            shap_values_answer = shap_values.values
            logging.info("Binary classification detected. Using SHAP values for all instances.")
        else:
            # For multi-class classification, shap_values.values has shape (n_instances, n_classes, n_features)
            shap_values_answer = shap_values.values[:, answer_index, :]
            logging.info(f"Multi-class classification detected. Extracting SHAP values for class index {answer_index}.")

        logging.info(f"Extracted SHAP values for the desired class: {shap_values_answer.shape}")

        selected_feature_names = vectorizer.get_feature_names_out()[selector.get_support()]
        selected_feature_names_count = len(selected_feature_names)
        logging.info(f"Selected {selected_feature_names_count} feature names: {selected_feature_names[:10]}")
        
        # Calculate the mean SHAP value for each feature
        # Calculate the mean SHAP value for each feature
        shap_values_list = [
            (feature, np.mean(shap_values_answer[:, featureIndex]))
            for featureIndex, feature in enumerate(selected_feature_names)
            if featureIndex < shap_values_answer.shape[1]
        ]
        logging.info("Mean SHAP values calculated for each feature.")

        ##########
        # Rich table

        shapley_analysis_table = Table(
        title=f"[royal_blue1][b]{self.parameters.target_score_name}[/b][/royal_blue1]",
        header_style="sky_blue1",
        border_style="sky_blue1")

        positive_features = Table(
            title=f"[royal_blue1][b]Top {self.parameters.leaderboard_n_features} Features Pushing Towards '{self.parameters.target_score_value}'[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1")
        positive_features.add_column("Feature", style="magenta1")
        positive_features.add_column("SHAP Value", style="magenta1", justify="right")

        negative_features = Table(
            title=f"[royal_blue1][b]Top {self.parameters.leaderboard_n_features} Features Pushing Away from '{self.parameters.target_score_value}'[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1")
        negative_features.add_column("Feature", style="magenta1")
        negative_features.add_column("SHAP Value", style="magenta1", justify="right")

        # Get the top 10 features pushing towards the value
        sorted_positive_shap_values = sorted(shap_values_list, key=lambda x: x[1], reverse=True)
        for feature, shap_value in sorted_positive_shap_values[:self.parameters.leaderboard_n_features]:
            positive_features.add_row(feature, f"{shap_value:.4f}")

        # Get the top 10 features pushing away from the value
        sorted_negative_shap_values = sorted(shap_values_list, key=lambda x: x[1])
        for feature, shap_value in sorted_negative_shap_values[:self.parameters.leaderboard_n_features]:
            negative_features.add_row(feature, f"{shap_value:.4f}")

        shapley_analysis_table.add_column("Positive Features", justify="center")
        shapley_analysis_table.add_column("Negative Features", justify="center")
        shapley_analysis_table.add_row(positive_features, negative_features)

        rich.print(Panel(shapley_analysis_table, title="[b]SHAP Analysis[/b]", style="sky_blue1"))

        # Rich table
        ##########

        ##########
        # SHAP plots
        plt.clf()
        report_directory_path = self.report_directory_path()

        # Get the top 10 positive and negative features
        top_positive_features = [feature for feature, _ in sorted_positive_shap_values[:self.parameters.leaderboard_n_features]]
        top_negative_features = [feature for feature, _ in sorted_negative_shap_values[:self.parameters.leaderboard_n_features]]

        # Convert selected_feature_names to a list
        selected_feature_names_list = selected_feature_names.tolist()

        # Plot SHAP summary for top positive features
        top_positive_indices = [selected_feature_names_list.index(feature) for feature in top_positive_features]
        shap_values_positive = shap_values_answer[:, top_positive_indices]
        shap_explanation_positive = shap.Explanation(
            values=shap_values_positive,
            base_values=explainer.expected_value,
            data=self.X_train[:, top_positive_indices],
            feature_names=top_positive_features,
        )
        shap.plots.beeswarm(shap_explanation_positive, show=False)
        plt.title("SHAP Summary Plot - Top Positive Features")
        plt.tight_layout()
        plt.savefig(os.path.join(report_directory_path, "shap_summary_top_positive.png"))
        plt.close()

        # Plot SHAP summary for top negative features
        plt.clf()
        top_negative_indices = [selected_feature_names_list.index(feature) for feature in top_negative_features]
        shap_values_negative = shap_values_answer[:, top_negative_indices]
        shap_explanation_negative = shap.Explanation(
            values=shap_values_negative,
            base_values=explainer.expected_value,
            data=self.X_train[:, top_negative_indices],
            feature_names=top_negative_features,
        )
        shap.plots.beeswarm(shap_explanation_negative, show=False)
        plt.title("SHAP Summary Plot - Top Negative Features")
        plt.tight_layout()
        plt.savefig(os.path.join(report_directory_path, "shap_summary_top_negative.png"))
        plt.close()

    def predict_validation(self):
        logging.info("predict_validation() called")
        logging.info(f"Number of test samples: {len(self.test_indices)}")

        self.val_predictions = []
        self.val_confidence_scores = []
        self.val_explanations = []
        self.val_labels = self.y_test

        for i, original_index in enumerate(self.test_indices):
            original_text = self.original_text_data[original_index]
            true_label = self.val_labels.iloc[i]

            # Use the actual predict() function
            result = self.predict(None, original_text)[0]

            self.val_predictions.append(result.score)
            self.val_confidence_scores.append(result.confidence)
            self.val_explanations.append(result.explanation)

            if i == 0 or result.score != true_label:
                logging.info(f"{'First sample' if i == 0 else 'Mismatch'} (index {i}):")
                logging.info(f"Original text:\n{original_text[:500]}...")  # Log first 500 characters
                logging.info(f"True label: {true_label}")
                logging.info(f"Prediction: {result.score}")
                logging.info(f"Confidence: {result.confidence}")
                logging.info(f"Explanation:\n{result.explanation}")

        self.val_predictions = np.array(self.val_predictions)
        self.val_confidence_scores = np.array(self.val_confidence_scores)

        accuracy = np.mean(self.val_predictions == self.val_labels)
        logging.info(f"Validation complete. Processed {len(self.test_indices)} samples.")
        logging.info(f"Accuracy: {accuracy:.2%}")

        logging.info(f"val_predictions shape: {self.val_predictions.shape}")
        logging.info(f"val_confidence_scores shape: {self.val_confidence_scores.shape}")
        logging.info(f"val_labels shape: {self.val_labels.shape}")
        logging.info(f"Number of explanations: {len(self.val_explanations)}")

        # Log a few sample predictions
        num_samples = min(5, len(self.val_predictions))
        logging.info(f"Sample predictions (first {num_samples}):")
        for i in range(num_samples):
            logging.info(f"  Sample {i}: True: {self.val_labels.iloc[i]}, Predicted: {self.val_predictions[i]}, Confidence: {self.val_confidence_scores[i]:.4f}")

    def preprocess_text(self, text):
        # Implement any necessary preprocessing steps here
        # This should mimic the preprocessing done during training
        return text  # For now, just return the text as-is

    def evaluate_model(self):
        # Set the necessary attributes before calling the parent's evaluate_model()
        self.val_input_ids = self.dataframe['text']
        self.val_attention_mask = None  # Set this if applicable to your model

        super().evaluate_model()

        # Perform any additional evaluation specific to ExplainableClassifier
        self.explain_model()

    # This visualization doesn't work for fastText, so leave it out.
    def _plot_training_history(self):
        pass

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
        This Score has an additional output attribute, explanation, which is a string
        """
        confidence: float
        explanation: str

    # New method to vectorize a single transcript
    def vectorize_transcript(self, transcript: str):        
        vectorized = self.vectorizer.transform([transcript])        
        selected = self.selector.transform(vectorized)
        return selected

    def predict(self, context, model_input):
        if isinstance(model_input, str):
            preprocessed_input = self.preprocess_text(model_input)
            
            # Check for keyword matches
            if self.parameters.keywords:
                for keyword in self.parameters.keywords:
                    # Use regex to find whole word matches
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, preprocessed_input, re.IGNORECASE):
                        # Find the sentence containing the keyword
                        sentences = preprocessed_input.split('.')
                        matching_sentence = next((s for s in sentences if re.search(pattern, s, re.IGNORECASE)), '')
                        
                        explanation = f"Keyword match found: '{keyword}' in the sentence: '{matching_sentence.strip()}'"
                        return [
                            self.Result(
                                name =        self.parameters.score_name,
                                value =       "Yes",
                                confidence =  1.0,
                                explanation = explanation
                            )
                        ]

            vectorized_input = self.vectorize_transcript(preprocessed_input)
        else:
            vectorized_input = model_input
        
        prepared_input = self._prepare_input(vectorized_input)
        probabilities = self._calculate_probabilities(prepared_input)
        prediction = np.argmax(probabilities)
        confidence_score = np.max(probabilities)
        
        prediction_label = list(self.label_map.keys())[list(self.label_map.values()).index(prediction)]
        
        # Generate a basic explanation
        feature_importance = self.model.feature_importances_
        feature_names = self.feature_names
        sorted_idx = feature_importance.argsort()
        top_features = [f"{feature_names[i]} ({feature_importance[i]:.4f})" for i in sorted_idx[-10:]]
        explanation = "\n".join(reversed(top_features))

        return [
            self.Result(
                name =        self.parameters.score_name,
                value =       prediction_label,
                confidence =  confidence_score,
                explanation = explanation
            )
        ]

    def _prepare_input(self, model_input):
        logging.debug(f"Preparing input of type: {type(model_input)}")
        if isinstance(model_input, dict):
            model_input = pd.DataFrame([model_input])
        if isinstance(model_input, pd.DataFrame):
            if model_input.shape[0] > 1:
                raise ValueError("Input should be a single sample, not multiple rows")
            logging.debug(f"Input shape: {model_input.shape}")
            return scipy.sparse.csr_matrix(model_input.values)
        elif isinstance(model_input, (list, np.ndarray)):
            model_input = np.array(model_input).reshape(1, -1)
            logging.debug(f"Input shape: {model_input.shape}")
            return scipy.sparse.csr_matrix(model_input)
        elif scipy.sparse.issparse(model_input):
            if model_input.shape[0] > 1:
                raise ValueError("Input should be a single sample, not multiple rows")
            logging.debug(f"Input shape: {model_input.shape}")
            return model_input
        else:
            raise ValueError(f"Unsupported input type: {type(model_input)}")

    def _calculate_probabilities(self, prepared_input):
        logging.debug("Predicting probabilities")
        probabilities = self.model.predict_proba(prepared_input)
        logging.debug(f"Probabilities shape: {probabilities.shape}")
        return probabilities[0]  # Return probabilities for single sample

    def _extract_shap_values(self, prepared_input):
        logging.debug("Extracting SHAP values")
        self.explainer = shap.TreeExplainer(self.model)
        shap_values = self.explainer.shap_values(prepared_input)
        logging.debug(f"SHAP values type: {type(shap_values)}")
        logging.debug(f"Shape of SHAP values: {np.array(shap_values).shape}")
        return np.array(shap_values)

    def _generate_explanations(self, prepared_input, predictions, confidenceScores, shap_values):
        logging.info("Generating explanations")
        explanations = []
        positive_log_count = 0
        negative_log_count = 0
        for sample_index in range(prepared_input.shape[0]):
            explanation = self._generate_single_explanation(
                sample_index, prepared_input, predictions, confidenceScores, shap_values,
                positive_log_count, negative_log_count
            )
            explanations.append(explanation)
            if predictions[sample_index] == 1:
                positive_log_count += 1
            else:
                negative_log_count += 1
        return explanations

    def _generate_single_explanation(self, prepared_input, prediction, confidence_score, shap_values, 
                                    sample_index, positive_log_count, negative_log_count):
        logging.debug(f"Generating explanation for sample {sample_index}")
        logging.debug(f"Prediction: {prediction}, Confidence: {confidence_score}")
        
        sample = prepared_input[0]  # Get the first (and only) sample
        if scipy.sparse.issparse(sample):
            non_zero_indices = sample.nonzero()[1]
        else:
            non_zero_indices = np.nonzero(sample)[0]
        
        logging.debug(f"Number of non-zero features: {len(non_zero_indices)}")
        
        if len(non_zero_indices) == 0:
            logging.warning(f"Sample {sample_index}: No non-zero features found.")
            return "Unable to generate explanation due to lack of non-zero features."

        sample_features = [self.feature_names[i] for i in non_zero_indices]
        
        # Handle multi-class SHAP values
        if shap_values.ndim == 3:  # Multi-class case
            logging.debug("Multi-class SHAP values detected")
            # For multi-class, use the SHAP values for the predicted class
            sample_shap_values = shap_values[0, non_zero_indices, prediction]
        else:
            logging.debug("Binary classification SHAP values detected")
            sample_shap_values = shap_values[0, non_zero_indices]

        logging.debug(f"Shape of sample_shap_values: {sample_shap_values.shape}")
        
        # Ensure sample_shap_values is 1-dimensional
        if sample_shap_values.ndim > 1:
            sample_shap_values = sample_shap_values.flatten()

        sorted_indices = np.argsort(-np.abs(sample_shap_values))
        logging.debug(f"Shape of sorted_indices: {sorted_indices.shape}")
        
        sorted_features = [sample_features[i] for i in sorted_indices]
        sorted_shap_values = sample_shap_values[sorted_indices]

        top_features = sorted_features[:10]
        top_shap_values = sorted_shap_values[:10]

        if not hasattr(self, 'positive_log_count'):
            self.positive_log_count = 0
        if not hasattr(self, 'negative_log_count'):
            self.negative_log_count = 0
        should_log = (prediction == 1 and self.positive_log_count < 3) or (prediction == 0 and self.negative_log_count < 3)
        if should_log:
            self._log_sample_explanation(sample_index, prediction, confidence_score,
                                        top_features, top_shap_values)
            if prediction == 1:
                self.positive_log_count += 1
            else:
                self.negative_log_count += 1

        explanation = "\n".join([f"{feature} ({shap_value:.4f})" for feature, shap_value in zip(top_features, top_shap_values)])
        return explanation

    def _log_sample_explanation(self, sample_index, prediction, confidence, top_features, top_shap_values):
        feature_shap_pairs = list(zip(top_features, top_shap_values))
        logging.info(f"Sample {sample_index} - Top {len(feature_shap_pairs)} features with SHAP values:")
        for feature, shap_value in feature_shap_pairs:
            logging.info(f"  {feature}: {shap_value:.4f}")

        shap_explanation = shap.Explanation(
            values=top_shap_values,
            base_values=self.explainer.expected_value[prediction] if isinstance(self.explainer.expected_value, list) else self.explainer.expected_value,
            data=np.zeros(len(top_features)),  # Placeholder data
            feature_names=top_features
        )

        try:
            plt.figure(figsize=(12, 8))
            plt.subplots_adjust(left=0.3)
            shap.plots.waterfall(shap_explanation, show=False, max_display=10)

            ax = plt.gca()
            labels = [item.get_text() for item in ax.get_yticklabels()]
            cleaned_labels = [label.split('=')[0].strip() for label in labels]
            ax.set_yticklabels(cleaned_labels, rotation=0, ha='right')

            plot_filename = self.report_file_name(f"shap_waterfall_sample_{sample_index}.png")
            plt.savefig(plot_filename, bbox_inches='tight')
            plt.close()

        except Exception as e:
            logging.warning(f"Unable to create SHAP waterfall plot for sample {sample_index}: {str(e)}")

        sample_table = Table(title=f"Sample #{sample_index}", title_style="bold magenta1")
        sample_table.add_column("Classification", justify="center", style="sky_blue1")
        sample_table.add_column("Confidence", justify="center", style="sky_blue1")
        sample_table.add_column("Features", justify="center", style="sky_blue1")

        feature_table = Table(title="Top Features with SHAP Values", title_style="bold magenta1")
        feature_table.add_column("Feature", justify="left", style="sky_blue1")
        feature_table.add_column("SHAP Value", justify="right", style="sky_blue1")
        for feature, shap_value in feature_shap_pairs:
            feature_table.add_row(feature, f"{shap_value:.4f}", style="sky_blue1")

        sample_table.add_row(str(prediction), f"{confidence:.2f}", feature_table, style="sky_blue1")

        console = Console()
        console.print(sample_table)