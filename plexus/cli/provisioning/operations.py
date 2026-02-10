"""
Provisioning operations for SageMaker endpoints.

This module handles the actual provisioning logic including:
- Finding trained models
- Packaging models for inference
- Deploying via CDK
- Managing endpoint lifecycle
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional

from plexus.CustomLogging import logging
from plexus.training.utils import get_scorecard_key, get_score_key
from plexus.training.endpoint_utils import (
    get_sagemaker_endpoint,
    should_deploy_endpoint,
    get_endpoint_status
)


def provision_endpoint_operation(
    scorecard_name: str,
    score_name: str,
    use_yaml: bool = False,
    model_s3_uri: Optional[str] = None,
    # CLI overrides (None means use YAML config)
    deployment_type: Optional[str] = None,
    memory_mb: Optional[int] = None,
    max_concurrency: Optional[int] = None,
    instance_type: Optional[str] = None,
    min_instances: Optional[int] = None,
    max_instances: Optional[int] = None,
    scale_in_cooldown: Optional[int] = None,
    scale_out_cooldown: Optional[int] = None,
    target_invocations: Optional[float] = None,
    pytorch_version: str = '2.3.0',
    region: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Provision a SageMaker endpoint for a trained model.

    Args:
        scorecard_name: Name of the scorecard
        score_name: Name of the score
        use_yaml: Load from local YAML files
        model_s3_uri: S3 URI to model (if None, finds local model)
        deployment_type: 'serverless' or 'realtime'
        memory_mb: Memory allocation for serverless
        max_concurrency: Max concurrent invocations for serverless
        pytorch_version: PyTorch container version
        force: Force re-provisioning

    Returns:
        Dictionary with provisioning result
    """
    try:
        # Step 1: Load scorecard and get score configuration
        logging.info("Loading scorecard and score configuration...")
        scorecard_class, score_config = _load_scorecard_and_score(
            scorecard_name, score_name, use_yaml
        )

        # Step 2: Get normalized keys for naming
        # IMPORTANT: Use the actual scorecard name from the loaded class, not the identifier
        if hasattr(scorecard_class, 'name') and callable(scorecard_class.name):
            actual_scorecard_name = scorecard_class.name()
        else:
            actual_scorecard_name = scorecard_name
        scorecard_key = get_scorecard_key(scorecard_name=actual_scorecard_name)

        # Get score key from config (which may have 'key' field already set)
        score_key = get_score_key(score_config)

        logging.info(f"Actual scorecard name: {actual_scorecard_name}")
        logging.info(f"Scorecard key: {scorecard_key}")
        logging.info(f"Score key: {score_key}")

        # Step 2.5: Read deployment config from YAML and merge with CLI overrides
        deployment_config = _get_deployment_config(
            score_config=score_config,
            # CLI overrides
            deployment_type=deployment_type,
            memory_mb=memory_mb,
            max_concurrency=max_concurrency,
            instance_type=instance_type,
            min_instances=min_instances,
            max_instances=max_instances,
            scale_in_cooldown=scale_in_cooldown,
            scale_out_cooldown=scale_out_cooldown,
            target_invocations=target_invocations
        )

        logging.info(f"Deployment config: {deployment_config}")

        # Extract deployment parameters
        deployment_type = deployment_config['type']
        memory_mb = deployment_config.get('memory_mb', 4096)
        max_concurrency = deployment_config.get('max_concurrency', 10)
        instance_type = deployment_config.get('instance_type')
        min_instances = deployment_config.get('min_instances', 0)
        max_instances = deployment_config.get('max_instances', 1)
        scale_in_cooldown = deployment_config.get('scale_in_cooldown', 300)
        scale_out_cooldown = deployment_config.get('scale_out_cooldown', 60)
        target_invocations = deployment_config.get('target_invocations_per_instance', 1.0)
        base_model_hf_id = deployment_config.get('base_model_hf_id')
        adapter_s3_uri = deployment_config.get('adapter_s3_uri')
        container_image = deployment_config.get('container_image')
        hf_token = deployment_config.get('hf_token')
        environment_vars = deployment_config.get('environment', {})

        # Step 3: Find or determine model S3 URI
        # For inference components (LoRA adapters), skip traditional model lookup
        if adapter_s3_uri:
            logging.info("Using inference components with adapter - skipping traditional model lookup")
            model_s3_uri = adapter_s3_uri  # Use adapter URI as the "model" for tracking
            inference_model_uri = adapter_s3_uri  # Skip packaging steps
        else:
            # Traditional model-based deployment
            if not model_s3_uri:
                logging.info("No model S3 URI provided, looking for local model...")
                model_s3_uri = _find_or_upload_model(scorecard_key, score_key, score_config)

            logging.info(f"Model S3 URI: {model_s3_uri}")

            # Step 4: Check if provisioning is needed (idempotency)
            if not force:
                logging.info("Checking if endpoint already exists and is up-to-date...")
                if not should_deploy_endpoint(scorecard_key, score_key, model_s3_uri, deployment_type):
                    logging.info("Endpoint already exists and is up-to-date!")
                    endpoint_name = get_sagemaker_endpoint(scorecard_key, score_key, deployment_type)
                    return {
                        'success': True,
                        'endpoint_name': endpoint_name,
                        'status': 'AlreadyExists',
                        'model_s3_uri': model_s3_uri,
                        'message': 'Endpoint already exists and is up-to-date'
                    }

            # Step 5: Package model for inference (if needed)
            logging.info("Packaging model for inference...")
            inference_ready_uri = _package_model_for_inference(
                model_s3_uri, scorecard_key, score_key, score_config
            )

            # Step 5.5: Copy model from training bucket to inference bucket
            # This keeps production models stable during training
            logging.info("Copying model to inference bucket...")
            inference_model_uri = _copy_model_to_inference_bucket(
                training_model_uri=inference_ready_uri,
                scorecard_key=scorecard_key,
                score_key=score_key,
                score_config=score_config
            )

        # Step 6: Deploy via CDK
        logging.info("Deploying endpoint via CDK...")
        result = _deploy_via_cdk(
            scorecard_key=scorecard_key,
            score_key=score_key,
            model_s3_uri=inference_model_uri,
            deployment_type=deployment_type,
            memory_mb=memory_mb,
            max_concurrency=max_concurrency,
            instance_type=instance_type,
            min_instances=min_instances,
            max_instances=max_instances,
            scale_in_cooldown=scale_in_cooldown,
            scale_out_cooldown=scale_out_cooldown,
            target_invocations=target_invocations,
            base_model_hf_id=base_model_hf_id,
            adapter_s3_uri=adapter_s3_uri,
            container_image=container_image,
            hf_token=hf_token,
            environment_vars=environment_vars,
            pytorch_version=pytorch_version,
            region=region
        )

        return result

    except Exception as e:
        logging.error(f"Provisioning failed: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def get_endpoint_status_operation(
    scorecard_name: str,
    score_name: str,
    use_yaml: bool = False,
    deployment_type: str = 'serverless'
) -> Optional[Dict[str, Any]]:
    """
    Get the status of a provisioned endpoint.

    Args:
        scorecard_name: Name of the scorecard
        score_name: Name of the score
        use_yaml: Load from local YAML files
        deployment_type: 'serverless' or 'realtime'

    Returns:
        Dictionary with endpoint status or None if not found
    """
    try:
        # Load scorecard to get keys
        scorecard_class, score_config = _load_scorecard_and_score(
            scorecard_name, score_name, use_yaml
        )

        scorecard_key = get_scorecard_key(scorecard_name=scorecard_name)
        score_key = get_score_key(score_config)

        # Get endpoint status
        status_info = get_endpoint_status(scorecard_key, score_key, deployment_type)

        return status_info

    except Exception as e:
        logging.error(f"Failed to get status: {str(e)}", exc_info=True)
        raise


