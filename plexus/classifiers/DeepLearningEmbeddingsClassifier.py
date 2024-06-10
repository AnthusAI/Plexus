from plexus.classifiers import Classifier, MLClassifier
from pydantic import BaseModel, validator, ValidationError

class DeepLearningEmbeddingsClassifierParameters(MLClassifier.Parameters):
    sliding_window: bool = False
    sliding_window_aggregation: str
    maximum_number_of_sliding_windows: int = 0
    epochs: int
    early_stop_patience: int
    batch_size: int
    warmup_start_learning_rate: float
    warmup_number_of_epochs: int
    plateau_learning_rate: float
    plateau_number_of_epochs: int
    learning_rate_decay: float
    l2_regularization_strength: float
    dropout_rate: float
    embeddings_model_name: str
    maximum_number_of_tokens_analyzed: int
    number_of_trainable_embeddings_model_layers: int

    @validator('sliding_window_aggregation')
    def validate_sliding_window_aggregation(cls, value):
        allowed_values = ['max', 'mean']
        if value not in allowed_values:
            raise ValueError(f"sliding_window_aggregation must be one of {allowed_values}")
        return value

    @validator('data_percentage')
    def convert_data_percentage(cls, value):
        return float(str(value).strip().replace('%', ''))

class DeepLearningEmbeddingsClassifier(MLClassifier):
    """
    Base class for deep learning classifiers that use vector embeddings.
    """
    def __new__(cls, *args, **parameters):
        if cls is DeepLearningEmbeddingsClassifier:
            from plexus.classifiers.DeepLearningSlidingWindowEmbeddingsClassifier import DeepLearningSlidingWindowEmbeddingsClassifier
            
            # Validate parameters
            try:
                validated_parameters = DeepLearningEmbeddingsClassifierParameters(**parameters).dict()
            except ValidationError as e:
                Classifier.log_validation_errors(e)
                raise

            # Instantiate DeepLearningSlidingWindowEmbeddingsClassifier
            return DeepLearningSlidingWindowEmbeddingsClassifier(*args, **validated_parameters)
        else:
            return super(DeepLearningEmbeddingsClassifier, cls).__new__(cls)

    class Parameters(DeepLearningEmbeddingsClassifierParameters):
        ...
