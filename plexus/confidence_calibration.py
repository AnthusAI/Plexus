#!/usr/bin/env python3
"""
Confidence calibration utilities for Plexus evaluations.

Implements isotonic regression calibration as described in:
https://github.com/AnthusAI/Classification-with-Confidence
"""
import logging
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Any, Optional
from sklearn.isotonic import IsotonicRegression
from sklearn.calibration import calibration_curve
from scipy.optimize import minimize_scalar


logger = logging.getLogger(__name__)


def extract_confidence_accuracy_pairs(evaluation_results: List[Dict[str, Any]]) -> Tuple[List[float], List[int]]:
    """
    Extract confidence scores and accuracy labels from evaluation results.

    Args:
        evaluation_results: List of evaluation results from Plexus

    Returns:
        Tuple of (confidence_scores, accuracy_labels) where:
        - confidence_scores: List of confidence values (0.0 to 1.0)
        - accuracy_labels: List of binary accuracy labels (1 for correct, 0 for incorrect)
    """
    confidence_scores = []
    accuracy_labels = []

    for result in evaluation_results:
        # Check if this result has confidence information
        if not isinstance(result, dict):
            continue

        # Look for confidence in the result structure
        confidence = None
        is_correct = None

        # Handle different result structures
        if 'scores' in result:
            # MCP-style result structure
            for score_result in result.get('scores', []):
                if isinstance(score_result, dict) and 'confidence' in score_result:
                    confidence = score_result.get('confidence')
                    # Determine correctness from metadata if available
                    if 'metadata' in score_result:
                        is_correct = score_result['metadata'].get('correct', None)
                    break
        elif 'confidence' in result:
            # Direct confidence in result
            confidence = result.get('confidence')
            is_correct = result.get('correct', result.get('metadata', {}).get('correct'))
        elif 'results' in result:
            # YAML evaluation nested structure
            for score_name, score_result_obj in result.get('results', {}).items():
                # Handle Result objects (YAML evaluation format)
                if hasattr(score_result_obj, 'confidence'):
                    confidence = getattr(score_result_obj, 'confidence', None)
                    # Look for correctness - check if the result has metadata or correct attribute
                    if hasattr(score_result_obj, 'metadata'):
                        metadata = getattr(score_result_obj, 'metadata', {})
                        is_correct = metadata.get('correct', None) if isinstance(metadata, dict) else None
                    elif hasattr(score_result_obj, 'correct'):
                        is_correct = getattr(score_result_obj, 'correct', None)
                    # Also check in the parent result structure for human labels
                    if is_correct is None and 'human_labels' in result:
                        human_labels = result.get('human_labels', {})
                        predicted_value = getattr(score_result_obj, 'value', None)
                        if score_name in human_labels and predicted_value is not None:
                            human_label = human_labels[score_name]
                            is_correct = (str(predicted_value).lower() == str(human_label).lower())
                    break
                # Also check if it's a dict with confidence
                elif isinstance(score_result_obj, dict) and 'confidence' in score_result_obj:
                    confidence = score_result_obj.get('confidence')
                    # Look for correctness in metadata
                    metadata = score_result_obj.get('metadata', {})
                    is_correct = metadata.get('correct', None)
                    break

        # Skip if we don't have both confidence and correctness
        if confidence is None or is_correct is None:
            continue

        # Ensure confidence is a valid float
        try:
            confidence_float = float(confidence)
            if 0.0 <= confidence_float <= 1.0:
                confidence_scores.append(confidence_float)
                accuracy_labels.append(1 if is_correct else 0)
        except (ValueError, TypeError):
            logger.warning(f"Invalid confidence value: {confidence}")
            continue

    logger.info(f"Extracted {len(confidence_scores)} confidence-accuracy pairs for calibration")
    return confidence_scores, accuracy_labels