def delete_endpoint_operation(
    scorecard_name: str,
    score_name: str,
    use_yaml: bool = False,
    deployment_type: str = 'serverless'
) -> Dict[str, Any]:
    """
    Delete a provisioned endpoint.

    Args:
        scorecard_name: Name of the scorecard
        score_name: Name of the score
        use_yaml: Load from local YAML files
        deployment_type: 'serverless' or 'realtime'

    Returns:
        Dictionary with deletion result
    """
    try:
        # Load scorecard to get keys
        scorecard_class, score_config = _load_scorecard_and_score(
            scorecard_name, score_name, use_yaml
        )

        scorecard_key = get_scorecard_key(scorecard_name=scorecard_name)
        score_key = get_score_key(score_config)

        # Generate endpoint name using Plexus naming convention
        endpoint_name = f"plexus-{scorecard_key}-{score_key}-{deployment_type}"

        # Delete via CDK destroy
        result = _delete_via_cdk(scorecard_key, score_key, deployment_type)

        result['endpoint_name'] = endpoint_name
        return result

    except Exception as e:
        logging.error(f"Deletion failed: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def _get_deployment_config(
    score_config: dict,
    # CLI overrides (None means use YAML value)
    deployment_type: Optional[str] = None,
    memory_mb: Optional[int] = None,
    max_concurrency: Optional[int] = None,
    instance_type: Optional[str] = None,
    min_instances: Optional[int] = None,
    max_instances: Optional[int] = None,
    scale_in_cooldown: Optional[int] = None,
    scale_out_cooldown: Optional[int] = None,
    target_invocations: Optional[float] = None
) -> dict:
    """
    Get deployment configuration by merging YAML config with CLI overrides.

    CLI parameters take precedence over YAML config.
    If no deployment config exists in YAML, uses serverless defaults.

    Args:
        score_config: Score configuration dict from YAML
        CLI override parameters (None means use YAML value)

    Returns:
        Merged deployment configuration dict
    """
    # Get deployment config from YAML (if exists)
    yaml_deployment = score_config.get('deployment', {})

    # Merge with CLI overrides (CLI takes precedence)
    config = {
        'type': deployment_type if deployment_type is not None else yaml_deployment.get('type', 'serverless'),
        'memory_mb': memory_mb if memory_mb is not None else yaml_deployment.get('memory_mb', 4096),
        'max_concurrency': max_concurrency if max_concurrency is not None else yaml_deployment.get('max_concurrency', 10),
        'instance_type': instance_type if instance_type is not None else yaml_deployment.get('instance_type'),
        'min_instances': min_instances if min_instances is not None else yaml_deployment.get('min_instances', 0),
        'max_instances': max_instances if max_instances is not None else yaml_deployment.get('max_instances', 1),
        'scale_in_cooldown': scale_in_cooldown if scale_in_cooldown is not None else yaml_deployment.get('scale_in_cooldown', 300),
        'scale_out_cooldown': scale_out_cooldown if scale_out_cooldown is not None else yaml_deployment.get('scale_out_cooldown', 60),
        'target_invocations_per_instance': target_invocations if target_invocations is not None else yaml_deployment.get('target_invocations_per_instance', 1.0),
        # Inference components parameters (from YAML only, no CLI overrides)
        'base_model_hf_id': yaml_deployment.get('base_model_hf_id'),
        'adapter_s3_uri': yaml_deployment.get('adapter_s3_uri'),
        'container_image': yaml_deployment.get('container_image'),
        'hf_token': yaml_deployment.get('hf_token'),
        'environment': yaml_deployment.get('environment', {})
    }

    return config


