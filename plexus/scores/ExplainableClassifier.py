import os
import mlflow
import pandas as pd
from plexus.scores.MLClassifier import MLClassifier
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
import xgboost as xgb
from rich import print as rich_print
from rich.panel import Panel
from rich.columns import Columns
from rich.table import Table
from rich.console import Console
import scipy.sparse

class ExplainableClassifier(MLClassifier):
    """
    A classifier based on XGBoost that uses n-gram vectorization and
    produces a ranked list of features for a target class, by importance.
    """

    class Parameters(MLClassifier.Parameters):
        ...
        top_n_features: int = 10000
        leaderboard_n_features: int = 10
        target_score_name: str
        target_score_value: str
        ngram_range: str = "2,3"
        scale_pos_weight_index: float = 0
        include_explanations: bool = False

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
        text_data = self.dataframe['Transcription'].tolist()
        y = self.dataframe[self.parameters.score_name]
        logging.info(f"Number of examples: {len(text_data)}")

        # Create a TF-IDF representation
        logging.info(f"Creating TF-IDF representation with ngram range: {self.parameters.ngram_range}")
        self.vectorizer = TfidfVectorizer(ngram_range=self.ngram_range)
        X = self.vectorizer.fit_transform(text_data)
            
        logging.info(f"Number of features before selection: {X.shape[1]}")

        # Select top N features based on ANOVA F-value with f_classif
        # selection_function = f_classif
        # For mutual cross information, use: mutual_info_classif
        selection_function = mutual_info_classif

        logging.info(f"Selecting top {self.parameters.top_n_features} features...")
        self.selector = SelectKBest(score_func=f_classif, k=self.parameters.top_n_features)
        self.selector.fit(X, y)

        self.feature_names = self.vectorizer.get_feature_names_out()[self.selector.get_support()]
        logging.info(f"Selected {len(self.feature_names)} feature names: {self.feature_names[:10]}")

        # Transform the data using the selected features
        X_selected = self.selector.transform(X)
        
        logging.info(f"Number of features after selection: {X_selected.shape[1]}")

        # Split the data into training and testing sets using the selected features
        logging.info("Splitting data into training and testing sets...")
        test_size_proportion = 0.2
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X_selected, y, test_size=test_size_proportion, random_state=42)

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
        # Encode the target variable
        self.label_encoder = LabelEncoder()
        self.y_train_encoded = self.label_encoder.fit_transform(self.y_train)
        self.y_test_encoded = self.label_encoder.transform(self.y_test)
        print("Unique values after encoding:", np.unique(self.y_train_encoded), np.unique(self.y_test_encoded))

        # Check if it's a binary or multi-class classification problem
        if len(self.label_encoder.classes_) == 2:
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

        # Create the label_map attribute
        self.label_map = {i: label for i, label in enumerate(self.label_encoder.classes_)}

    @Score.ensure_report_directory_exists
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

        rich_print(Panel(shapley_analysis_table, title="[b]SHAP Analysis[/b]", style="sky_blue1"))

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
        """
        Implement the prediction logic for the validation set.
        """
        # Convert sparse matrix to DataFrame
        X_test_df = pd.DataFrame(self.X_test.toarray(), columns=self.feature_names)

        # Ensure the labels are encoded
        self.val_labels = self.label_encoder.transform(self.y_test)

        # Call predict() with a DataFrame as would be done in production
        self.val_predictions, self.val_confidence_scores, self.val_explanations = self.predict(None, X_test_df)

    def evaluate_model(self):
        # Set the necessary attributes before calling the parent's evaluate_model()
        self.val_input_ids = self.dataframe['Transcription']
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

    def predict(self, context, model_input):
        """
        Make predictions on the test data with confidence scores and top three influential features.
        """
        if isinstance(model_input, pd.DataFrame):
            model_input = scipy.sparse.csr_matrix(model_input.values)

        probabilities = self.model.predict_proba(model_input)
        predictions = probabilities.argmax(axis=1)
        confidenceScores = probabilities.max(axis=1)

        # Extract SHAP values for the features in each sample
        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer.shap_values(model_input)

        # For binary classification, shap_values is a list with one element
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # We take the positive class SHAP values

        explanations = []
        positive_log_count = 0
        negative_log_count = 0
        for sample_index in range(model_input.shape[0]):
            prediction = predictions[sample_index]
            sample = model_input[sample_index]
            non_zero_indices = sample.nonzero()[1]
            sample_features = np.array(self.feature_names)[non_zero_indices]
            sample_shap_values = shap_values[sample_index][non_zero_indices]

            # Sort features by absolute SHAP value
            sorted_indices = np.argsort(-np.abs(sample_shap_values))
            sorted_features = sample_features[sorted_indices]
            sorted_shap_values = sample_shap_values[sorted_indices]

            # Take top 10 features
            top_features = sorted_features[:10]
            top_shap_values = sorted_shap_values[:10]

            log_output = False
            if (prediction == 1) and (positive_log_count < 3):
                positive_log_count += 1
                log_output = True
            elif (prediction == 0) and (negative_log_count < 3):
                negative_log_count += 1
                log_output = True

            if log_output:
                feature_shap_pairs = list(zip(top_features, top_shap_values))

                sample_table = Table(title=f"Sample #{sample_index}", title_style="bold magenta1")
                sample_table.add_column("Classification", justify="center", style="sky_blue1")
                sample_table.add_column("Confidence", justify="center", style="sky_blue1")
                sample_table.add_column("Features", justify="center", style="sky_blue1")

                feature_table = Table(title="Top Features with SHAP Values", title_style="bold magenta1")
                feature_table.add_column("Feature", justify="left", style="sky_blue1")
                feature_table.add_column("SHAP Value", justify="right", style="sky_blue1")
                for feature, shap_value in feature_shap_pairs:
                    feature_table.add_row(feature, f"{shap_value:.4f}", style="sky_blue1")

                sample_table.add_row(
                    str(predictions[sample_index]),
                    f"{confidenceScores[sample_index]:.2f}",
                    feature_table,
                    style="sky_blue1")

                console = Console()
                console.print(sample_table)

            explanations.append("\n".join([f"{feature} ({shap_value:.4f})" for feature, shap_value in zip(top_features, top_shap_values)]))

        return predictions, confidenceScores, explanations