def apply_temperature_scaling(confidence_scores: List[float], temperature: float) -> List[float]:
    """
    Apply temperature scaling to confidence scores.

    Temperature scaling applies a single parameter T to logits before applying softmax:
    P_calibrated = softmax(logit / T)

    For confidence scores (already probabilities), we convert back to logits,
    apply temperature scaling, then convert back to probabilities.

    Args:
        confidence_scores: List of raw confidence scores (0.0 to 1.0)
        temperature: Temperature parameter (T > 1 decreases confidence, T < 1 increases)

    Returns:
        List of temperature-scaled confidence scores
    """
    if temperature <= 0:
        raise ValueError("Temperature must be positive")

    # Convert probabilities to logits (assuming binary classification)
    # For a probability p, logit = log(p / (1-p))
    # For temperature scaling: scaled_logit = logit / T
    # Then: p_scaled = 1 / (1 + exp(-scaled_logit))

    scaled_scores = []
    for prob in confidence_scores:
        # Clip probability to avoid log(0) or log(inf)
        prob = max(1e-7, min(1 - 1e-7, prob))

        # Convert to logit
        logit = np.log(prob / (1 - prob))

        # Apply temperature scaling
        scaled_logit = logit / temperature

        # Convert back to probability
        scaled_prob = 1 / (1 + np.exp(-scaled_logit))
        scaled_scores.append(scaled_prob)

    return scaled_scores


def find_optimal_temperature(confidence_scores: List[float],
                           accuracy_labels: List[int],
                           method: str = "minimize_scalar") -> float:
    """
    Find optimal temperature parameter to minimize Expected Calibration Error (ECE).

    Args:
        confidence_scores: List of raw confidence scores (0.0 to 1.0)
        accuracy_labels: List of binary accuracy labels (1 for correct, 0 for incorrect)
        method: Optimization method - "minimize_scalar" or "grid_search"

    Returns:
        Optimal temperature parameter
    """
    if len(confidence_scores) < 10:
        logger.warning(f"Insufficient data for temperature optimization: {len(confidence_scores)} samples")
        return 1.0  # Default temperature (no scaling)

    confidences = np.array(confidence_scores)
    accuracies = np.array(accuracy_labels)

    def objective(temperature):
        """Objective function to minimize - returns ECE for given temperature"""
        try:
            temp_scaled_scores = apply_temperature_scaling(confidence_scores, temperature)
            temp_scaled_array = np.array(temp_scaled_scores)
            ece = expected_calibration_error(temp_scaled_array, accuracies, n_bins=10)
            return ece
        except Exception as e:
            logger.warning(f"Error computing ECE for temperature {temperature}: {e}")
            return float('inf')

    try:
        if method == "grid_search":
            # Grid search over temperature range
            temperatures = np.logspace(-1, 1, 21)  # 0.1 to 10.0, 21 points
            best_temp = 1.0
            best_ece = float('inf')

            for temp in temperatures:
                ece = objective(temp)
                if ece < best_ece:
                    best_ece = ece
                    best_temp = temp

            logger.info(f"Grid search found optimal temperature: {best_temp:.4f} (ECE: {best_ece:.4f})")
            return best_temp

        else:  # minimize_scalar
            # Use scipy's minimize_scalar for more precise optimization
            result = minimize_scalar(objective, bounds=(0.1, 10.0), method='bounded')

            if result.success:
                optimal_temp = result.x
                optimal_ece = result.fun
                logger.info(f"Optimization found optimal temperature: {optimal_temp:.4f} (ECE: {optimal_ece:.4f})")
                return optimal_temp
            else:
                logger.warning("Temperature optimization failed, using default temperature 1.0")
                return 1.0

    except Exception as e:
        logger.error(f"Error in temperature optimization: {e}")
        return 1.0


def compute_isotonic_regression_calibration(confidence_scores: List[float],
                                          accuracy_labels: List[int]) -> Optional[IsotonicRegression]:
    """
    Compute isotonic regression calibration curve.

    Args:
        confidence_scores: List of raw confidence scores (0.0 to 1.0)
        accuracy_labels: List of binary accuracy labels (1 for correct, 0 for incorrect)

    Returns:
        Fitted IsotonicRegression model, or None if insufficient data
    """
    if len(confidence_scores) < 10:
        logger.warning(f"Insufficient data for calibration: {len(confidence_scores)} samples (need at least 10)")
        return None

    try:
        # Convert to numpy arrays
        X = np.array(confidence_scores)
        y = np.array(accuracy_labels)

        # Fit isotonic regression
        iso_reg = IsotonicRegression(out_of_bounds='clip')
        iso_reg.fit(X, y)

        logger.info(f"Successfully fitted isotonic regression calibration with {len(confidence_scores)} samples")
        return iso_reg

    except Exception as e:
        logger.error(f"Error computing isotonic regression calibration: {e}")
        return None


