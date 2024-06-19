import os
import mlflow
import pandas as pd
from plexus.classifiers.MLClassifier import MLClassifier
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
from plexus.classifiers.Score import Score
import xgboost as xgb
from rich import print as rich_print
from rich.panel import Panel
from rich.columns import Columns
from rich.table import Table

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
        logging.info("Creating TF-IDF representation...")
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

        selected_feature_names = self.vectorizer.get_feature_names_out()[self.selector.get_support()]
        selected_feature_names_count = len(selected_feature_names)
        logging.info(f"Selected {selected_feature_names_count} feature names: {selected_feature_names[:10]}")

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
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                random_state=42,
                use_label_encoder=False,
                eval_metric='logloss')
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
        shap_values_list = [(feature, np.mean(shap_values_answer[:, i])) for i, feature in enumerate(selected_feature_names)]
        logging.info("Mean SHAP values calculated for each feature.")
    
        # Log detailed SHAP values for the first 10 features
        for feature, shap_value in shap_values_list[:10]:
            logging.info(f"Feature: \"{feature}\", Mean SHAP Value: {shap_value}")

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
            logging.info(f"Feature: \"{feature}\", Mean SHAP Value: {shap_value}")
            positive_features.add_row(feature, f"{shap_value:.4f}")

        # Get the top 10 features pushing away from the value
        sorted_negative_shap_values = sorted(shap_values_list, key=lambda x: x[1])
        for feature, shap_value in sorted_negative_shap_values[:self.parameters.leaderboard_n_features]:
            logging.info(f"Feature: \"{feature}\", Mean SHAP Value: {shap_value}")
            negative_features.add_row(feature, f"{shap_value:.4f}")

        shapley_analysis_table.add_column("Positive Features", justify="center")
        shapley_analysis_table.add_column("Negative Features", justify="center")
        shapley_analysis_table.add_row(positive_features, negative_features)

        rich_print(Panel(shapley_analysis_table, title="[b]SHAP Analysis[/b]", style="sky_blue1"))

        # Rich table
        ##########

        ##########
        # SHAP plots
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
        self.val_labels = self.label_encoder.transform(self.y_test)
        self.val_predictions = self.model.predict(self.X_test)

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
        Make predictions on the test data.

        :param context: MLflow context for the prediction.
        :param model_input: The input data for making predictions.
        :return: The predictions.
        """
        pass
