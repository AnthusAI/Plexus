# Plexus Classifier Interface Standard

Scoring models in Plexus follow a uniform interface standard based on the MLFlow `pyfunc` standard.  This standard is designed to ensure that all scoring models in Plexus have a consistent interface, regardless of the model type or the specific implementation.  Using a standard interface enables mixing and matching different types of classifiers in one scorecard.

## MLFlow `pyfunc` Standard

MLFlow provides a unified approach for creating and managing custom MLflow models. This interface standard allows any model to be integrated into the MLFlow model registry using `mlflow.pyfunc.log_model()`. At runtime, these models can be retrieved with `mlflow.pyfunc.load_model()` for inference. This standard interface ensures consistency in sending transcript text to the model and receiving responses, whether dealing with a machine learning model, an agentic LLM score, or a programmatic model, as demonstrated in the first example of the provided [guide](https://mlflow.org/blog/custom-pyfunc). For more detailed information, refer to the [documentation](https://mlflow.org/docs/latest/python_api/mlflow.pyfunc.html) for `mlflow.pyfunc`.

## Details

The specific details of the standard are:

### `predict()` is required

Every `Score` in Plexus derives from `mlflow.pyfunc.PythonModel` and must implement a `predict()` method.

### `predict()` must accept a `Input`

This method must accept a `Input` object instance.  The `Input` classis defined in the `plexus.MLClassifier` module.

### `predict()` must return a `Result`

The `predict()` method must return a `Result`.  The `Result` is defined in the `plexus.MLClassifier` module, and each classifier can optionally define additional `Result` subclasses to support additional features.