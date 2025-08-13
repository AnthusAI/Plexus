import os
import re
import pandas as pd
import numpy as np
import json
import click
from .DataLakeCommands import lake_group
import plexus
import nltk
from nltk.corpus import stopwords
from tqdm import tqdm
from plexus.data.DataCache import DataCache
import rich
from rich.table import Table
from plexus.CustomLogging import logging
from rich.layout import Layout
from rich.panel import Panel
from rich.columns import Columns
from plexus.cli.shared.console import console
from plexus.Registries import scorecard_registry
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.multiclass import OneVsRestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.utils import resample
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb
import shap
from imblearn.over_sampling import RandomOverSampler, SMOTE
from imblearn.under_sampling import RandomUnderSampler

from dotenv import load_dotenv
response = load_dotenv('./.env')

# data.add_command(lake_group)

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

@click.group()
def data():
    """Profiling the data available for each score in the scorecard."""
    pass

class VectorizerLogger:
    def __init__(self, analyzer):
        self.progress = 0
        self.total = 0
        self.analyzer = analyzer

    def __call__(self, doc):
        self.progress += 1
        if self.progress % 1000 == 0:
            logging.info(f"Processed {self.progress}/{self.total} samples")
        return self.analyzer(doc)

@data.command()
@click.option('--scorecard-name', required=True, help='The name of the scorecard to load data for')
@click.option('--excel', required=False, help='The path to the Excel file to load data from')
@click.option('--score-name', required=False, help='The name of the score to analyze for answer breakdown')
@click.option('--all', 'all_questions', is_flag=True, help='Analyze all questions in the scorecard')
@click.option('--value', 'value', required=False, help='The answer value to analyze for feature importance')
@click.option('--top-n-features', 'top_n_features', required=False, default=10000, help='The number of features to analyze for feature importance')
@click.option('--leaderboard-n-features', 'leaderboard_n_features', required=False, default=10, help='The number of features to show in the leaderboard for feature importance')
@click.option('--sample-size', 'sample_size', required=False, default=1, help='The number of samples to use for feature importance')
@click.option('--ngram-range', 'ngram_range', default='2,3', help='The range of n-grams to use for feature extraction, e.g., "2,3"')
def analyze(scorecard_name, excel, score_name, all_questions, value, top_n_features, leaderboard_n_features, sample_size, ngram_range):
    plexus.Scorecard.load_and_register_scorecards('scorecards/')

    try:
        if ',' in ngram_range:
            start, end = map(int, ngram_range.split(','))
            ngram_range = (start, end)
        else:
            single_value = int(ngram_range)
            ngram_range = (single_value, single_value)
    except (ValueError, TypeError):
        raise click.BadParameter("Invalid ngram_range format. Expected 'start,end' (e.g., '2,3') or a single integer.")

    logging.info(f"Analyzing data for scorecard [purple][b]{scorecard_name}[/b][/purple]")
    analyze_scorecard(
        scorecard_name,
        excel,
        score_name,
        all_questions,
        value,
        top_n_features,
        leaderboard_n_features,
        sample_size,
        ngram_range)