def _load_scorecard_and_score(
    scorecard_name: str,
    score_name: str,
    use_yaml: bool
):
    """
    Load scorecard and score configuration using existing resolvers.

    Uses the same DRY pattern as train and evaluate commands.
    """
    if use_yaml:
        from plexus.cli.evaluation.evaluations import load_scorecard_from_yaml_files
        scorecard_class = load_scorecard_from_yaml_files(
            scorecard_identifier=scorecard_name,
            score_names=[score_name]
        )
    else:
        from plexus.cli.evaluation.evaluations import load_scorecard_from_api
        scorecard_class = load_scorecard_from_api(
            scorecard_identifier=scorecard_name,
            score_names=[score_name]
        )

    # Find the score configuration
    # Note: load_scorecard functions already resolve identifiers and filter to the requested score
    # So if we passed score_names=[score_name], scorecard_class.scores should contain only that score
    score_config = None

    # First try to find by matching the identifier we passed in
    for config in scorecard_class.scores:
        # Check if the config matches by name, ID, or external ID
        if (config.get('name') == score_name or
            str(config.get('id')) == str(score_name) or
            str(config.get('external_id')) == str(score_name)):
            score_config = config
            break

    # If not found by matching, but we only have one score loaded, use it
    # (this happens when the loader resolved the identifier for us)
    if not score_config and len(scorecard_class.scores) == 1:
        score_config = scorecard_class.scores[0]
        logging.info(f"Using single loaded score: {score_config.get('name')}")

    if not score_config:
        raise ValueError(
            f"Score '{score_name}' not found in scorecard '{scorecard_name}'. "
            f"Loaded {len(scorecard_class.scores)} score(s)."
        )

    return scorecard_class, score_config