def compute_two_stage_calibration(confidence_scores: List[float],
                                accuracy_labels: List[int]) -> Tuple[float, Optional[IsotonicRegression], List[float]]:
    """
    Compute two-stage calibration: temperature scaling followed by isotonic regression.

    Args:
        confidence_scores: List of raw confidence scores (0.0 to 1.0)
        accuracy_labels: List of binary accuracy labels (1 for correct, 0 for incorrect)

    Returns:
        Tuple of (optimal_temperature, isotonic_model, temperature_scaled_scores)
    """
    if len(confidence_scores) < 10:
        logger.warning(f"Insufficient data for two-stage calibration: {len(confidence_scores)} samples")
        return 1.0, None, confidence_scores

    try:
        # Stage 1: Find optimal temperature
        logger.info("Stage 1: Optimizing temperature scaling...")
        optimal_temperature = find_optimal_temperature(confidence_scores, accuracy_labels)

        # Apply temperature scaling
        temp_scaled_scores = apply_temperature_scaling(confidence_scores, optimal_temperature)
        logger.info(f"Applied temperature scaling with T={optimal_temperature:.4f}")

        # Stage 2: Apply isotonic regression to temperature-scaled scores
        logger.info("Stage 2: Applying isotonic regression to temperature-scaled scores...")
        isotonic_model = compute_isotonic_regression_calibration(temp_scaled_scores, accuracy_labels)

        if isotonic_model is not None:
            logger.info("Two-stage calibration completed successfully")
        else:
            logger.warning("Isotonic regression failed in two-stage calibration")

        return optimal_temperature, isotonic_model, temp_scaled_scores

    except Exception as e:
        logger.error(f"Error in two-stage calibration: {e}")
        return 1.0, None, confidence_scores


def serialize_calibration_model(calibration_model: IsotonicRegression) -> Dict[str, Any]:
    """
    Serialize calibration model for storage in YAML/JSON.

    Args:
        calibration_model: Fitted isotonic regression model

    Returns:
        Dictionary containing serialized calibration data
    """
    try:
        # Extract the calibration mapping from the isotonic regression model
        # Sample points across the confidence range to create a lookup table
        test_points = np.linspace(0, 1, 101)  # 0.00, 0.01, 0.02, ..., 1.00
        calibrated_points = calibration_model.predict(test_points)

        return {
            "method": "isotonic_regression",
            "raw_confidence": test_points.tolist(),
            "calibrated_confidence": calibrated_points.tolist(),
            "x_min": float(calibration_model.X_min_),
            "x_max": float(calibration_model.X_max_),
            "y_min": float(calibration_model.y_min_),
            "y_max": float(calibration_model.y_max_)
        }
    except Exception as e:
        logger.error(f"Error serializing calibration model: {e}")
        return {"error": f"Failed to serialize calibration model: {str(e)}"}


def apply_calibration_from_serialized(raw_confidence: float,
                                    calibration_data: Dict[str, Any]) -> float:
    """
    Apply calibration using serialized calibration data.

    Args:
        raw_confidence: Raw confidence score (0.0 to 1.0)
        calibration_data: Serialized calibration data

    Returns:
        Calibrated confidence score
    """
    if not calibration_data or calibration_data.get("method") != "isotonic_regression":
        return raw_confidence

    try:
        raw_points = np.array(calibration_data["raw_confidence"])
        calibrated_points = np.array(calibration_data["calibrated_confidence"])

        # Interpolate to find calibrated value
        calibrated_confidence = np.interp(raw_confidence, raw_points, calibrated_points)

        # Ensure bounds
        calibrated_confidence = max(0.0, min(1.0, float(calibrated_confidence)))

        return calibrated_confidence

    except Exception as e:
        logger.warning(f"Error applying calibration: {e}")
        return raw_confidence


