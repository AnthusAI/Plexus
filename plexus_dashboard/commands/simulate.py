import click
import json
import logging
import numpy as np
import random
import time
from datetime import datetime, timezone
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    confusion_matrix,
    balanced_accuracy_score,
    f1_score
)
from plexus_dashboard.api.client import PlexusDashboardClient
from plexus_dashboard.api.models.account import Account
from plexus_dashboard.api.models.experiment import Experiment
from plexus_dashboard.api.models.score import Score
from plexus_dashboard.api.models.scorecard import Scorecard
from plexus_dashboard.api.models.score_result import ScoreResult
import math

logger = logging.getLogger(__name__)

SCORE_GOALS = ['sensitivity', 'precision', 'balanced']

MEDICAL_CALL_CLASSES = [
    "3rd Party Clinic", "Agent calling for a Patient", "Follow-up Appointment",
    "New Patient Registration", "Insurance Verification", "Patient Referral",
    "Lab Results Inquiry", "Medication Refill Request", "Appointment Cancellation",
    "Telehealth Consultation", "Patient Feedback", "Emergency Contact",
    "Billing Inquiry", "Health Record Request"
]

ICE_CREAM_CLASSES = [
    "Vanilla", "Chocolate", "Strawberry", "Mint Chocolate Chip", 
    "Cookie Dough", "Rocky Road", "Butter Pecan", "Coffee",
    "Pistachio", "Cookies and Cream", "Salted Caramel", "Neapolitan",
    "Cherry Garcia", "French Vanilla", "Dark Chocolate", "Chocolate Chip"
]

DOG_BREED_CLASSES = [
    "Labrador Retriever", "German Shepherd", "Golden Retriever", 
    "French Bulldog", "Bulldog", "Poodle", "Beagle", "Rottweiler",
    "Dachshund", "Yorkshire Terrier", "Boxer", "Great Dane",
    "Siberian Husky", "Doberman", "Corgi", "Shih Tzu"
]

SOCIAL_SENTIMENT_CLASSES = [
    "Positive Promotion", "Negative Review", "Customer Support Request",
    "Product Question", "Feature Request", "Bug Report", "Spam",
    "Harassment", "Community Discussion", "News Share", "Meme/Humor",
    "Political Content", "Event Announcement", "Job Posting",
    "Partnership Inquiry", "Market Research"
]

CLASS_SETS = [
    ("Medical Call Types", MEDICAL_CALL_CLASSES),
    ("Ice Cream Flavors", ICE_CREAM_CLASSES),
    ("Dog Breeds", DOG_BREED_CLASSES),
    ("Social Media Content", SOCIAL_SENTIMENT_CLASSES)
]

def select_num_classes() -> int:
    """Select number of classes with logarithmic bias towards smaller numbers."""
    # Generate random number between 0 and 1
    r = random.random()
    # Use log scale to bias towards smaller numbers
    # This will give roughly:
    # 50% chance of 2 classes
    # 25% chance of 3 classes
    # Remaining 25% spread across 4-20 classes
    if r < 0.5:  # 50% chance
        return 2
    elif r < 0.75:  # 25% chance
        return 3
    else:  # 25% chance spread across 4-20
        # Use log scale for remaining range
        log_range = math.log(20 - 3)  # log of range from 4 to 20
        scaled_r = (r - 0.75) * 4  # Scale remaining range to 0-1
        num_classes = math.floor(math.exp(scaled_r * log_range)) + 4
        return min(num_classes, 20)

def generate_class_distribution(num_classes: int, total_items: int, balanced: bool) -> list:
    """Generate a distribution of classes with counts."""
    if balanced:
        base_count = total_items // num_classes
        remainder = total_items % num_classes
        counts = [base_count for _ in range(num_classes)]
        for i in range(remainder):
            counts[i] += 1
    else:
        remaining_items = total_items
        counts = []
        for i in range(num_classes - 1):
            portion = random.uniform(0.3, 0.7) if i == 0 else random.uniform(0.1, 0.4)
            count = int(remaining_items * portion)
            counts.append(count)
            remaining_items -= count
        counts.append(remaining_items)
    
    # Determine labels based on number of classes
    if num_classes == 2 and random.random() < 0.5:
        labels = ["Yes", "No"]
    elif num_classes == 3 and random.random() < 0.5:
        labels = ["Yes", "No", "NA"]
    else:
        # Select a random class set
        class_set_name, class_set = random.choice(CLASS_SETS)
        labels = random.sample(class_set, num_classes)
        logger.info(f"Using {class_set_name} for classification labels")
    
    return [
        {"label": label, "count": count}
        for label, count in zip(labels, counts)
    ]