def _find_or_upload_model(
    scorecard_key: str,
    score_key: str,
    score_config: Dict[str, Any]
) -> str:
    """
    Find trained model in S3.

    Training (both local and SageMaker) uploads models to S3 automatically,
    so we just need to construct the expected S3 URI.

    Checks for versioned paths first (recommended), then falls back to legacy paths.

    Returns:
        S3 URI to model.tar.gz
    """
    # Get S3 bucket from environment
    bucket_name = os.getenv('PLEXUS_S3_BUCKET')
    if not bucket_name:
        raise ValueError(
            "PLEXUS_S3_BUCKET environment variable not set. "
            "This should be set automatically from your Plexus config. "
            "Check that aws.storage.training_bucket is configured in ~/.plexus/config.yaml"
        )

    try:
        import boto3
        from botocore.exceptions import ClientError
        s3_client = boto3.client('s3')
    except ImportError:
        raise ImportError(
            "boto3 is required for provisioning. "
            "Install with: pip install boto3"
        )

    # Try versioned path first (if score has version ID)
    version_id = score_config.get('version')
    if version_id:
        versioned_s3_key = f"models/{scorecard_key}/{score_key}/{version_id}/model.tar.gz"
        versioned_s3_uri = f"s3://{bucket_name}/{versioned_s3_key}"

        logging.info(f"Checking for versioned model: {versioned_s3_uri}")
        try:
            s3_client.head_object(Bucket=bucket_name, Key=versioned_s3_key)
            logging.info(f"✓ Model found in S3 (versioned): {versioned_s3_uri}")
            return versioned_s3_uri
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logging.info(f"Versioned model not found, checking legacy path...")
            else:
                raise Exception(f"Error checking S3 for versioned model: {e}")

    # Fall back to legacy path without version
    legacy_s3_key = f"models/{scorecard_key}/{score_key}/model.tar.gz"
    legacy_s3_uri = f"s3://{bucket_name}/{legacy_s3_key}"

    logging.info(f"Checking for legacy model: {legacy_s3_uri}")
    try:
        s3_client.head_object(Bucket=bucket_name, Key=legacy_s3_key)
        logging.info(f"✓ Model found in S3 (legacy path): {legacy_s3_uri}")
        logging.warning(
            "Using legacy model path without version ID. "
            "Consider retraining with --yaml flag to use versioned storage."
        )
        return legacy_s3_uri
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            # Neither path exists
            raise FileNotFoundError(
                f"No trained model found in S3. Checked:\n"
                f"  - Versioned: {versioned_s3_uri if version_id else '(no version ID)'}\n"
                f"  - Legacy: {legacy_s3_uri}\n\n"
                f"Please train the model first using:\n"
                f"  plexus train --scorecard '{scorecard_key}' --score '{score_key}' --yaml\n"
                f"Training will automatically upload the model to S3."
            )
        else:
            raise Exception(f"Error checking S3 for model: {e}")


