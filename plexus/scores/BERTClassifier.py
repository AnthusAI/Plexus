"""
BERTClassifier - PyTorch-based BERT classifier for semantic classification.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from pydantic import Field

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from plexus.scores.Score import Score

logger = logging.getLogger(__name__)


class BERTClassificationModel(nn.Module):
    """PyTorch model for BERT-based binary classification."""

    def __init__(self, model_name: str, dropout_rate: float = 0.3, trainable_layers: int = 3):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)

        # Freeze all layers initially
        for param in self.bert.parameters():
            param.requires_grad = False

        # Unfreeze the last n layers
        if trainable_layers > 0:
            # Get encoder layers
            if hasattr(self.bert, 'encoder') and hasattr(self.bert.encoder, 'layer'):
                total_layers = len(self.bert.encoder.layer)
                for layer in self.bert.encoder.layer[-trainable_layers:]:
                    for param in layer.parameters():
                        param.requires_grad = True

        # Classification head
        self.dropout = nn.Dropout(dropout_rate)
        self.classifier = nn.Linear(self.bert.config.hidden_size, 2)  # Binary classification

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output if hasattr(outputs, 'pooler_output') else outputs.last_hidden_state[:, 0]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return logits


class TextDataset(Dataset):
    """Dataset for text classification."""

    def __init__(self, texts: List[str], labels: List[int], tokenizer, max_length: int = 512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]

        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'label': torch.tensor(label, dtype=torch.long)
        }


class BERTClassifier(Score):
    """
    PyTorch-based BERT classifier for semantic classification.
    """

    class Parameters(Score.Parameters):
        """Parameters for BERT classifier."""

        # Model configuration
        embeddings_model: str = Field(
            description="Name of the pre-trained BERT model (e.g., 'distilbert-base-uncased', 'bert-base-uncased')"
        )
        embeddings_model_trainable_layers: int = Field(
            default=3,
            description="Number of BERT layers to fine-tune (0 = freeze all)"
        )
        maximum_tokens_per_window: int = Field(
            default=512,
            description="Maximum sequence length for tokenization"
        )

        # Training hyperparameters
        number_of_epochs: int = Field(description="Total number of training epochs")
        batch_size: int = Field(default=16, description="Training batch size")
        warmup_learning_rate: float = Field(description="Learning rate for warmup phase")
        number_of_warmup_epochs: int = Field(description="Number of warmup epochs")
        plateau_learning_rate: float = Field(description="Learning rate for plateau phase")
        number_of_plateau_epochs: int = Field(description="Number of plateau epochs")
        learning_rate_decay: float = Field(default=0.95, description="Learning rate decay factor")
        early_stop_patience: int = Field(default=3, description="Patience for early stopping")

        # Regularization
        l2_regularization_strength: float = Field(default=0.01, description="L2 regularization (weight decay)")
        dropout_rate: float = Field(default=0.3, description="Dropout rate")

        # Data configuration
        data: Optional[Dict[str, Any]] = Field(default=None, description="Data source configuration")

        # Training configuration
        training: Optional[Dict[str, Any]] = Field(default=None, description="Training configuration")

    def __init__(self, **parameters):
        """Initialize BERT classifier."""
        super().__init__(**parameters)
        self.model = None
        self.tokenizer = None

        # Select device: CUDA (NVIDIA) > MPS (Apple Silicon) > CPU
        if torch.cuda.is_available():
            self.device = torch.device('cuda')
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            self.device = torch.device('mps')
        else:
            self.device = torch.device('cpu')

        logger.info(f"Using device: {self.device}")

    @classmethod
    async def create(cls, **parameters):
        """Factory method to create a BERTClassifier instance."""
        instance = cls(**parameters)
        # Load the trained model if it exists
        await instance.load_model()
        return instance

    async def load_model(self):
        """Load a trained model from disk."""
        model_dir = self.model_directory_path()
        model_path = os.path.join(model_dir, 'model.pt')
        config_path = os.path.join(model_dir, 'config.json')
        tokenizer_path = os.path.join(model_dir, 'tokenizer')

        if not os.path.exists(model_path):
            logger.warning(f"No trained model found at {model_path}")
            return

        logger.info(f"Loading model from {model_dir}")

        # Load config
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Load tokenizer from shared cache (same pattern as inference)
        base_model_name = config['embeddings_model'].replace('/', '--')
        tokenizer_cache_path = os.path.join(model_dir, 'base', f"{base_model_name}-tokenizer")

        if os.path.exists(tokenizer_cache_path):
            # New models: Load from packaged cache
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_cache_path)
        elif os.path.exists(f"./models/base/{base_model_name}-tokenizer"):
            # Load from global shared cache
            self.tokenizer = AutoTokenizer.from_pretrained(f"./models/base/{base_model_name}-tokenizer")
        else:
            # Fall back to HuggingFace
            self.tokenizer = AutoTokenizer.from_pretrained(config['embeddings_model'])

        # Load BERT base model from shared cache
        bert_cache_path = os.path.join(model_dir, 'base', base_model_name)

        if os.path.exists(bert_cache_path):
            # New models: Load from packaged cache (fast!)
            bert_base = AutoModel.from_pretrained(bert_cache_path)
        elif os.path.exists(f"./models/base/{base_model_name}"):
            # Load from global shared cache (fast!)
            bert_base = AutoModel.from_pretrained(f"./models/base/{base_model_name}")
        else:
            # Fall back to HuggingFace download (slow)
            bert_base = AutoModel.from_pretrained(config['embeddings_model'])

        # Build classification model with loaded BERT base
        self.model = BERTClassificationModel.__new__(BERTClassificationModel)
        nn.Module.__init__(self.model)
        self.model.bert = bert_base
        self.model.dropout = nn.Dropout(config['dropout_rate'])
        self.model.classifier = nn.Linear(self.model.bert.config.hidden_size, 2)
        self.model = self.model.to(self.device)

        # Load model weights
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

        # Reconstruct label encoder
        from sklearn.preprocessing import LabelEncoder
        self.label_encoder = LabelEncoder()
        self.label_encoder.classes_ = np.array(config['label_classes'])

        logger.info(f"Model loaded successfully with {len(config['label_classes'])} classes")

    def process_data(self, data=None):
        """
        Process the loaded data for training.
        Creates train/val split and encodes labels.
        """
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder

        # Call parent process_data first
        super().process_data()

        # Get the data
        if data is None:
            if not hasattr(self, 'dataframe') or self.dataframe is None:
                raise ValueError("No data provided and no dataframe found")
            data = self.dataframe

        # Get the label column name
        score_name = self.get_label_score_name()

        # Fill NaN labels with 'Unknown'
        data[score_name] = data[score_name].fillna('Unknown')

        # Encode labels
        self.label_encoder = LabelEncoder()
        data['encoded_labels'] = self.label_encoder.fit_transform(data[score_name])

        # Train/val split
        self.train_data, self.val_data = train_test_split(
            data, test_size=0.2, random_state=42
        )

        logger.info(f"Processed {len(data)} samples")
        logger.info(f"Training set: {len(self.train_data)} samples")
        logger.info(f"Validation set: {len(self.val_data)} samples")
        logger.info(f"Label distribution: {np.bincount(data['encoded_labels'])}")

    def train_model(self):
        """
        Train the BERT classifier.
        Reads data from self.train_data and self.val_data set by process_data().
        """
        logger.info(f"Starting BERT classifier training")
        logger.info(f"Model: {self.parameters.embeddings_model}")
        logger.info(f"Device: {self.device}")

        # Extract texts and labels from train_data
        texts = self.train_data['text'].tolist()
        labels = self.train_data['encoded_labels'].tolist()

        logger.info(f"Training on {len(texts)} samples")
        logger.info(f"Label distribution: {np.bincount(labels)}")

        # Initialize tokenizer and model
        logger.info("Loading tokenizer and model...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.parameters.embeddings_model)
        self.model = BERTClassificationModel(
            model_name=self.parameters.embeddings_model,
            dropout_rate=self.parameters.dropout_rate,
            trainable_layers=self.parameters.embeddings_model_trainable_layers
        ).to(self.device)

        # Create dataset and dataloader
        dataset = TextDataset(
            texts=texts,
            labels=labels,
            tokenizer=self.tokenizer,
            max_length=self.parameters.maximum_tokens_per_window
        )
        dataloader = DataLoader(
            dataset,
            batch_size=self.parameters.batch_size,
            shuffle=True
        )

        # Training setup
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.parameters.warmup_learning_rate,
            weight_decay=self.parameters.l2_regularization_strength
        )

        # Training loop
        best_loss = float('inf')
        patience_counter = 0
        training_history = []

        for epoch in range(self.parameters.number_of_epochs):
            # Adjust learning rate based on phase
            if epoch < self.parameters.number_of_warmup_epochs:
                lr = self.parameters.warmup_learning_rate
            elif epoch < self.parameters.number_of_warmup_epochs + self.parameters.number_of_plateau_epochs:
                lr = self.parameters.plateau_learning_rate
            else:
                # Apply decay
                epochs_after_plateau = epoch - (self.parameters.number_of_warmup_epochs + self.parameters.number_of_plateau_epochs)
                lr = self.parameters.plateau_learning_rate * (self.parameters.learning_rate_decay ** epochs_after_plateau)

            for param_group in optimizer.param_groups:
                param_group['lr'] = lr

            # Training epoch
            self.model.train()
            epoch_loss = 0
            all_preds = []
            all_labels = []

            num_batches = len(dataloader)
            log_interval = max(1, num_batches // 10)  # Log 10 times per epoch

            for batch_idx, batch in enumerate(dataloader):
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                batch_labels = batch['label'].to(self.device)

                optimizer.zero_grad()
                logits = self.model(input_ids, attention_mask)
                loss = criterion(logits, batch_labels)
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                preds = torch.argmax(logits, dim=1).cpu().numpy()
                all_preds.extend(preds)
                all_labels.extend(batch_labels.cpu().numpy())

                # Log progress during epoch
                if (batch_idx + 1) % log_interval == 0 or (batch_idx + 1) == num_batches:
                    current_loss = epoch_loss / (batch_idx + 1)
                    progress = (batch_idx + 1) / num_batches * 100
                    logger.info(
                        f"  Epoch {epoch + 1}/{self.parameters.number_of_epochs} - "
                        f"Batch {batch_idx + 1}/{num_batches} ({progress:.0f}%) - "
                        f"Loss: {current_loss:.4f}"
                    )

            # Calculate metrics
            avg_loss = epoch_loss / len(dataloader)
            accuracy = accuracy_score(all_labels, all_preds)
            precision, recall, f1, _ = precision_recall_fscore_support(
                all_labels, all_preds, average='binary', zero_division=0
            )

            epoch_metrics = {
                'epoch': epoch + 1,
                'loss': avg_loss,
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'learning_rate': lr
            }
            training_history.append(epoch_metrics)

            logger.info(
                f"Epoch {epoch + 1}/{self.parameters.number_of_epochs} - "
                f"Loss: {avg_loss:.4f}, Acc: {accuracy:.4f}, F1: {f1:.4f}, LR: {lr:.6f}"
            )

            # Early stopping
            if avg_loss < best_loss:
                best_loss = avg_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= self.parameters.early_stop_patience:
                    logger.info(f"Early stopping triggered at epoch {epoch + 1}")
                    break

        # Save model artifacts using model_directory_path method
        model_dir = self.model_directory_path()
        os.makedirs(model_dir, exist_ok=True)

        # Save the complete trained model (state dict with trained weights)
        model_path = os.path.join(model_dir, 'model.pt')
        torch.save(self.model.state_dict(), model_path)
        logger.info(f"Model weights saved to {model_path}")

        # Save the BERT base model to shared global cache (convention-over-configuration)
        # Multiple scores using the same base model will share this cache locally
        import shutil
        base_model_name = self.parameters.embeddings_model.replace('/', '--')  # filesystem-safe
        base_cache_root = "./models/base"
        base_model_cache_dir = f"{base_cache_root}/{base_model_name}"

        # Ensure global shared cache exists
        if not os.path.exists(base_model_cache_dir):
            os.makedirs(base_model_cache_dir, exist_ok=True)
            self.model.bert.save_pretrained(base_model_cache_dir)
            logger.info(f"Saved BERT base model to shared cache: {base_model_cache_dir}")
        else:
            logger.info(f"BERT base model already cached at: {base_model_cache_dir}")

        # Save tokenizer to shared global cache
        tokenizer_cache_dir = f"{base_cache_root}/{base_model_name}-tokenizer"
        if not os.path.exists(tokenizer_cache_dir):
            os.makedirs(tokenizer_cache_dir, exist_ok=True)
            self.tokenizer.save_pretrained(tokenizer_cache_dir)
            logger.info(f"Saved tokenizer to shared cache: {tokenizer_cache_dir}")
        else:
            logger.info(f"Tokenizer already cached at: {tokenizer_cache_dir}")

        # Copy shared cache into model directory for packaging/deployment
        # This allows the model.tar.gz to be self-contained for SageMaker
        model_base_cache_dir = os.path.join(model_dir, 'base')
        os.makedirs(model_base_cache_dir, exist_ok=True)

        # Copy base model to model package
        model_bert_dest = os.path.join(model_base_cache_dir, base_model_name)
        if os.path.exists(model_bert_dest):
            shutil.rmtree(model_bert_dest)
        shutil.copytree(base_model_cache_dir, model_bert_dest)
        logger.info(f"Copied BERT base model to model package: {model_bert_dest}")

        # Copy tokenizer to model package
        model_tokenizer_dest = os.path.join(model_base_cache_dir, f"{base_model_name}-tokenizer")
        if os.path.exists(model_tokenizer_dest):
            shutil.rmtree(model_tokenizer_dest)
        shutil.copytree(tokenizer_cache_dir, model_tokenizer_dest)
        logger.info(f"Copied tokenizer to model package: {model_tokenizer_dest}")

        # Save training history
        history_path = os.path.join(model_dir, 'training_history.json')
        with open(history_path, 'w') as f:
            json.dump(training_history, f, indent=2)

        # Save configuration
        config_path = os.path.join(model_dir, 'config.json')
        with open(config_path, 'w') as f:
            json.dump({
                'embeddings_model': self.parameters.embeddings_model,
                'maximum_tokens_per_window': self.parameters.maximum_tokens_per_window,
                'dropout_rate': self.parameters.dropout_rate,
                'trainable_layers': self.parameters.embeddings_model_trainable_layers,
                'num_labels': 2,
                'label_classes': self.label_encoder.classes_.tolist()
            }, f, indent=2)

        # Save SageMaker inference handler
        inference_code = self._generate_inference_code()
        inference_path = os.path.join(model_dir, 'inference.py')
        with open(inference_path, 'w') as f:
            f.write(inference_code)
        logger.info(f"Inference handler saved to {inference_path}")

        final_metrics = training_history[-1]
        logger.info(
            f"Training completed - Loss: {final_metrics['loss']:.4f}, "
            f"Accuracy: {final_metrics['accuracy']:.4f}, F1: {final_metrics['f1']:.4f}"
        )

    def _generate_inference_code(self) -> str:
        """
        Generate SageMaker inference handler code for this BERT classifier.

        Returns:
            Python code as a string that SageMaker can use to serve the model
        """
        return '''"""
