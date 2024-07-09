import os
import json
import mlflow
from plexus.CustomLogging import logging
from plexus.scores.core.utils import ensure_report_directory_exists

class ScoreMLFlow:
    @ensure_report_directory_exists
    def record_configuration(self, configuration):
        """
        Record the provided configuration dictionary as a JSON file in the appropriate report folder for this model.

        Parameters
        ----------
        configuration : dict
            Dictionary containing the configuration to be recorded.

        Notes
        -----
        The configuration JSON file can be useful as an artifact for logging in MLFlow.
        """
        file_name = self.report_file_name("configuration.json")

        with open(file_name, 'w') as json_file:
            json.dump(configuration, json_file, indent=4)

    def log_stored_parameters(self):
        """
        Log the stored parameters to MLflow.
        """
        if hasattr(self, '_stored_parameters'):
            for name, value in self.parameters.items():
                mlflow.log_param(name, value)

    def start_mlflow_experiment_run(self):
        """
        Start an MLflow experiment run and log common parameters.
        """
        experiment_name = f"{self.parameters.scorecard_name} - {self.parameters.score_name}"
        if os.getenv('MLFLOW_EXPERIMENT_NAME'):
            experiment_name = experiment_name + " - " + os.getenv('MLFLOW_EXPERIMENT_NAME')
        logging.info(f"Setting MLFLow experiment name to [magenta1][b]{experiment_name}[/b][/magenta1]")
        mlflow.set_experiment(experiment_name)

        mlflow_tracking_uri = os.getenv('MLFLOW_TRACKING_URI')
        if mlflow_tracking_uri:
            logging.info(f"Using MLFlow tracking URL: {mlflow_tracking_uri}")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        else:
            mlflow.set_tracking_uri(f'file:///{os.path.abspath("./mlruns")}')

        try:
            mlflow.start_run()
        except Exception as e:
            logging.error(f"Error: {e}")
            logging.info("Attempting to end the previous run and start a new one.")
            mlflow.end_run()
            mlflow.start_run()

        mlflow.log_param("classifier_class", self.__class__.__name__)

        mlflow.log_param("scorecard_name", self.parameters.scorecard_name)
        mlflow.log_param("score_name", self.parameters.score_name)

        self.log_stored_parameters()

    def log_evaluation_metrics(self, metrics):
        """
        Log evaluation metrics to MLflow.

        Parameters
        ----------
        metrics : dict
            Dictionary containing evaluation metrics.
        """
        mlflow.log_metric("accuracy", metrics["accuracy"])
        mlflow.log_metric("precision", metrics["precision"])
        mlflow.log_metric("recall", metrics["recall"])
        mlflow.log_metric("f1_score", metrics["f1_score"])