def _package_model_for_inference(
    model_s3_uri: str,
    scorecard_key: str,
    score_key: str,
    score_config: Dict[str, Any]
) -> str:
    """
    Package model with inference code for SageMaker.

    Downloads the model, checks for inference.py, adds it if missing, and re-uploads.

    Args:
        model_s3_uri: S3 URI to trained model
        scorecard_key: Scorecard key
        score_key: Score key
        score_config: Score configuration

    Returns:
        S3 URI to inference-ready model
    """
    import boto3
    import tarfile
    import tempfile
    import shutil
    import re

    # Parse S3 URI
    match = re.match(r's3://([^/]+)/(.+)', model_s3_uri)
    if not match:
        raise ValueError(f"Invalid S3 URI: {model_s3_uri}")

    bucket_name = match.group(1)
    s3_key = match.group(2)

    s3_client = boto3.client('s3')

    # Create temp directory for model processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download model.tar.gz
        local_tar_path = os.path.join(temp_dir, 'model.tar.gz')
        logging.info(f"Downloading model from {model_s3_uri}")
        s3_client.download_file(bucket_name, s3_key, local_tar_path)

        # Extract model
        extract_dir = os.path.join(temp_dir, 'model_extracted')
        os.makedirs(extract_dir, exist_ok=True)

        logging.info(f"Extracting model to {extract_dir}")
        with tarfile.open(local_tar_path, 'r:gz') as tar:
            tar.extractall(extract_dir)

        # Check if model has code/ directory with inference.py and requirements.txt
        # This is the SageMaker pattern for custom inference code
        code_dir = os.path.join(extract_dir, 'code')
        code_inference_path = os.path.join(code_dir, 'inference.py')
        code_requirements_path = os.path.join(code_dir, 'requirements.txt')

        code_dir_exists = os.path.exists(code_dir)
        code_inference_exists = os.path.exists(code_inference_path) if code_dir_exists else False
        code_requirements_exists = os.path.exists(code_requirements_path) if code_dir_exists else False

        if code_dir_exists and code_inference_exists and code_requirements_exists:
            logging.info("✓ Model already has code/ directory with inference.py and requirements.txt")
            return model_s3_uri

        # Need to create code/ directory with inference.py and requirements.txt
        logging.info("✗ Model missing code/ directory structure, creating it...")

        # Create code/ directory
        os.makedirs(code_dir, exist_ok=True)

        # Generate inference.py
        score_class_name = score_config.get('class')
        if score_class_name == 'BERTClassifier':
            from plexus.scores.BERTClassifier import BERTClassifier

            # Create a temporary instance just to generate the inference code
            temp_config = {
                'name': score_config.get('name', 'temp'),
                'embeddings_model': score_config.get('embeddings_model', 'distilbert-base-uncased'),
                'number_of_epochs': 1,  # Dummy values
                'warmup_learning_rate': 0.00001,
                'number_of_warmup_epochs': 1,
                'plateau_learning_rate': 0.0001,
                'number_of_plateau_epochs': 1
            }
            temp_instance = BERTClassifier(**temp_config)
            inference_code = temp_instance._generate_inference_code()

            with open(code_inference_path, 'w') as f:
                f.write(inference_code)
            logging.info(f"✓ Generated code/inference.py")
        else:
            logging.warning(f"Unknown score class '{score_class_name}', cannot generate inference.py")
            return model_s3_uri

        # Create requirements.txt
        logging.info("Creating code/requirements.txt...")
        with open(code_requirements_path, 'w') as f:
            # Add required dependencies for BERT models
            # SageMaker will install these during container startup
            f.write("transformers>=4.30.0\n")
            f.write("torch>=2.0.0\n")
            f.write("numpy\n")
            f.write("scikit-learn\n")
        logging.info("✓ Created code/requirements.txt")

        # Repack model with code/ directory
        new_tar_path = os.path.join(temp_dir, 'model_repacked.tar.gz')
        logging.info(f"Repacking model with code/ directory to {new_tar_path}")

        with tarfile.open(new_tar_path, 'w:gz') as tar:
            for item in os.listdir(extract_dir):
                item_path = os.path.join(extract_dir, item)
                tar.add(item_path, arcname=item)

        # Upload repacked model back to S3
        logging.info(f"Uploading repacked model to {model_s3_uri}")
        s3_client.upload_file(new_tar_path, bucket_name, s3_key)
        logging.info("✓ Model repackaged with code/ directory containing inference.py and requirements.txt")

        return model_s3_uri


