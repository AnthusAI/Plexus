import os
import re
import pandas as pd
import numpy as np
import json
import click
import plexus
import nltk
from nltk.corpus import stopwords
from tqdm import tqdm
from plexus.DataCache import DataCache
from rich import print as rich_print
from rich.table import Table
from plexus.CustomLogging import logging
from rich.layout import Layout
from rich.panel import Panel
from rich.columns import Columns
from plexus.cli.console import console
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
from plexus.scorecards.TermLifeAI import TermLifeAI

from dotenv import load_dotenv
response = load_dotenv('./.env')

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
@click.option('--score-name', required=False, help='The name of the score to analyze for answer breakdown')
@click.option('--all', 'all_questions', is_flag=True, help='Analyze all questions in the scorecard')
@click.option('--value', 'value', required=False, help='The answer value to analyze for feature importance')
def analyze(scorecard_name, score_name, all_questions, value):
    plexus.Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)

    logging.info(f"Analyzing data for scorecard [purple][b]{scorecard_name}[/b][/purple]")
    analyze_scorecard(scorecard_name, score_name, all_questions, value)

def analyze_scorecard(scorecard_name, score_name, all_questions, value):
    
    # First, find the scorecard class from the name.
    scorecard_class = scorecard_registry.get(scorecard_name)
    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    scorecard_folder = os.path.join('.', 'scorecards', scorecard_name)
    scorecard_instance = scorecard_class(scorecard_folder_path=scorecard_folder)
    report_folder = os.path.join('.', 'reports', scorecard_class.name)
    logging.info(f"Using scorecard key [purple][b]{scorecard_name}[/b][/purple] with class name [purple][b]{scorecard_instance.__class__.__name__}[/b][/purple]")
    scorecard_id = scorecard_class.metadata['foreign_id']
    logging.info(f"Scorecard foreign_id [purple][b]{scorecard_id}[/b][/purple]")

    data_cache = DataCache(os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME'],
                           os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME'],
                           os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME'])
    dataframe = data_cache.load_dataframe(queries=[{'scorecard-id':scorecard_id}])

    print('')

    if (score_name or all_questions):
        grid = Table.grid(expand=True)
        grid.add_column()
        
        if score_name:
            columns = analyze_question(scorecard_id, score_name, dataframe, report_folder, value)
            question_panel = Panel(columns, title=f"[royal_blue1][b]Question: {score_name}[/b][/royal_blue1]", border_style="magenta1")
            grid.add_row(question_panel)
        else:
            # This means --all
            for score_name in scorecard_instance.score_names():
                columns = analyze_question(scorecard_id, score_name, dataframe, report_folder)
                question_panel = Panel(columns, title=f"[royal_blue1][b]Question: {score_name}[/b][/royal_blue1]", border_style="magenta1")
                grid.add_row(question_panel)

        outer_panel = Panel(grid,
            title=f"[royal_blue1][b]Scorecard: {scorecard_name}[/b][/royal_blue1]", border_style="magenta1")

        rich_print(outer_panel)
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

        rich_print(outer_panel)

def analyze_question(scorecard_id, score_name, dataframe, report_folder, value=None):
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
        sorted_shap_values = compute_shap_feature_importances(scorecard_id, score_name, value, dataframe)
        data_profiling_results['shap_analysis'][value] = {
            'features': [feature for feature, _ in sorted_shap_values],
            'shap_values': [shap_value for _, shap_value in sorted_shap_values]
        }

        sitfl_table_positive = Table(
            title=f"[royal_blue1][b]Top 10 Features Pushing Towards '{value}'[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1")
        sitfl_table_positive.add_column("Feature", style="magenta1")
        sitfl_table_positive.add_column("SHAP Value", style="magenta1", justify="right")

        sitfl_table_negative = Table(
            title=f"[royal_blue1][b]Top 10 Features Pushing Away from '{value}'[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1")
        sitfl_table_negative.add_column("Feature", style="magenta1")
        sitfl_table_negative.add_column("SHAP Value", style="magenta1", justify="right")

        # Get the top 10 features pushing towards the value
        for feature, shap_value in sorted_shap_values[:10]:
            sitfl_table_positive.add_row(feature, f"{shap_value:.4f}")

        # Sort the SHAP values in ascending order to get the most negative values first
        sorted_shap_values_asc = sorted(sorted_shap_values, key=lambda x: x[1])

        # Get the top 10 features pushing away from the value
        for feature, shap_value in sorted_shap_values_asc[:10]:
            sitfl_table_negative.add_row(feature, f"{shap_value:.4f}")

        panels.append(Panel(sitfl_table_positive, border_style="royal_blue1"))
        panels.append(Panel(sitfl_table_negative, border_style="royal_blue1"))
        
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
        header_text = f"[bold royal_blue1]{scorecard_name}[/bold royal_blue1]"

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
nltk.download('punkt')
nltk.download('stopwords')

def compute_shap_feature_importances(scorecard_id, score_name, answer_value, dataframe, top_n_features=1024, sample_size=.25):
    logging.info(f"Computing sITFL difference for scorecard: {scorecard_id}, score: {score_name}")
    
    # Filter the dataframe to include only the relevant score
    filtered_dataframe = dataframe[dataframe[score_name].notnull()]
    
    # Randomly sample a subset of the filtered dataframe
    sampled_dataframe = filtered_dataframe.sample(frac=sample_size, random_state=42)

    # Log the number of sampled examples
    logging.info(f"Number of sampled examples: {sampled_dataframe.shape[0]}")
    
    # Extract the text data and target labels from the sampled dataframe
    text_data = sampled_dataframe['Transcription'].tolist()
    y = sampled_dataframe[score_name]
    
    logging.info(f"Number of examples: {len(text_data)}")
    
    # Preprocess the text data
    stop_words = set(stopwords.words('english'))
    preprocessed_text_data = [preprocess_text(text, stop_words) for text in text_data]
    
    # Create a TF-IDF representation
    logging.info("Creating TF-IDF representation...")
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(preprocessed_text_data)
    
    # Select top N features based on ANOVA F-value with f_classif
    # selection_function = f_classif
    # For mutual cross information, use: mutual_info_classif
    selection_function = mutual_info_classif

    logging.info(f"Selecting top {top_n_features} features...")
    selector = SelectKBest(score_func=f_classif, k=top_n_features)
    logging.info(f"Fitting selector with {X.shape[1]} features...")
    selector.fit(X, y)
    
    selected_feature_names = vectorizer.get_feature_names_out()[selector.get_support()]
    logging.debug(f"Selected feature names: {selected_feature_names}")

    # Transform the data using the selected features
    X_selected = selector.transform(X)
    
    logging.info(f"Number of features after selection: {X_selected.shape[1]}")
 
    # Split the data into training and testing sets using the selected features
    logging.info("Splitting data into training and testing sets...")
    X_train, X_test, y_train, y_test = train_test_split(X_selected, y, test_size=0.2, random_state=42)

    logging.info(f"Data type of y_train: {y_train.dtype}")
    logging.info(f"Unique values in y_train: {np.unique(y_train)}")

    # Encode the target variable
    label_encoder = LabelEncoder()
    y_train_encoded = label_encoder.fit_transform(y_train)
    y_test_encoded = label_encoder.transform(y_test)

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

    with tqdm(total=model.n_estimators, desc="Training", unit="estimator") as pbar:
        model.fit(X_train, y_train_encoded)
        pbar.update(model.n_estimators)
    
    logging.info("Training completed.")

    # Evaluate the model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test_encoded, y_pred)
    precision = precision_score(y_test_encoded, y_pred, average='weighted')
    recall = recall_score(y_test_encoded, y_pred, average='weighted')
    f1 = f1_score(y_test_encoded, y_pred, average='weighted')

    logging.info(f"Model Evaluation for {score_name}:")
    logging.info(f"Accuracy: {accuracy:.4f}")
    logging.info(f"Precision (weighted): {precision:.4f}")
    logging.info(f"Recall (weighted): {recall:.4f}")
    logging.info(f"F1 Score (weighted): {f1:.4f}")

    logging.info(f"Feature names: {selected_feature_names}")

    # Calculate SHAP values
    logging.info("Calculating SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_train)

    # Get the index of the answer value in the label encoder's classes
    answer_index = list(label_encoder.classes_).index(answer_value)

    # For binary classification, shap_values is a list with a single array
    if len(label_encoder.classes_) == 2:
        shap_values = shap_values[0]
    else:
        # For multi-class classification, shap_values is a list of arrays (one per class)
        shap_values = shap_values[answer_index]

    # Calculate the mean SHAP value for each feature
    shap_values_list = [(feature, np.mean(shap_value)) for feature, shap_value in zip(selected_feature_names, shap_values)]

    # Verify SHAP values
    for feature, shap_value in shap_values_list:
        logging.info(f"Feature: {feature}, SHAP Value: {shap_value}, Type: {type(shap_value)}")

    # Sort the features by the absolute value of their SHAP values in descending order
    sorted_shap_values = sorted(shap_values_list, key=lambda x: abs(x[1]), reverse=True)

    return sorted_shap_values