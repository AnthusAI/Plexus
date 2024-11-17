import click
import json
import logging
import numpy as np
import random
import time
from datetime import datetime, timezone
from sklearn.metrics import confusion_matrix
from plexus_dashboard.api.client import PlexusDashboardClient
from plexus_dashboard.api.models.account import Account
from plexus_dashboard.api.models.experiment import Experiment
from plexus_dashboard.api.models.score import Score
from plexus_dashboard.api.models.scorecard import Scorecard
from plexus_dashboard.api.models.score_result import ScoreResult

logger = logging.getLogger(__name__)

SCORE_GOALS = ['sensitivity', 'precision', 'balanced']
POSSIBLE_CLASSES = [
    "3rd Party Clinic", "Agent calling for a Patient", "Follow-up Appointment",
    "New Patient Registration", "Insurance Verification", "Patient Referral",
    "Lab Results Inquiry", "Medication Refill Request", "Appointment Cancellation",
    "Telehealth Consultation", "Patient Feedback", "Emergency Contact",
    "Billing Inquiry", "Health Record Request"
]

def generate_class_distribution(num_classes: int, total_items: int, balanced: bool) -> list:
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
    
    selected_classes = random.sample(POSSIBLE_CLASSES, num_classes)
    
    return [
        {"label": label, "count": count}
        for label, count in zip(selected_classes, counts)
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