def _copy_model_to_inference_bucket(
    training_model_uri: str,
    scorecard_key: str,
    score_key: str,
    score_config: Dict[str, Any]
) -> str:
    """
    Copy model from training bucket to inference bucket.

    This keeps production models stable during training iterations.

    Args:
        training_model_uri: S3 URI in training bucket
        scorecard_key: Scorecard key
        score_key: Score key
        score_config: Score configuration

    Returns:
        S3 URI in inference bucket
    """
    import boto3
    import re

    # Parse training URI
    # Format: s3://training-bucket/models/{scorecard}/{score}/{version}/model.tar.gz
    match = re.match(r's3://([^/]+)/(.+)', training_model_uri)
    if not match:
        raise ValueError(f"Invalid S3 URI: {training_model_uri}")

    training_bucket = match.group(1)
    training_key = match.group(2)

    # Get version ID from config
    version_id = score_config.get('version', 'latest')

    # Get environment from env vars (PLEXUS_ENVIRONMENT or environment from .env file)
    # Falls back to development if not set
    environment = os.getenv('PLEXUS_ENVIRONMENT', os.getenv('environment', 'development'))

    # Construct inference bucket name and key
    inference_bucket = f"plexus-{environment}-inference"
    inference_key = f"models/{scorecard_key}/{score_key}/{version_id}/model.tar.gz"
    inference_uri = f"s3://{inference_bucket}/{inference_key}"

    logging.info(f"Copying model:")
    logging.info(f"  From (training): {training_model_uri}")
    logging.info(f"  To (inference): {inference_uri}")

    # Copy using boto3
    s3 = boto3.client('s3')
    copy_source = {'Bucket': training_bucket, 'Key': training_key}

    try:
        s3.copy_object(
            CopySource=copy_source,
            Bucket=inference_bucket,
            Key=inference_key
        )
        logging.info("✓ Model copied successfully")
        return inference_uri
    except Exception as e:
        logging.error(f"Failed to copy model: {e}")
        raise