SageMaker inference handler for BERT Classifier.
This module is loaded by SageMaker to serve predictions.
"""
import json
import os
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel
import numpy as np


class BERTClassificationModel(nn.Module):
    """PyTorch model for BERT-based binary classification."""

    def __init__(self, model_name: str, dropout_rate: float = 0.3, trainable_layers: int = 3):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)

        # Freeze all layers initially
        for param in self.bert.parameters():
            param.requires_grad = False

        # Unfreeze the last n layers
        if trainable_layers > 0:
            if hasattr(self.bert, 'encoder') and hasattr(self.bert.encoder, 'layer'):
                for layer in self.bert.encoder.layer[-trainable_layers:]:
                    for param in layer.parameters():
                        param.requires_grad = True

        # Classification head
        self.dropout = nn.Dropout(dropout_rate)
        self.classifier = nn.Linear(self.bert.config.hidden_size, 2)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output if hasattr(outputs, 'pooler_output') else outputs.last_hidden_state[:, 0]
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)
        return logits


def model_fn(model_dir):
    """
    Load the model for inference.
    Called once when the endpoint starts.

    Loads the BERT model from local saved files to avoid downloading
    from HuggingFace on every cold start (which causes timeouts).
    """
    # Load configuration
    config_path = os.path.join(model_dir, 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Load tokenizer from shared cache within model package
    # The base model directory is packaged with the model for inference
    base_model_name = config['embeddings_model'].replace('/', '--')
    tokenizer_cache_path = os.path.join(model_dir, 'base', f"{base_model_name}-tokenizer")
    bert_cache_path = os.path.join(model_dir, 'base', base_model_name)

    if os.path.exists(tokenizer_cache_path):
        # New models: Load from shared cache within package (fast!)
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_cache_path)
    else:
        # Old models: Fall back to HuggingFace (backwards compatibility)
        tokenizer = AutoTokenizer.from_pretrained(config['embeddings_model'])

    # Load BERT base model from shared cache within package
    if os.path.exists(bert_cache_path):
        # New models: Load from shared cache (fast!)
        bert_base_model = AutoModel.from_pretrained(bert_cache_path)
    else:
        # Old models: Fall back to HuggingFace download (slow)
        bert_base_model = AutoModel.from_pretrained(config['embeddings_model'])

    # Build the classification model using the loaded BERT base
    model = BERTClassificationModel.__new__(BERTClassificationModel)
    nn.Module.__init__(model)
    model.bert = bert_base_model
    model.dropout = nn.Dropout(config['dropout_rate'])
    model.classifier = nn.Linear(model.bert.config.hidden_size, 2)

    # Load trained weights
    model_path = os.path.join(model_dir, 'model.pt')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()

    # Load label encoder classes
    label_classes = np.array(config['label_classes'])

    return {
        'model': model,
        'tokenizer': tokenizer,
        'device': device,
        'config': config,
        'label_classes': label_classes
    }


def input_fn(request_body, request_content_type):
    """
    Deserialize input data.
    """
    if request_content_type == 'application/json':
        data = json.loads(request_body)
        return data['text']
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(text, model_artifacts):
    """
    Make a prediction.
    """
    model = model_artifacts['model']
    tokenizer = model_artifacts['tokenizer']
    device = model_artifacts['device']
    config = model_artifacts['config']
    label_classes = model_artifacts['label_classes']

    # Tokenize input
    if isinstance(text, list):
        text = " ".join(text)

    encoding = tokenizer(
        text,
        max_length=config['maximum_tokens_per_window'],
        padding='max_length',
        truncation=True,
        return_tensors='pt'
    )

    input_ids = encoding['input_ids'].to(device)
    attention_mask = encoding['attention_mask'].to(device)

    # Run inference
    with torch.no_grad():
        logits = model(input_ids, attention_mask)
        probs = torch.softmax(logits, dim=1)
        pred_class = torch.argmax(probs, dim=1).item()
        confidence = probs[0][pred_class].item()

    # Map class index to label
    predicted_label = label_classes[pred_class]

    return {
        'value': predicted_label,
        'confidence': confidence,
        'probabilities': {
            'class_0': probs[0][0].item(),
            'class_1': probs[0][1].item()
        }
    }


def output_fn(prediction, response_content_type):
    """
    Serialize the prediction result.
    """
    if response_content_type == 'application/json':
        return json.dumps(prediction)
    else:
        raise ValueError(f"Unsupported content type: {response_content_type}")
'''

    async def predict(self, context, model_input: Score.Input) -> Score.Result:
        """
        Predict class for a single text input.

        Args:
            context: Context for the prediction (not used by BERTClassifier)
            model_input: Score.Input containing text and metadata

        Returns:
            Score.Result with prediction and confidence
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model not loaded. Call train_model() or load_model() first.")

        self.model.eval()

        # Extract text from model_input
        text = model_input.text
        if isinstance(text, list):
            text = " ".join(text)

        encoding = self.tokenizer(
            text,
            max_length=self.parameters.maximum_tokens_per_window,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)

        with torch.no_grad():
            logits = self.model(input_ids, attention_mask)
            probs = torch.softmax(logits, dim=1)
            pred_class = torch.argmax(probs, dim=1).item()
            confidence = probs[0][pred_class].item()

        # Map class index to label
        if hasattr(self, 'label_encoder') and self.label_encoder is not None:
            predicted_label = self.label_encoder.classes_[pred_class]
        else:
            # Fallback to generic class names
            predicted_label = f"class_{pred_class}"

        return Score.Result(
            parameters=self.parameters,
            value=predicted_label,
            confidence=confidence,
            metadata={
                'probabilities': {
                    'class_0': probs[0][0].item(),
                    'class_1': probs[0][1].item()
                }
            }
        )

    def provision_endpoint(self, **kwargs):
        """
        Provision a SageMaker Serverless Inference endpoint for this BERT classifier.

        This method handles the complete provisioning workflow:
        1. Locates the trained model in S3
        2. Copies the model from training bucket to inference bucket
        3. Deploys a SageMaker endpoint using CDK infrastructure

        Parameters
        ----------
        **kwargs : dict
            Provisioning parameters:
            - deployment_type: str = 'serverless' (deployment type)
            - memory_mb: int = 4096 (memory allocation in MB)
            - max_concurrency: int = 10 (max concurrent invocations)
            - pytorch_version: str = '2.3.0' (PyTorch version)
            - force: bool = False (force re-provision)
            - model_s3_uri: str = None (explicit model location)

        Returns
        -------
        dict
            Provisioning result with keys:
            - success: bool
            - endpoint_name: str
            - status: str
            - model_s3_uri: str
            - message: str
        """
        from plexus.cli.provisioning.operations import provision_endpoint_operation
        from plexus.training.utils import normalize_name_to_key

        # Extract parameters
        deployment_type = kwargs.get('deployment_type', 'serverless')
        memory_mb = kwargs.get('memory_mb', 4096)
        max_concurrency = kwargs.get('max_concurrency', 10)
        pytorch_version = kwargs.get('pytorch_version', '2.3.0')
        force = kwargs.get('force', False)
        model_s3_uri = kwargs.get('model_s3_uri')

        # Get scorecard information
        scorecard = kwargs.get('scorecard')
        if not scorecard:
            return {
                'success': False,
                'error': 'Scorecard instance required for provisioning'
            }

        scorecard_name = scorecard.name()
        score_name = self.parameters.name

        logger.info(f"Provisioning SageMaker endpoint for {scorecard_name} / {score_name}")

        try:
            result = provision_endpoint_operation(
                scorecard_name=scorecard_name,
                score_name=score_name,
                use_yaml=False,  # Use API by default
                model_s3_uri=model_s3_uri,
                deployment_type=deployment_type,
                memory_mb=memory_mb,
                max_concurrency=max_concurrency,
                pytorch_version=pytorch_version,
                force=force
            )

            return result

        except Exception as e:
            logger.error(f"Provisioning failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def test_endpoint(self, endpoint_name: str, **kwargs):
        """
        Test the provisioned SageMaker endpoint with Lorem Ipsum text.

        This smoke test verifies the endpoint is responding correctly by:
        1. Waiting for endpoint to reach InService status
        2. Sending Lorem Ipsum text to the endpoint (with retries)
        3. Verifying we receive a prediction response
        4. Checking the response format is valid

        Parameters
        ----------
        endpoint_name : str
            Name of the provisioned SageMaker endpoint
        **kwargs : dict
            Optional testing parameters:
            - test_text: str (custom test text, defaults to Lorem Ipsum)
            - wait_timeout: int (seconds to wait for InService, default 300)
            - max_retries: int (max invocation retries, default 3)

        Returns
        -------
        dict
            Test result with keys:
            - success: bool
            - message: str
            - prediction: dict (the prediction result)
            - latency_ms: float (response time)
        """
        import boto3
        import time

        test_text = kwargs.get('test_text',
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor "
            "incididunt ut labore et dolore magna aliqua."
        )
        wait_timeout = kwargs.get('wait_timeout', 300)  # 5 minutes for endpoint to reach InService
        max_retries = kwargs.get('max_retries', 2)  # With 10-min timeout, first request should succeed

        logger.info(f"Testing endpoint {endpoint_name} with Lorem Ipsum text")

        try:
            # Get AWS region from environment or boto3 session
            import os
            from botocore.config import Config

            aws_region = (
                os.getenv('AWS_REGION') or
                os.getenv('AWS_DEFAULT_REGION') or
                os.getenv('PLEXUS_AWS_REGION_NAME')
            )

            # If not in environment, detect from boto3 session
            if not aws_region:
                session = boto3.Session()
                aws_region = session.region_name

            if not aws_region:
                return {
                    'success': False,
                    'message': 'AWS region not configured. Set AWS_REGION, AWS_DEFAULT_REGION, or configure default region in ~/.aws/config'
                }

            logger.info(f"Using AWS region: {aws_region}")

            # Initialize SageMaker clients
            # Configure runtime client with long timeout for serverless cold starts
            # Serverless endpoints can take 5-10 minutes on first invocation
            runtime_config = Config(
                read_timeout=600,  # 10 minutes - generous timeout for cold starts
                connect_timeout=10
            )
            sagemaker = boto3.client('sagemaker', region_name=aws_region)
            runtime = boto3.client('sagemaker-runtime', region_name=aws_region, config=runtime_config)

            # Step 1: Wait for endpoint to be InService
            logger.info(f"Waiting for endpoint to reach InService status (timeout: {wait_timeout}s)...")
            start_wait = time.time()
            last_status = None

            while (time.time() - start_wait) < wait_timeout:
                try:
                    response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
                    status = response['EndpointStatus']

                    if status != last_status:
                        logger.info(f"Endpoint status: {status}")
                        last_status = status

                    if status == 'InService':
                        logger.info(f"✓ Endpoint is InService (waited {time.time() - start_wait:.1f}s)")
                        break
                    elif status in ['Failed', 'RollingBack']:
                        failure_reason = response.get('FailureReason', 'Unknown')
                        return {
                            'success': False,
                            'message': f'Endpoint creation failed with status {status}: {failure_reason}'
                        }

                    # Wait before next check
                    time.sleep(10)

                except Exception as e:
                    if 'Could not find endpoint' in str(e):
                        logger.warning(f"Endpoint not found yet, waiting... ({time.time() - start_wait:.1f}s)")
                        time.sleep(10)
                    else:
                        raise
            else:
                # Timeout reached
                return {
                    'success': False,
                    'message': f'Timeout waiting for endpoint to be InService (waited {wait_timeout}s, last status: {last_status})'
                }

            # Step 2: Test endpoint with retries
            logger.info(f"Testing endpoint invocation (max retries: {max_retries}, timeout: 600s per attempt)...")
            logger.info("Note: Serverless endpoints can take 5-10 minutes on first invocation (cold start)")
            payload = {'text': test_text}

            for attempt in range(max_retries):
                try:
                    start_time = time.time()
                    response = runtime.invoke_endpoint(
                        EndpointName=endpoint_name,
                        ContentType='application/json',
                        Body=json.dumps(payload)
                    )
                    latency_ms = (time.time() - start_time) * 1000

                    # Parse response
                    result_bytes = response['Body'].read()
                    result = json.loads(result_bytes.decode('utf-8'))

                    # Validate response structure
                    if not isinstance(result, dict):
                        return {
                            'success': False,
                            'message': 'Invalid response format: expected dict',
                            'prediction': result,
                            'latency_ms': latency_ms
                        }

                    # Check for prediction value
                    if 'value' not in result and 'prediction' not in result:
                        return {
                            'success': False,
                            'message': 'Response missing prediction value',
                            'prediction': result,
                            'latency_ms': latency_ms
                        }

                    logger.info(f"✓ Endpoint test successful - Latency: {latency_ms:.2f}ms")
                    return {
                        'success': True,
                        'message': f'Endpoint responding correctly (latency: {latency_ms:.2f}ms)',
                        'prediction': result,
                        'latency_ms': latency_ms
                    }

                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(f"Invocation attempt {attempt + 1} failed: {str(e)}, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Endpoint invocation failed after {max_retries} attempts: {str(e)}", exc_info=True)
                        return {
                            'success': False,
                            'message': f'Endpoint invocation failed after {max_retries} attempts: {str(e)}'
                        }

        except Exception as e:
            logger.error(f"Endpoint test failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Endpoint test failed: {str(e)}'
            }