def generate_calibration_report(confidence_scores: List[float],
                              accuracy_labels: List[int],
                              calibration_model: Optional[IsotonicRegression] = None) -> Dict[str, Any]:
    """
    Generate a calibration analysis report.

    Args:
        confidence_scores: Raw confidence scores
        accuracy_labels: Binary accuracy labels
        calibration_model: Optional fitted calibration model

    Returns:
        Dictionary containing calibration metrics and analysis
    """
    if len(confidence_scores) == 0:
        return {"error": "No confidence scores available for calibration analysis"}

    try:
        # Convert to numpy arrays
        X = np.array(confidence_scores)
        y = np.array(accuracy_labels)

        # Calculate basic statistics
        report = {
            "total_samples": len(confidence_scores),
            "confidence_stats": {
                "mean": float(np.mean(X)),
                "std": float(np.std(X)),
                "min": float(np.min(X)),
                "max": float(np.max(X)),
                "median": float(np.median(X))
            },
            "accuracy_stats": {
                "overall_accuracy": float(np.mean(y)),
                "total_correct": int(np.sum(y)),
                "total_incorrect": int(len(y) - np.sum(y))
            }
        }

        # Calculate reliability curve (calibration curve)
        if len(set(y)) > 1:  # Need both correct and incorrect samples
            fraction_of_positives, mean_predicted_value = calibration_curve(
                y, X, n_bins=min(10, len(confidence_scores) // 10 + 1)
            )

            report["reliability_curve"] = {
                "mean_predicted_values": mean_predicted_value.tolist(),
                "fraction_of_positives": fraction_of_positives.tolist()
            }

            # Calculate Expected Calibration Error (ECE)
            bin_boundaries = np.linspace(0, 1, len(mean_predicted_value) + 1)
            bin_lowers = bin_boundaries[:-1]
            bin_uppers = bin_boundaries[1:]

            ece = 0
            for bin_lower, bin_upper, mean_pred, frac_pos in zip(
                bin_lowers, bin_uppers, mean_predicted_value, fraction_of_positives
            ):
                # Find samples in this bin
                in_bin = (X > bin_lower) & (X <= bin_upper)
                prop_in_bin = in_bin.mean()

                if prop_in_bin > 0:
                    ece += np.abs(mean_pred - frac_pos) * prop_in_bin

            report["expected_calibration_error"] = float(ece)

        # Add calibration model info if provided
        if calibration_model is not None:
            # Test calibration on some sample points
            test_points = np.linspace(0, 1, 21)  # 0.0, 0.05, 0.1, ..., 1.0
            calibrated_points = calibration_model.predict(test_points)

            report["calibration_mapping"] = {
                "raw_confidence": test_points.tolist(),
                "calibrated_confidence": calibrated_points.tolist()
            }

        return report

    except Exception as e:
        logger.error(f"Error generating calibration report: {e}")
        return {"error": f"Failed to generate calibration report: {str(e)}"}


def detect_confidence_feature_enabled(evaluation_results: List[Dict[str, Any]]) -> bool:
    """
    Detect if the confidence feature is enabled in evaluation results.

    Args:
        evaluation_results: List of evaluation results

    Returns:
        True if confidence values are present, False otherwise
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"Checking confidence detection on {len(evaluation_results)} results")

    for i, result in enumerate(evaluation_results):
        if not isinstance(result, dict):
            logger.debug(f"Result {i} is not a dict: {type(result)}")
            continue

        logger.info(f"Result {i} keys: {list(result.keys())}")
        # Show the structure of the first result in detail
        if i == 0:
            logger.info(f"First result sample structure: {result}")
        if i < 3:  # Show first 3 results structure
            logger.info(f"Result {i} structure sample: {str(result)[:500]}")

        # Check for confidence in various result structures
        if 'scores' in result:
            logger.debug(f"Result {i} has 'scores' key")
            for j, score_result in enumerate(result.get('scores', [])):
                if isinstance(score_result, dict) and 'confidence' in score_result:
                    confidence = score_result.get('confidence')
                    logger.info(f"Found confidence in result {i}, score {j}: {confidence}")
                    if confidence is not None:
                        try:
                            confidence_float = float(confidence)
                            if 0.0 <= confidence_float <= 1.0:
                                logger.info(f"Valid confidence found: {confidence_float}")
                                return True
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid confidence value: {confidence}")
                            continue
        elif 'confidence' in result:
            confidence = result.get('confidence')
            logger.info(f"Found direct confidence in result {i}: {confidence}")
            if confidence is not None:
                try:
                    confidence_float = float(confidence)
                    if 0.0 <= confidence_float <= 1.0:
                        logger.info(f"Valid direct confidence found: {confidence_float}")
                        return True
                except (ValueError, TypeError):
                    logger.warning(f"Invalid direct confidence value: {confidence}")
                    continue
        # Check for nested results structure (YAML evaluation format)
        elif 'results' in result:
            logger.debug(f"Result {i} has 'results' key - checking nested structure")
            for score_name, score_result_obj in result.get('results', {}).items():
                # Handle Result objects (YAML evaluation format)
                if hasattr(score_result_obj, 'confidence'):
                    confidence = getattr(score_result_obj, 'confidence', None)
                    logger.info(f"Found confidence attribute in result {i}, score '{score_name}': {confidence}")
                    if confidence is not None:
                        try:
                            confidence_float = float(confidence)
                            if 0.0 <= confidence_float <= 1.0:
                                logger.info(f"Valid confidence found in Result object: {confidence_float}")
                                return True
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid confidence value in Result object: {confidence}")
                            continue
                # Also check if it's a dict with confidence
                elif isinstance(score_result_obj, dict) and 'confidence' in score_result_obj:
                    confidence = score_result_obj.get('confidence')
                    logger.info(f"Found confidence in result {i}, score '{score_name}': {confidence}")
                    if confidence is not None:
                        try:
                            confidence_float = float(confidence)
                            if 0.0 <= confidence_float <= 1.0:
                                logger.info(f"Valid confidence found in nested structure: {confidence_float}")
                                return True
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid confidence value in nested structure: {confidence}")
                            continue
                else:
                    logger.debug(f"Score result object in {i}/{score_name} has no confidence: {type(score_result_obj)}")
        else:
            logger.debug(f"Result {i} has no confidence data in expected locations")

    logger.warning("No confidence data found in any result")
    return False


def plot_reliability_diagram(confidence_scores: List[float],
                            accuracy_labels: List[int],
                            save_path: str,
                            title: str = "Confidence Calibration - Reliability Diagram",
                            n_bins: int = 20,
                            temperature_scaled_scores: List[float] = None,
                            calibrated_confidence_scores: List[float] = None) -> None:
    """
    Plot reliability diagram showing calibration quality with confidence buckets.
    Can show raw, temperature-scaled, and final calibrated confidence scores for comparison.

    Perfect calibration appears as points on the diagonal line.
    Points above the line = overconfident, below = underconfident.

    Args:
        confidence_scores: List of raw confidence scores (0.0 to 1.0)
        accuracy_labels: List of binary accuracy labels (1 for correct, 0 for incorrect)
        save_path: Path to save the plot image
        title: Plot title
        n_bins: Number of confidence bins (default 20 for 5% buckets)
        temperature_scaled_scores: Optional list of temperature-scaled confidence scores
        calibrated_confidence_scores: Optional list of final calibrated confidence scores
    """
    if len(confidence_scores) == 0:
        logger.warning("No confidence scores provided for reliability diagram")
        return

    try:
        # Convert to numpy arrays
        confidences = np.array(confidence_scores)
        accuracies = np.array(accuracy_labels)

        # Create bins (20 bins = 5% buckets)
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        bin_lowers = bin_boundaries[:-1]
        bin_uppers = bin_boundaries[1:]

        bin_confidences = []
        bin_accuracies = []
        bin_counts = []

        for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
            in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
            if in_bin.sum() > 0:
                bin_confidences.append(confidences[in_bin].mean())
                bin_accuracies.append(accuracies[in_bin].mean())
                bin_counts.append(in_bin.sum())

        # Create the plot with styling from Classification-with-Confidence
        fig, ax = plt.subplots(figsize=(12, 10))

        # Show actual confidence buckets used in the calculation
        bins_with_data = set()
        for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
            in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
            if in_bin.sum() > 0:
                bins_with_data.add((bin_lower, bin_upper))

        # Draw bucket regions - different colors for populated vs empty buckets
        for i, (bin_lower, bin_upper) in enumerate(zip(bin_lowers, bin_uppers)):
            has_data = (bin_lower, bin_upper) in bins_with_data

            if has_data:
                # Populated bucket - light blue background
                color = 'lightblue'
                alpha = 0.15
                edge_color = 'blue'
                edge_alpha = 0.3
            else:
                # Empty bucket - light gray background
                color = 'lightgray'
                alpha = 0.1
                edge_color = 'gray'
                edge_alpha = 0.2

            # Draw the bucket region as a rectangle
            rect = plt.Rectangle((bin_lower, bin_lower), bin_upper - bin_lower, bin_upper - bin_lower,
                               facecolor=color, alpha=alpha, edgecolor=edge_color,
                               linewidth=1, linestyle='--')
            ax.add_patch(rect)

            # Add bucket boundary lines
            ax.axvline(bin_lower, color=edge_color, linestyle=':', alpha=edge_alpha, linewidth=1)
            ax.axhline(bin_lower, color=edge_color, linestyle=':', alpha=edge_alpha, linewidth=1)

            # Label the bucket in the center if it has data
            if has_data:
                center_x = (bin_lower + bin_upper) / 2
                center_y = (bin_lower + bin_upper) / 2
                bucket_size = bin_upper - bin_lower
                ax.text(center_x, center_y, f'{bucket_size*100:.0f}%', ha='center', va='center',
                       fontsize=8, alpha=0.6, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='none'))

        # Add final boundary lines
        ax.axvline(1.0, color='blue', linestyle=':', alpha=0.3, linewidth=1)
        ax.axhline(1.0, color='blue', linestyle=':', alpha=0.3, linewidth=1)

        # Perfect calibration line
        ax.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration', alpha=0.8, linewidth=3, zorder=4)

        # Plot raw confidence scores (original data)
        if bin_counts:
            # Color points based on how far they are from perfect calibration
            distances = [abs(conf - acc) for conf, acc in zip(bin_confidences, bin_accuracies)]
            colors = ['red' if d > 0.1 else 'orange' if d > 0.05 else 'green' for d in distances]

            scatter_raw = ax.scatter(bin_confidences, bin_accuracies,
                               s=[count/max(bin_counts)*400 + 150 for count in bin_counts],
                               alpha=0.9, c=colors, edgecolors='black', linewidth=2, zorder=5,
                               label='Raw Confidence (Uncalibrated)', marker='o')

            # Add sample count labels on each point for raw data
            for i, (conf, acc, count) in enumerate(zip(bin_confidences, bin_accuracies, bin_counts)):
                ax.annotate(f'{count}', (conf, acc),
                           xytext=(8, 8), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor='gray'),
                           fontsize=9, fontweight='bold', ha='left')

        # Plot temperature-scaled confidence scores if provided
        if temperature_scaled_scores is not None:
            # Calculate binned stats for temperature-scaled scores
            temp_scaled_confidences = np.array(temperature_scaled_scores)

            temp_bin_confidences = []
            temp_bin_accuracies = []
            temp_bin_counts = []

            for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
                in_bin = (temp_scaled_confidences > bin_lower) & (temp_scaled_confidences <= bin_upper)
                if in_bin.sum() > 0:
                    temp_bin_confidences.append(temp_scaled_confidences[in_bin].mean())
                    temp_bin_accuracies.append(accuracies[in_bin].mean())
                    temp_bin_counts.append(in_bin.sum())

            if temp_bin_counts:
                # Plot temperature-scaled points with triangles, orange
                scatter_temp = ax.scatter(temp_bin_confidences, temp_bin_accuracies,
                                   s=[count/max(temp_bin_counts)*400 + 150 for count in temp_bin_counts],
                                   alpha=0.8, c='orange', edgecolors='darkorange', linewidth=2, zorder=6,
                                   label='Temperature Scaled', marker='^')

                # Add sample count labels for temperature-scaled data
                for i, (conf, acc, count) in enumerate(zip(temp_bin_confidences, temp_bin_accuracies, temp_bin_counts)):
                    ax.annotate(f'{count}', (conf, acc),
                               xytext=(0, 12), textcoords='offset points',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='wheat', alpha=0.9, edgecolor='orange'),
                               fontsize=9, fontweight='bold', ha='center')

        # Plot final calibrated confidence scores if provided
        if calibrated_confidence_scores is not None:
            # Calculate binned stats for calibrated scores
            calibrated_confidences = np.array(calibrated_confidence_scores)

            cal_bin_confidences = []
            cal_bin_accuracies = []
            cal_bin_counts = []

            for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
                in_bin = (calibrated_confidences > bin_lower) & (calibrated_confidences <= bin_upper)
                if in_bin.sum() > 0:
                    cal_bin_confidences.append(calibrated_confidences[in_bin].mean())
                    cal_bin_accuracies.append(accuracies[in_bin].mean())
                    cal_bin_counts.append(in_bin.sum())

            if cal_bin_counts:
                # Plot final calibrated points with squares, blue
                scatter_cal = ax.scatter(cal_bin_confidences, cal_bin_accuracies,
                                   s=[count/max(cal_bin_counts)*400 + 150 for count in cal_bin_counts],
                                   alpha=0.8, c='blue', edgecolors='darkblue', linewidth=2, zorder=7,
                                   label='Final Calibrated (Two-Stage)', marker='s')

                # Add sample count labels for final calibrated data
                for i, (conf, acc, count) in enumerate(zip(cal_bin_confidences, cal_bin_accuracies, cal_bin_counts)):
                    ax.annotate(f'{count}', (conf, acc),
                               xytext=(-8, -8), textcoords='offset points',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.9, edgecolor='blue'),
                               fontsize=9, fontweight='bold', ha='right')

        # Enhanced labels and title
        ax.set_xlabel('Mean Predicted Confidence', fontsize=14, fontweight='bold')
        ax.set_ylabel('Mean Actual Accuracy', fontsize=14, fontweight='bold')
        ax.set_title(f"{title} (n={len(confidence_scores)})", fontsize=16, fontweight='bold', pad=20)

        # Enhanced legend
        ax.legend(fontsize=12, loc='lower right')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        # Add comprehensive calibration info
        from sklearn.calibration import calibration_curve
        fraction_of_positives, mean_predicted_value = calibration_curve(
            accuracies, confidences, n_bins=min(10, len(confidence_scores) // 10 + 1)
        )

        # Calculate Expected Calibration Error (ECE)
        ece = 0
        bin_boundaries_ece = np.linspace(0, 1, len(mean_predicted_value) + 1)
        bin_lowers_ece = bin_boundaries_ece[:-1]
        bin_uppers_ece = bin_boundaries_ece[1:]

        for bin_lower, bin_upper, mean_pred, frac_pos in zip(
            bin_lowers_ece, bin_uppers_ece, mean_predicted_value, fraction_of_positives
        ):
            in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
            prop_in_bin = in_bin.mean()
            if prop_in_bin > 0:
                ece += np.abs(mean_pred - frac_pos) * prop_in_bin

        # Interpretation text
        if ece < 0.05:
            interpretation = "Excellent"
            color = 'green'
        elif ece < 0.10:
            interpretation = "Good"
            color = 'orange'
        else:
            interpretation = "Poor"
            color = 'red'

        info_text = f'ECE: {ece:.3f} ({interpretation})\nSamples: {len(confidence_scores)}'
        ax.text(0.05, 0.95, info_text, transform=ax.transAxes,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor=color, linewidth=2),
                fontsize=12, verticalalignment='top')

        # Add explanation text
        explanation = ("THREE-STAGE CONFIDENCE CALIBRATION:\n"
                      "• Circles = Raw uncalibrated confidence scores\n"
                      "• Triangles = Temperature scaled scores (T-scaling)\n"
                      "• Squares = Final calibrated scores (T-scaling + Isotonic)\n"
                      "• Shape size = number of predictions in that bucket\n"
                      "• Green/Orange/Red = calibration quality (good/fair/poor)\n"
                      "• Perfect calibration = points on diagonal line\n"
                      "• Points above line = overconfident, below = underconfident")
        ax.text(0.98, 0.02, explanation, transform=ax.transAxes,
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.9, edgecolor='navy'),
                fontsize=10, horizontalalignment='right', verticalalignment='bottom', fontweight='bold')

        plt.tight_layout()

        # Save the plot
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()  # Close to free memory

        logger.info(f"Reliability diagram saved to: {save_path}")
        logger.info(f"Expected Calibration Error (ECE): {ece:.4f} ({interpretation})")

    except Exception as e:
        logger.error(f"Error creating reliability diagram: {e}")


def expected_calibration_error(confidences: np.ndarray, accuracies: np.ndarray,
                             n_bins: int = 10) -> float:
    """
    Calculate Expected Calibration Error (ECE).

    ECE measures the average difference between confidence and accuracy
    across different confidence bins. Lower is better (0 = perfect calibration).

    Args:
        confidences: Array of confidence scores [0, 1]
        accuracies: Array of binary correctness [0, 1]
        n_bins: Number of confidence bins to use

    Returns:
        ECE score (lower is better, 0 = perfect calibration)
    """
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]

    ece = 0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        # Find predictions in this confidence bin
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = in_bin.mean()

        if prop_in_bin > 0:
            # Average confidence and accuracy in this bin
            accuracy_in_bin = accuracies[in_bin].mean()
            avg_confidence_in_bin = confidences[in_bin].mean()

            # Add weighted calibration error for this bin
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin

    return ece