def _deploy_via_cdk(
    scorecard_key: str,
    score_key: str,
    model_s3_uri: str,
    deployment_type: str,
    memory_mb: int,
    max_concurrency: int,
    instance_type: Optional[str],
    min_instances: int,
    max_instances: int,
    scale_in_cooldown: int,
    scale_out_cooldown: int,
    target_invocations: float,
    base_model_hf_id: Optional[str],
    adapter_s3_uri: Optional[str],
    container_image: Optional[str],
    hf_token: Optional[str],
    environment_vars: dict,
    pytorch_version: str,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deploy endpoint using CDK.

    Args:
        scorecard_key: Scorecard key
        score_key: Score key
        model_s3_uri: S3 URI to inference-ready model
        deployment_type: 'serverless' or 'realtime'
        memory_mb: Memory allocation
        max_concurrency: Max concurrent invocations
        instance_type: Instance type for real-time
        min_instances: Minimum instances
        max_instances: Maximum instances
        scale_in_cooldown: Scale-in cooldown
        scale_out_cooldown: Scale-out cooldown
        target_invocations: Target invocations per instance
        base_model_hf_id: HuggingFace base model ID
        adapter_s3_uri: S3 URI to LoRA adapter
        container_image: Container image URI
        hf_token: HuggingFace token
        environment_vars: Additional environment variables
        pytorch_version: PyTorch version

    Returns:
        Dictionary with deployment result
    """
    # Find CDK directory
    project_root = Path(__file__).parent.parent.parent.parent  # Go up to project root
    cdk_dir = project_root / 'infrastructure'

    if not cdk_dir.exists():
        raise FileNotFoundError(f"CDK directory not found: {cdk_dir}")

    logging.info(f"Using CDK directory: {cdk_dir}")

    # Get AWS region - prefer explicitly provided region, then fall back to environment
    if region:
        aws_region = region
        logging.info(f"Using explicitly provided region: {aws_region}")
    else:
        # Try multiple sources in order of preference
        aws_region = (
            os.getenv('AWS_REGION') or
            os.getenv('AWS_DEFAULT_REGION') or
            os.getenv('PLEXUS_AWS_REGION_NAME')
        )

        # If not in environment, detect from boto3 session (which uses AWS config files)
        if not aws_region:
            try:
                import boto3
                session = boto3.Session()
                aws_region = session.region_name
                if aws_region:
                    logging.info(f"Detected region from boto3 session: {aws_region}")
            except Exception as e:
                logging.warning(f"Could not detect region from boto3: {e}")

        if not aws_region:
            raise ValueError(
                "AWS region not configured. Set AWS_REGION, AWS_DEFAULT_REGION, or "
                "configure default region in ~/.aws/config, or use --region flag"
            )

        logging.info(f"Deploying to AWS region: {aws_region}")

    # Get environment from env vars (PLEXUS_ENVIRONMENT or environment from .env file)
    # Falls back to development if not set
    environment = os.getenv('PLEXUS_ENVIRONMENT', os.getenv('environment', 'development'))

    # Construct stack name (replace underscores with hyphens for CDK compatibility)
    stack_name = f"PlexusInference-{scorecard_key}-{score_key}".replace('_', '-')

    # Build stack parameters
    stack_params = [
        f'scorecard_key=\\"{scorecard_key}\\"',
        f'score_key=\\"{score_key}\\"',
        f'model_s3_uri=\\"{model_s3_uri}\\"',
        f'environment=\\"{environment}\\"',
        f'deployment_type=\\"{deployment_type}\\"',
        f'memory_mb={memory_mb}',
        f'max_concurrency={max_concurrency}',
        f'pytorch_version=\\"{pytorch_version}\\"'
    ]

    # Add real-time parameters
    if instance_type:
        stack_params.append(f'instance_type=\\"{instance_type}\\"')
    stack_params.append(f'min_instances={min_instances}')
    stack_params.append(f'max_instances={max_instances}')
    stack_params.append(f'scale_in_cooldown={scale_in_cooldown}')
    stack_params.append(f'scale_out_cooldown={scale_out_cooldown}')
    stack_params.append(f'target_invocations={target_invocations}')

    # Add inference components parameters
    if base_model_hf_id:
        stack_params.append(f'base_model_hf_id=\\"{base_model_hf_id}\\"')
    if adapter_s3_uri:
        stack_params.append(f'adapter_s3_uri=\\"{adapter_s3_uri}\\"')
    if container_image:
        stack_params.append(f'container_image=\\"{container_image}\\"')
    if hf_token:
        stack_params.append(f'hf_token=\\"{hf_token}\\"')
    if environment_vars:
        # Use repr() to create a valid Python literal
        # repr() produces a string like: {'KEY': 'value', ...}
        stack_params.append(f'environment_vars={repr(environment_vars)}')

    # Build CDK deploy command with region and environment specified
    # The env parameter ensures CDK uses the correct region (same as S3 bucket)
    # The environment parameter tells CDK which shared role to use
    cmd = [
        'cdk', 'deploy',
        '--app', f'python3 -c "import sys; sys.path.insert(0, \\"{cdk_dir}\\"); from stacks.sagemaker_inference_stack import SageMakerInferenceStack; import aws_cdk as cdk; app = cdk.App(); SageMakerInferenceStack(app, \\"{stack_name}\\", {", ".join(stack_params)}, env=cdk.Environment(region=\\"{aws_region}\\")); app.synth()"',
        '--require-approval', 'never'
    ]

    logging.info(f"Running CDK deploy: {' '.join(cmd)}")

    try:
        # Run CDK deploy with real-time output streaming
        # Don't capture output so it streams directly to console
        result = subprocess.run(
            cmd,
            cwd=cdk_dir,
            check=True
        )

        # Generate endpoint name using Plexus naming convention
        endpoint_name = f"plexus-{scorecard_key}-{score_key}-{deployment_type}"

        return {
            'success': True,
            'endpoint_name': endpoint_name,
            'status': 'InService',
            'model_s3_uri': model_s3_uri,
            'message': 'Endpoint provisioned successfully'
        }

    except subprocess.CalledProcessError as e:
        logging.error(f"CDK deploy failed with exit code {e.returncode}")
        return {
            'success': False,
            'error': f"CDK deploy failed with exit code {e.returncode}"
        }


def _delete_via_cdk(
    scorecard_key: str,
    score_key: str,
    deployment_type: str
) -> Dict[str, Any]:
    """
    Delete endpoint using CDK destroy.

    Args:
        scorecard_key: Scorecard key
        score_key: Score key
        deployment_type: 'serverless' or 'realtime'

    Returns:
        Dictionary with deletion result
    """
    # Find CDK directory
    project_root = Path(__file__).parent.parent.parent.parent
    cdk_dir = project_root / 'infrastructure'

    stack_name = f"PlexusInference-{scorecard_key}-{score_key}"

    cmd = [
        'cdk', 'destroy',
        stack_name,
        '--force'  # Skip confirmation
    ]

    logging.info(f"Running CDK destroy: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=cdk_dir,
            capture_output=True,
            text=True,
            check=True
        )

        logging.info("CDK destroy output:")
        logging.info(result.stdout)

        return {
            'success': True,
            'message': 'Endpoint deleted successfully'
        }

    except subprocess.CalledProcessError as e:
        logging.error(f"CDK destroy failed: {e.stderr}")
        return {
            'success': False,
            'error': f"CDK destroy failed: {e.stderr}"
        }