def analyze_scorecard(
        scorecard_name,
        excel,
        score_name,
        all_questions,
        value,
        top_n_features,
        leaderboard_n_features,
        sample_size,
        ngram_range):
    
    # First, find the scorecard class from the name.
    scorecard_class = scorecard_registry.get(scorecard_name)
    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    scorecard_folder = os.path.join('.', 'scorecards', scorecard_name)
    scorecard_instance = scorecard_class(scorecard_name=scorecard_name)
    report_folder = os.path.join('.', 'score_results', scorecard_class.name)
    logging.info(f"Using scorecard key [purple][b]{scorecard_name}[/b][/purple] with class name [purple][b]{scorecard_instance.__class__.__name__}[/b][/purple]")
    scorecard_id = scorecard_class.metadata['foreign_id']
    logging.info(f"Scorecard foreign_id [purple][b]{scorecard_id}[/b][/purple]")

    data_cache = DataCache(os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME'],
                           os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME'],
                           os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME'])
    dataframe = None
    # if excel:
    #     server_name = os.getenv('DB_SERVER')
    #     database_name = os.getenv('DB_NAME')
    #     user_name = os.getenv('DB_USER')
    #     password = os.getenv('DB_PASS')
    #     DB.set_current(server_name, database_name, user_name, password)
    
    #     dataframe = data_cache.load_dataframe_from_excel(file_path=excel, scorecard_id=scorecard_id, score_name=score_name)
    # else:
    dataframe = data_cache.load_dataframe_from_queries(queries=[{'scorecard-id':scorecard_id}])

    logging.info("Generating summary of the dataframe")
    dataframe_summary = dataframe.describe()
    rich.print(Panel(dataframe_summary.to_string(), title="Dataframe Summary", border_style="cyan"))

    logging.info("Displaying the first few rows of the dataframe")
    dataframe_head = dataframe.head()
    rich.print(Panel(dataframe_head.to_string(), title="Dataframe Head", border_style="green"))

    if (score_name or all_questions):
        grid = Table.grid(expand=True)
        grid.add_column()
        
        if score_name:
            columns = analyze_question(
                scorecard_id,
                score_name,
                dataframe,
                report_folder,
                value,
                top_n_features=top_n_features,
                leaderboard_n_features=leaderboard_n_features,
                sample_size=sample_size,
                ngram_range=ngram_range)
            question_panel = Panel(columns, title=f"[royal_blue1][b]Question: {score_name}[/b][/royal_blue1]", border_style="magenta1")
            grid.add_row(question_panel)
        else:
            # This means --all
            for score_name in scorecard_instance.score_names():
                columns = analyze_question(
                    scorecard_id,
                    score_name,
                    dataframe,
                    report_folder)
                question_panel = Panel(columns, title=f"[royal_blue1][b]Question: {score_name}[/b][/royal_blue1]", border_style="magenta1")
                grid.add_row(question_panel)

        outer_panel = Panel(grid,
            title=f"[royal_blue1][b]Scorecard: {scorecard_name}[/b][/royal_blue1]", border_style="magenta1")

        rich.print(outer_panel)
    else:
        dataframe_summary_title = f"[royal_blue1][b]Dataframe Summary[/b][/royal_blue1]\nfor [purple][b]Scorecard ID: {scorecard_id}[/b][/purple]"
        dataframe_summary_table = Table(
            title=dataframe_summary_title,
            header_style="sky_blue1",
            border_style="sky_blue1")
        dataframe_summary_table.add_column("Description", justify="right", style="royal_blue1", no_wrap=True)
        dataframe_summary_table.add_column("Value", style="magenta1", justify="right")
        dataframe_summary_table.add_row("Number of Rows", str(dataframe.shape[0]), style="magenta1 bold")
        dataframe_summary_table.add_row("Number of Columns", str(dataframe.shape[1]))
        dataframe_summary_table.add_row("Total Cells", str(dataframe.size))

        column_names_table = Table(
            title="[royal_blue1][b]Column Names[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1")
        column_names_table.add_column("Column Name", style="magenta1")
        for column_name in dataframe.columns:
            column_names_table.add_row(column_name)

        outer_panel = Panel(
            Columns([dataframe_summary_table, column_names_table]),
            title=f"[royal_blue1][b]Scorecard: {scorecard_name}[/b][/royal_blue1]", border_style="magenta1")

        rich.print(outer_panel)

def analyze_question(
        scorecard_id,
        score_name,
        dataframe,
        report_folder,
        value=None,
        top_n_features=10000,
        leaderboard_n_features=14,
        sample_size=1,
        ngram_range=(2,3)):
    panels = []

    data_profiling_results = {}

    question_analysis_table = Table(
        title="[royal_blue1][b]Answer Breakdown[/b][/royal_blue1]",
        header_style="sky_blue1",
        border_style="sky_blue1")
    question_analysis_table.add_column("Answer", justify="right", style="royal_blue1", no_wrap=True)
    question_analysis_table.add_column("Count", style="magenta1", justify="right")
    question_analysis_table.add_column("Percentage", style="magenta1 bold", justify="right")

    answer_counts = dataframe[score_name].value_counts()
    total_responses = answer_counts.sum()
    data_profiling_results['answer_breakdown'] = {}
    for answer_value, count in answer_counts.items():
        percentage_of_total = (count / total_responses) * 100
        formatted_percentage = f"{percentage_of_total:.1f}%"
        question_analysis_table.add_row(str(answer_value), str(count), formatted_percentage)
        data_profiling_results['answer_breakdown'][answer_value] = {
            'count': int(count),
            'percentage': formatted_percentage
        }

    data_profiling_results['shap_analysis'] = {}
    if value is not None:
        sorted_shap_values = compute_shap_feature_importances(
            scorecard_id,
            score_name,
            value,
            dataframe,
            top_n_features=top_n_features,
            sample_size=sample_size,
            ngram_range=ngram_range)
        data_profiling_results['shap_analysis'][value] = {
            'features': [feature for feature, _ in sorted_shap_values],
            'shap_values': [shap_value for _, shap_value in sorted_shap_values]
        }

        positive_features = Table(
            title=f"[royal_blue1][b]Top {leaderboard_n_features} Features Pushing Towards '{value}'[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1")
        positive_features.add_column("Feature", style="magenta1")
        positive_features.add_column("SHAP Value", style="magenta1", justify="right")

        negative_features = Table(
            title=f"[royal_blue1][b]Top {leaderboard_n_features} Features Pushing Away from '{value}'[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1")
        negative_features.add_column("Feature", style="magenta1")
        negative_features.add_column("SHAP Value", style="magenta1", justify="right")

        # Get the top 10 features pushing towards the value
        sorted_shap_values_desc = sorted(sorted_shap_values, key=lambda x: x[1], reverse=True)
        for feature, shap_value in sorted_shap_values_desc[:leaderboard_n_features]:
            positive_features.add_row(feature, f"{shap_value:.4f}")

        # Sort the SHAP values in ascending order to get the most negative values first
        sorted_shap_values_asc = sorted(sorted_shap_values, key=lambda x: x[1])

        # Get the top 10 features pushing away from the value
        for feature, shap_value in sorted_shap_values_asc[:leaderboard_n_features]:
            negative_features.add_row(feature, f"{shap_value:.4f}")

        panels.append(Panel(positive_features, border_style="royal_blue1"))
        panels.append(Panel(negative_features, border_style="royal_blue1"))
        
    panels.append(Panel(question_analysis_table, border_style="royal_blue1"))

    dataframe_summary_title = "[royal_blue1][b]Dataframe Summary[/b][/royal_blue1]"
    dataframe_summary_table = Table(
        title=dataframe_summary_title,
        header_style="sky_blue1",
        border_style="sky_blue1")
    dataframe_summary_table.add_column("Description", justify="right", style="royal_blue1", no_wrap=True)
    dataframe_summary_table.add_column("Value", style="magenta1", justify="right")
    dataframe_summary_table.add_row("Number of Rows", str(dataframe.shape[0]), style="magenta1 bold")

    smallest_answer_count = answer_counts.min()
    total_kinds_of_non_null_answers = dataframe[score_name].nunique()
    total_balanced_count = smallest_answer_count * total_kinds_of_non_null_answers

    dataframe_summary_table.add_row("Smallest Count", str(smallest_answer_count))
    dataframe_summary_table.add_row("Total Balanced Count", str(total_balanced_count), style="magenta1 bold")

    data_profiling_results['dataframe_summary'] = {
        'number_of_rows': int(dataframe.shape[0]),
        'number_of_columns': int(dataframe.shape[1]),
        'total_cells': int(dataframe.size),
        'smallest_answer_count': int(smallest_answer_count),
        'total_balanced_count': int(total_balanced_count)
    }
    report_subfolder = os.path.join(report_folder, f'{score_name}')
    os.makedirs(report_subfolder, exist_ok=True)
    with open(os.path.join(report_subfolder, 'data_profiling.json'), 'w') as data_profiling_file:
        json.dump(data_profiling_results, data_profiling_file, cls=NumpyEncoder)

    panels.append(Panel(dataframe_summary_table, border_style="royal_blue1"))

    columns = Columns(panels)
    if score_name:   
        header_text = f"[bold royal_blue1]{score_name}[/bold royal_blue1]"
    else:
        header_text = f"[bold royal_blue1]{scorecard_id}[/bold royal_blue1]"

    return columns

def preprocess_text(text, stop_words):
    # Remove numerical values and non-word characters, and convert to lowercase
    text = re.sub(r'\d+', '', text)
    text = re.sub(r'\W+', ' ', text.lower())
    
    # Tokenize the text and remove stop words
    tokens = text.split()
    filtered_tokens = [token for token in tokens if token not in stop_words]
    
    return ' '.join(filtered_tokens)

import re
from nltk.corpus import stopwords

def compute_shap_feature_importances(
        scorecard_id,
        score_name,
        answer_value,
        dataframe,
        top_n_features=10000,
        sample_size=1,
        ngram_range=(2,3)):
    logging.info(f"Computing feature importance for scorecard: {scorecard_id}, score: {score_name}")

    # Filter the dataframe to include only the relevant score
    filtered_dataframe = dataframe[dataframe[score_name].notnull()]
    
    # Randomly sample a subset of the filtered dataframe
    sampled_dataframe = filtered_dataframe.sample(frac=sample_size, random_state=42)

    # Log the number of sampled examples
    logging.info(f"Number of sampled examples: {sampled_dataframe.shape[0]}")
    
    # Extract the text data and target labels from the sampled dataframe
    text_data = sampled_dataframe['text'].tolist()
    y = sampled_dataframe[score_name]
    
    logging.info(f"Number of examples: {len(text_data)}")
    
    # Preprocess the text data
    # stop_words = set(stopwords.words('english'))
    # text_data = [preprocess_text(text, stop_words) for text in text_data]
    
    # Create a TF-IDF representation
    logging.info("Creating TF-IDF representation...")
    vectorizer = TfidfVectorizer(ngram_range=ngram_range)
    X = vectorizer.fit_transform(text_data)
    
    logging.info(f"Number of features before selection: {X.shape[1]}")

    # Select top N features based on ANOVA F-value with f_classif
    # selection_function = f_classif
    # For mutual cross information, use: mutual_info_classif
    selection_function = mutual_info_classif

    logging.info(f"Selecting top {top_n_features} features...")
    selector = SelectKBest(score_func=f_classif, k=top_n_features)
    selector.fit(X, y)

    selected_feature_names = vectorizer.get_feature_names_out()[selector.get_support()]
    selected_feature_names_count = len(selected_feature_names)
    logging.info(f"Selected {selected_feature_names_count} feature names: {selected_feature_names[:10]}")

    # Transform the data using the selected features
    X_selected = selector.transform(X)
    
    logging.info(f"Number of features after selection: {X_selected.shape[1]}")
 
    # Split the data into training and testing sets using the selected features
    logging.info("Splitting data into training and testing sets...")
    test_size_proportion = 0.2
    X_train, X_test, y_train, y_test = train_test_split(
        X_selected, y, test_size=test_size_proportion, random_state=42)

    # Log the shape and distribution of the training and testing sets
    logging.info(f"Training set shape: {X_train.shape}, Testing set shape: {X_test.shape}")
    logging.info(f"Training set class distribution: {y_train.value_counts(normalize=True)}")
    logging.info(f"Testing set class distribution: {y_test.value_counts(normalize=True)}")

    # Oversampling using SMOTE (Synthetic Minority Over-sampling Technique)
    smote = SMOTE(random_state=42)
    X_train, y_train = smote.fit_resample(X_train, y_train)

    logging.info(f"Data type of y_train: {y_train.dtype}")
    logging.info(f"Unique values in y_train: {np.unique(y_train)}")

    print("Class distribution in training set:")
    print(y_train.value_counts(normalize=True))
    print("Class distribution in testing set:")
    print(y_test.value_counts(normalize=True))

    print("Unique values before encoding:", np.unique(y))
    # Encode the target variable
    label_encoder = LabelEncoder()
    y_train_encoded = label_encoder.fit_transform(y_train)
    y_test_encoded = label_encoder.transform(y_test)
    print("Unique values after encoding:", np.unique(y_train_encoded), np.unique(y_test_encoded))

    # Check if it's a binary or multi-class classification problem
    if len(label_encoder.classes_) == 2:
        # Binary classification
        logging.info("Training XGBoost Classifier for binary classification...")
        model = xgb.XGBClassifier(
            n_estimators=100,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss')
    else:
        # Multi-class classification
        logging.info("Training XGBoost Classifier for multi-class classification...")
        model = xgb.XGBClassifier(
            n_estimators=100,
            random_state=42,
            use_label_encoder=False,
            eval_metric='mlogloss')

    model.fit(X_train, y_train_encoded)
    
    logging.info("Training completed.")

    # Evaluate the model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test_encoded, y_pred)
    precision = precision_score(y_test_encoded, y_pred, average='weighted')
    recall = recall_score(y_test_encoded, y_pred, average='weighted')
    f1 = f1_score(y_test_encoded, y_pred, average='weighted')

    logging.info(f"Predictions type: {type(y_pred)}, shape: {y_pred.shape}, sample: {y_pred[:5]}")
    logging.info(f"Actual values type: {type(y_test_encoded)}, shape: {y_test_encoded.shape}, sample: {y_test_encoded[:5]}")

    # Log the confusion matrix
    confusion_matrix = pd.crosstab(y_test_encoded, y_pred, rownames=['Actual'], colnames=['Predicted'])
    logging.info(f"Confusion Matrix:\n{confusion_matrix}")

    logging.info(f"Model Evaluation for {score_name}:")
    logging.info(f"Accuracy: {accuracy:.4f}")
    logging.info(f"Precision (weighted): {precision:.4f}")
    logging.info(f"Recall (weighted): {recall:.4f}")
    logging.info(f"F1 Score (weighted): {f1:.4f}")

    logging.info("Calculating SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer(X_train)
    logging.info(f"SHAP values calculated for all classes: {shap_values.values.shape}")
    logging.info(f"SHAP values calculated: {type(shap_values)}; Shape: {getattr(shap_values, 'shape', 'No shape attribute')}")

    # Get the index of the answer value in the label encoder's classes
    answer_index = list(label_encoder.classes_).index(answer_value)
    logging.info(f"Index of the answer value '{answer_value}' in label encoder's classes: {answer_index}")

    # Extract the SHAP values for the desired answer index
    if len(label_encoder.classes_) == 2:
        # For binary classification, shap_values.values has shape (n_instances, n_features)
        shap_values_answer = shap_values.values
        logging.info("Binary classification detected. Using SHAP values for all instances.")
    else:
        # For multi-class classification, shap_values.values has shape (n_instances, n_classes, n_features)
        shap_values_answer = shap_values.values[:, answer_index, :]
        logging.info(f"Multi-class classification detected. Extracting SHAP values for class index {answer_index}.")

    logging.info(f"Extracted SHAP values for the desired class: {shap_values_answer.shape}")

    # Calculate the mean SHAP value for each feature
    shap_values_list = [(feature, np.mean(shap_values_answer[:, i])) for i, feature in enumerate(selected_feature_names)]
    logging.info("Mean SHAP values calculated for each feature.")

    # Log detailed SHAP values for the first 10 features
    for feature, shap_value in shap_values_list[:10]:
        logging.info(f"Feature: \"{feature}\", Mean SHAP Value: {shap_value}")
    
    return shap_values_list
