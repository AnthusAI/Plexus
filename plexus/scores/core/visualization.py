import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc, precision_recall_curve
from sklearn.preprocessing import LabelBinarizer
import mlflow
from plexus.CustomLogging import logging
import matplotlib.ticker as ticker

class ScoreVisualization:

    def _plot_confusion_matrix(self):
        """
        Generate and save a confusion matrix plot.
        """
        file_name = self.report_file_name("confusion_matrix.png")

        all_classes = set(self.label_map.values())
        all_classes.update(set(self.val_labels))
        all_classes.update(set(self.val_predictions))
        
        all_classes = set(str(label) for label in all_classes)
        
        sorted_labels = sorted(all_classes)
        
        label_to_int = {label: i for i, label in enumerate(sorted_labels)}
        logging.info(f"Label to int mapping: {label_to_int}")

        val_labels_int = np.array([label_to_int[str(label)] for label in self.val_labels])
        val_predictions_int = np.array([label_to_int[str(pred)] for pred in self.val_predictions])

        relevant_labels = [label_to_int[label] for label in self.label_map.keys()]
        logging.info(f"Relevant labels: {relevant_labels}")
        cm = confusion_matrix(val_labels_int, val_predictions_int, labels=relevant_labels)
        
        plt.figure(figsize=(10, 8))
        custom_colormap = sns.light_palette(self._fuchsia, as_cmap=True)
        sns.heatmap(cm, annot=True, fmt='d', cmap=custom_colormap, 
                    xticklabels=list(self.label_map.keys()), yticklabels=list(self.label_map.keys()))
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.title('Confusion Matrix')

        plt.tight_layout()
        plt.savefig(file_name, dpi=300)
        plt.close()

        mlflow.log_artifact(file_name)
        
        cm_text = np.array2string(cm, separator=', ')
        logging.info(f"Confusion matrix: {cm_text}")

        class_distribution = Counter(self.val_labels)
        logging.info(f"Class distribution in validation set: {dict(class_distribution)}")

    def _plot_roc_curve(self):
        """
        Generate and save a ROC curve plot.
        """
        file_name = self.report_file_name("roc_curve.png")

        all_classes = set(self.label_map.values())
        all_classes.update(set(self.val_labels))
        all_classes.update(set(self.val_predictions))
        
        all_classes = set(str(label) for label in all_classes)
        
        sorted_labels = sorted(all_classes)
        
        label_to_int = {label: i for i, label in enumerate(sorted_labels)}

        val_labels_int = np.array([label_to_int[str(label)] for label in self.val_labels])

        if self.val_confidence_scores.ndim == 2:
            if self.val_confidence_scores.shape[1] == 1:
                val_confidence_scores = self.val_confidence_scores.ravel()
            else:
                positive_class_index = self.label_map['Yes']
                val_confidence_scores = self.val_confidence_scores[:, positive_class_index]
        else:
            val_confidence_scores = self.val_confidence_scores

        pos_label = label_to_int['Yes']

        fpr, tpr, _ = roc_curve(val_labels_int, val_confidence_scores, pos_label=pos_label)
        roc_auc = auc(fpr, tpr)

        plt.figure(figsize=(10, 8))
        plt.plot(fpr, tpr, color=self._fuchsia, lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
        plt.plot([0, 1], [0, 1], color=self._sky_blue, lw=2, linestyle='--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC) Curve')
        plt.legend(loc="lower right")
        plt.savefig(file_name)
        plt.close()

        mlflow.log_artifact(file_name)
        mlflow.log_metric("roc_auc", roc_auc)

        logging.info(f"Number of unique labels: {len(sorted_labels)}")
        logging.info(f"Shape of val_confidence_scores: {val_confidence_scores.shape}")
        logging.info(f"Shape of val_labels_int: {val_labels_int.shape}")
        logging.info(f"label_to_int mapping: {label_to_int}")

    def _plot_precision_recall_curve(self):
        """
        Generate and save a precision-recall curve plot.
        """
        file_name = self.report_file_name("precision_and_recall_curve.png")

        plt.figure()

        all_classes = set(self.label_map.values())
        all_classes.update(set(self.val_labels))
        all_classes.update(set(self.val_predictions))
        
        all_classes = set(str(label) for label in all_classes)
        
        sorted_labels = sorted(all_classes)
        
        label_to_int = {label: i for i, label in enumerate(sorted_labels)}

        val_labels_int = np.array([label_to_int[str(label)] for label in self.val_labels])
        val_predictions_int = np.array([label_to_int[str(pred)] for pred in self.val_predictions])

        valid_indices = (val_labels_int != -1) & (val_predictions_int != -1)
        val_labels_int = val_labels_int[valid_indices]
        val_predictions_int = val_predictions_int[valid_indices]
        val_confidence_scores = self.val_confidence_scores[valid_indices]

        if self._is_multi_class:
            lb = LabelBinarizer()
            val_labels_one_hot = lb.fit_transform(val_labels_int)
            
            if val_confidence_scores.ndim == 1:
                temp_scores = np.zeros((len(val_confidence_scores), len(label_to_int)))
                temp_scores[np.arange(len(val_predictions_int)), val_predictions_int] = val_confidence_scores
                val_confidence_scores = temp_scores

            n_classes = val_labels_one_hot.shape[1]
            for i in range(n_classes):
                precision, recall, _ = precision_recall_curve(val_labels_one_hot[:, i], val_confidence_scores[:, i])
                pr_auc = auc(recall, precision)
                class_label = list(label_to_int.keys())[list(label_to_int.values()).index(i)]
                plt.plot(recall, precision, lw=2, label=f'Class {class_label} (area = {pr_auc:0.2f})')
        else:
            # Convert binary labels to 0 and 1
            val_labels_binary = (val_labels_int == label_to_int['Yes']).astype(int)
            precision, recall, _ = precision_recall_curve(val_labels_binary, val_confidence_scores)
            pr_auc = auc(recall, precision)
            plt.plot(recall, precision, color=self._sky_blue, lw=2, label='PR curve (area = %0.2f)' % pr_auc)

        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall curve')
        plt.legend(loc="lower left")
        plt.savefig(file_name)
        plt.close()
        mlflow.log_artifact(file_name)
    def _plot_training_history(self):
        """
        Plot and save the training history of the model.

        This method generates a plot of the training history, including learning rate, loss, and accuracy over epochs.
        The plot is saved as a PNG file in the report directory.

        Returns
        -------
        None
        """
        file_name = self.report_file_name("training_history.png")

        plt.figure(figsize=(12, 9))  # Adjusted for a 4x3 aspect ratio with three subplots

        plt.suptitle(f"Training History\n{self.parameters.score_name}", fontsize=16, verticalalignment='top')

        # Learning Rate plot
        plt.subplot(1, 3, 1)  # First subplot for learning rate
        plt.plot(self.history.history['lr'], label='Learning Rate', color=self._fuchsia, lw=4)
        plt.title('Learning Rate')
        plt.ylabel('Learning Rate')
        plt.xlabel('Epoch')
        plt.legend(loc='upper right')
        plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        plt.gca().set_xticklabels(range(1, len(self.history.history['lr']) + 1))

        # Loss plot
        plt.subplot(1, 3, 2)  # Second subplot for loss
        plt.plot(self.history.history['loss'], label='Train Loss', color=self._sky_blue, lw=4)
        plt.plot(self.history.history['val_loss'], label='Validation Loss', color=self._fuchsia, lw=4)
        plt.title('Model Loss')
        plt.ylabel('Loss')
        plt.xlabel('Epoch')
        plt.yscale('log')  # Logarithmic scale for loss
        plt.legend(loc='upper right')
        plt.gca().xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        plt.gca().set_xticklabels(range(1, len(self.history.history['loss']) + 1))

        # Set the loss y-axis to have a fixed locator so it only shows specific ticks, and format them properly.
        plt.gca().yaxis.set_major_locator(ticker.FixedLocator(np.logspace(np.log10(plt.ylim()[0]), np.log10(plt.ylim()[1]), num=5)))
        plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: '{:.2g}'.format(y)))

        # Accuracy plot
        plt.subplot(1, 3, 3)  # Third subplot for accuracy
        plt.plot(self.history.history['accuracy'], label='Train Accuracy', color=self._sky_blue, lw=4)
        plt.plot(self.history.history['val_accuracy'], label='Validation Accuracy', color=self._fuchsia, lw=4)
        plt.title('Model Accuracy')
        plt.ylabel('Accuracy (%)')
        plt.xlabel('Epoch')
        plt.legend(loc='lower right')
        plt.ylim(0.45, 1.0)  # Adjust based on your model's accuracy range
        # Adjust y-axis to show percentages, and format them properly.
        plt.gca().yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0, decimals=0))
        plt.gca().set_xticklabels(range(1, len(self.history.history['accuracy']) + 1))

        # Add horizontal line and label for final validation accuracy
        final_val_accuracy = self.history.history['val_accuracy'][-1]
        plt.axhline(y=final_val_accuracy, color='gray', linestyle='--', lw=2)
        plt.text(len(self.history.history['val_accuracy']) - 1, final_val_accuracy, f'{final_val_accuracy:.3%}', 
                 color='black', ha='right', va='bottom')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(file_name)
        # plt.show()
        mlflow.log_artifact(file_name)

    def _plot_calibration_curve(self, *, target_accuracy=0.90):
        """
        Plot and save the calibration curve of the model.

        This method generates a calibration curve, showing the accuracy of predictions by confidence bucket.
        The plot is saved as a PNG file in the report directory.

        Parameters
        ----------
        target_accuracy : float, optional
            The target accuracy for determining the confidence threshold, by default 0.90

        Returns
        -------
        None
        """
        file_name = self.report_file_name("calibration_curve.png")

        confidences = self.val_confidence_scores.flatten()
        predicted_labels = self.val_predictions
        true_labels = self.val_labels

        logging.info(f"Calibration curve - Unique values in predicted_labels: {set(predicted_labels)}")
        logging.info(f"Calibration curve - Unique values in true_labels: {set(true_labels)}")
        logging.info(f"Calibration curve - label_map: {self.label_map}")

        # Ensure all classes are represented
        all_classes = set(self.label_map.values())
        all_classes.update(set(true_labels))
        all_classes.update(set(predicted_labels))
        
        # Convert all labels to strings
        all_classes = set(str(label) for label in all_classes)
        
        # Create a sorted list of unique labels
        sorted_labels = sorted(all_classes)
        
        # Create label_to_int mapping
        label_to_int = {label: i for i, label in enumerate(sorted_labels)}

        logging.info(f"Calibration curve - label_to_int dictionary: {label_to_int}")

        try:
            predicted_labels_numeric = np.array([label_to_int[str(label)] for label in predicted_labels])
            true_labels_numeric = np.array([label_to_int[str(label)] for label in true_labels])
        except KeyError as e:
            logging.error(f"KeyError encountered: {e}")
            logging.error(f"Label causing the error: {e.args[0]}")
            logging.error(f"All unique labels in predicted_labels: {set(predicted_labels)}")
            logging.error(f"All unique labels in true_labels: {set(true_labels)}")
            raise

        def find_confidence_threshold(confidences, true_labels, predicted_labels, target_accuracy):
            sorted_indices = np.argsort(confidences)
            sorted_confidences = confidences[sorted_indices]
            sorted_true_labels = true_labels[sorted_indices]
            sorted_predicted_labels = predicted_labels[sorted_indices]
            
            for i in range(len(sorted_confidences)):
                remaining_accuracy = np.mean(sorted_predicted_labels[i:] == sorted_true_labels[i:])
                if remaining_accuracy >= target_accuracy:
                    return sorted_confidences[i]
            
            return sorted_confidences[-1]  # Return the highest confidence if target not achievable

        confidence_threshold = find_confidence_threshold(confidences, true_labels_numeric, predicted_labels_numeric, target_accuracy)

        sorted_indices = np.argsort(confidences)
        sorted_confidences = confidences[sorted_indices]
        sorted_predictions = predicted_labels_numeric[sorted_indices]
        sorted_true_labels = true_labels_numeric[sorted_indices]

        n = len(confidences)
        bucket_sizes = [n // 6, n // 3, n - (n // 6) - (n // 3)]

        buckets = []
        start_index = 0
        for size in bucket_sizes:
            end_index = start_index + size

            bucket_confidences = sorted_confidences[start_index:end_index]
            bucket_predictions = sorted_predictions[start_index:end_index]
            bucket_true_labels = sorted_true_labels[start_index:end_index]

            bucket_accuracy = np.mean(bucket_predictions == bucket_true_labels)
            bucket_mean_confidence = np.mean(bucket_confidences)

            buckets.append((bucket_mean_confidence, bucket_accuracy, len(bucket_predictions)))

            start_index = end_index

        plt.figure(figsize=(10, 8))
        plt.plot([0, 1], [0, 1], linestyle='--', color=self._sky_blue, label='Perfectly calibrated')

        bucket_confidences, bucket_accuracies, bucket_sample_counts = zip(*buckets)
        plt.plot(bucket_confidences, bucket_accuracies, label='Model calibration', marker='o', color=self._fuchsia)

        plt.axvline(x=confidence_threshold, color='blue', linestyle='-', label=f'Confidence threshold ({confidence_threshold:.2%})')

        plt.xlabel('Confidence')
        plt.ylabel('Accuracy')
        plt.title('Calibration Curve: Accuracy by Confidence Bucket')
        plt.legend(loc='lower right')

        x_ticks = np.arange(0, 1.1, 0.1)
        plt.xticks(x_ticks)
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.0%}"))

        y_ticks = np.arange(0, 1.1, 0.1)
        plt.yticks(y_ticks)
        plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, p: f"{y:.0%}"))

        plt.ylim(0, 1)
        plt.xlim(0, 1)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.savefig(file_name)
        mlflow.log_artifact(file_name)

        print("\nOverall statistics:")
        print(f"Total samples: {len(confidences)}")
        print(f"Min confidence: {np.min(confidences):.2%}")
        print(f"Max confidence: {np.max(confidences):.2%}")
        print(f"Mean confidence: {np.mean(confidences):.2%}")
        print(f"Overall accuracy: {np.mean(predicted_labels_numeric == true_labels_numeric)::.2%}")
        print(f"\nConfidence threshold for {target_accuracy:.0%} accuracy: {confidence_threshold:.2%}")
        print(f"Predictions above threshold: {np.sum(confidences > confidence_threshold)}")
        print(f"Predictions at or below threshold: {np.sum(confidences <= confidence_threshold)}")
        remaining_predictions = confidences > confidence_threshold
        remaining_accuracy = np.mean(predicted_labels_numeric[remaining_predictions] == true_labels_numeric[remaining_predictions])
        print(f"Accuracy of predictions above threshold: {remaining_accuracy:.2%}")
        predictions_below_threshold = np.sum(confidences <= confidence_threshold)
        percentage_below_threshold = predictions_below_threshold / len(confidences) * 100
        print(f"Percentage of predictions below threshold: {percentage_below_threshold:.2f}%")

        plt.figure(figsize=(10, 6))
        plt.hist(confidences, bins=20, edgecolor='black')
        plt.title('Distribution of Confidences')
        plt.xlabel('Confidence')
        plt.ylabel('Count')
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.0%}"))
        plt.savefig(self.report_file_name("confidence_distribution.png"))
        mlflow.log_artifact(self.report_file_name("confidence_distribution.png"))

        print("\nBucket details:")
        for i, (conf, acc, count) in enumerate(buckets):
            print(f"Bucket {i+1}:")
            print(f"  Confidence range: {conf:.2%}")
            print(f"  Mean confidence: {conf:.2%}")
            print(f"  Accuracy: {acc:.2%}")
            print(f"  Number of samples: {count}")