def simulate_prediction(true_label: str, accuracy: float, valid_labels: list) -> str:
    if random.random() < accuracy:
        return true_label
    else:
        other_labels = [l for l in valid_labels if l != true_label]
        return random.choice(other_labels)

def select_metrics_and_explanation(
    is_binary: bool,
    is_balanced: bool,
    score_goal: str
) -> tuple[list[str], str]:
    metrics_config = {
        "binary": {
            "balanced": {
                "sensitivity": (
                    ["Sensitivity", "Accuracy", "Precision", "F1"],
                    "Sensitivity is prioritized to maximize true positive detection rate"
                ),
                "precision": (
                    ["Precision", "Accuracy", "Sensitivity", "F1"],
                    "Precision is prioritized to minimize false positive predictions"
                ),
                "balanced": (
                    ["Balanced Accuracy", "Precision", "Sensitivity", "F1"],
                    "Balanced accuracy ensures equal treatment of all classes"
                )
            },
            "unbalanced": {
                "sensitivity": (
                    ["Sensitivity", "Balanced Accuracy", "Precision", "F1"],
                    "Sensitivity focus with balanced accuracy for imbalanced data"
                ),
                "precision": (
                    ["Precision", "Balanced Accuracy", "Sensitivity", "NPV"],
                    "Precision focus with balanced metrics for imbalanced data"
                ),
                "balanced": (
                    ["Balanced Accuracy", "Precision", "Sensitivity", "F1"],
                    "Balanced metrics chosen for imbalanced dataset"
                )
            }
        },
        "multiclass": {
            "balanced": {
                "sensitivity": (
                    ["Macro Sensitivity", "Accuracy", "Macro Precision", "Macro F1"],
                    "Macro sensitivity prioritized across all classes"
                ),
                "precision": (
                    ["Macro Precision", "Accuracy", "Macro Sensitivity", "Macro F1"],
                    "Macro precision prioritized for reliable predictions"
                ),
                "balanced": (
                    ["Accuracy", "Macro Precision", "Macro Sensitivity", "Macro F1"],
                    "Balanced evaluation across all classes"
                )
            },
            "unbalanced": {
                "sensitivity": (
                    ["Macro Sensitivity", "Balanced Accuracy", "Macro Precision", 
                     "Macro F1"],
                    "Macro sensitivity with balanced accuracy for fairness"
                ),
                "precision": (
                    ["Macro Precision", "Balanced Accuracy", "Macro Sensitivity", 
                     "Macro F1"],
                    "Macro precision with balanced handling of classes"
                ),
                "balanced": (
                    ["Balanced Accuracy", "Macro Precision", "Macro Sensitivity", 
                     "Macro F1"],
                    "Balanced metrics for fair multiclass evaluation"
                )
            }
        }
    }
    
    classification_type = "binary" if is_binary else "multiclass"
    balance_type = "balanced" if is_balanced else "unbalanced"
    
    return metrics_config[classification_type][balance_type][score_goal]

def calculate_metrics(true_values, predicted_values, is_binary, is_balanced, score_goal):
    metric_names, explanation = select_metrics_and_explanation(
        is_binary, is_balanced, score_goal
    )
    
    y_true = np.array(true_values)
    y_pred = np.array(predicted_values)
    
    metrics = []
    for metric_name in metric_names:
        if metric_name == "Accuracy":
            value = accuracy_score(y_true, y_pred) * 100
        elif metric_name == "Balanced Accuracy":
            value = balanced_accuracy_score(y_true, y_pred) * 100
        elif metric_name in ["Precision", "Macro Precision"]:
            value = precision_score(y_true, y_pred, average='macro', 
                                  zero_division=0) * 100
        elif metric_name in ["Sensitivity", "Macro Sensitivity"]:
            value = recall_score(y_true, y_pred, average='macro', 
                               zero_division=0) * 100
        elif metric_name in ["F1", "Macro F1"]:
            value = f1_score(y_true, y_pred, average='macro', 
                           zero_division=0) * 100
        else:  # NPV - custom calculation
            tn = np.sum((y_true != 1) & (y_pred != 1))
            fn = np.sum((y_true == 1) & (y_pred != 1))
            value = (tn / (tn + fn) if (tn + fn) > 0 else 0) * 100
        
        metrics.append({
            "name": metric_name,
            "value": float(value),
            "unit": "%",
            "maximum": 100,
            "priority": metric_names.index(metric_name) == 0
        })
    
    return metrics, explanation 