"""
Test CDK stack synthesis.

This tests that the SageMaker inference stack can be synthesized successfully
without errors. This validates the CDK code structure without requiring AWS deployment.
"""

import sys
import os

# Add infrastructure to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
infrastructure_path = os.path.join(project_root, 'infrastructure')
if infrastructure_path not in sys.path:
    sys.path.insert(0, infrastructure_path)


def test_sagemaker_stack_imports():
    """Test that the SageMaker inference stack can be imported."""
    from stacks.sagemaker_inference_stack import SageMakerInferenceStack
    assert SageMakerInferenceStack is not None


def test_sagemaker_stack_synthesis():
    """Test that the SageMaker inference stack can be synthesized."""
    import aws_cdk as cdk
    from stacks.sagemaker_inference_stack import SageMakerInferenceStack

    # Create a test app
    app = cdk.App()

    # Create the stack with test parameters
    stack = SageMakerInferenceStack(
        app,
        "TestPlexusInferenceStack",
        scorecard_key="test-scorecard",
        score_key="test-score",
        model_s3_uri="s3://test-bucket/models/test-scorecard/test-score/model.tar.gz",
        deployment_type="serverless",
        memory_mb=4096,
        max_concurrency=10,
        env=cdk.Environment(region="us-west-2")
    )

    # Synthesize the stack (this validates the CDK code)
    cloud_assembly = app.synth()

    # Verify the stack was created
    assert stack is not None
    assert stack.endpoint_name == "plexus-test-scorecard-test-score-serverless"

    # Verify cloud assembly was created
    assert cloud_assembly is not None

    # Verify stack template was generated
    stack_artifact = cloud_assembly.get_stack_by_name("TestPlexusInferenceStack")
    assert stack_artifact is not None

    # Verify template has required resources
    template = stack_artifact.template
    assert 'Resources' in template

    # Should have SageMaker Model, EndpointConfig, and Endpoint
    resources = template['Resources']

    # Find resources by type
    models = [k for k, v in resources.items() if v['Type'] == 'AWS::SageMaker::Model']
    configs = [k for k, v in resources.items() if v['Type'] == 'AWS::SageMaker::EndpointConfig']
    endpoints = [k for k, v in resources.items() if v['Type'] == 'AWS::SageMaker::Endpoint']

    assert len(models) == 1, f"Expected 1 Model, found {len(models)}"
    assert len(configs) == 1, f"Expected 1 EndpointConfig, found {len(configs)}"
    assert len(endpoints) == 1, f"Expected 1 Endpoint, found {len(endpoints)}"

    print("✓ Stack synthesis successful")
    print(f"✓ Endpoint name: {stack.endpoint_name}")
    print(f"✓ Model name: {stack.model_name}")
    print(f"✓ Resources: {len(models)} Model, {len(configs)} Config, {len(endpoints)} Endpoint")


def test_sagemaker_stack_validation():
    """Test stack parameter validation."""
    import aws_cdk as cdk
    from stacks.sagemaker_inference_stack import SageMakerInferenceStack
    import pytest

    app = cdk.App()

    # Test invalid deployment_type
    with pytest.raises(ValueError, match="deployment_type must be"):
        SageMakerInferenceStack(
            app, "Test1",
            scorecard_key="sc", score_key="score",
            model_s3_uri="s3://bucket/model.tar.gz",
            deployment_type="invalid"
        )

    # Test invalid memory_mb (too low)
    with pytest.raises(ValueError, match="memory_mb must be between"):
        SageMakerInferenceStack(
            app, "Test2",
            scorecard_key="sc", score_key="score",
            model_s3_uri="s3://bucket/model.tar.gz",
            memory_mb=512
        )

    # Test invalid memory_mb (too high)
    with pytest.raises(ValueError, match="memory_mb must be between"):
        SageMakerInferenceStack(
            app, "Test3",
            scorecard_key="sc", score_key="score",
            model_s3_uri="s3://bucket/model.tar.gz",
            memory_mb=10000
        )

    # Test invalid max_concurrency (too low)
    with pytest.raises(ValueError, match="max_concurrency must be between"):
        SageMakerInferenceStack(
            app, "Test4",
            scorecard_key="sc", score_key="score",
            model_s3_uri="s3://bucket/model.tar.gz",
            max_concurrency=0
        )

    # Test invalid max_concurrency (too high)
    with pytest.raises(ValueError, match="max_concurrency must be between"):
        SageMakerInferenceStack(
            app, "Test5",
            scorecard_key="sc", score_key="score",
            model_s3_uri="s3://bucket/model.tar.gz",
            max_concurrency=300
        )

    print("✓ Parameter validation working correctly")


def test_sagemaker_stack_with_different_parameters():
    """Test stack with various parameter combinations."""
    import aws_cdk as cdk
    from stacks.sagemaker_inference_stack import SageMakerInferenceStack

    app = cdk.App()

    # Test with different memory sizes
    for memory_mb in [1024, 2048, 4096, 6144]:
        stack = SageMakerInferenceStack(
            app, f"TestMemory{memory_mb}",
            scorecard_key="sc", score_key="score",
            model_s3_uri="s3://bucket/model.tar.gz",
            memory_mb=memory_mb
        )
        assert stack is not None

    # Test with different concurrency levels
    for max_concurrency in [1, 10, 50, 100, 200]:
        stack = SageMakerInferenceStack(
            app, f"TestConcurrency{max_concurrency}",
            scorecard_key="sc", score_key="score",
            model_s3_uri="s3://bucket/model.tar.gz",
            max_concurrency=max_concurrency
        )
        assert stack is not None

    # Test with different PyTorch versions
    for pytorch_version in ['2.0.0', '2.1.0', '2.3.0']:
        stack = SageMakerInferenceStack(
            app, f"TestPytorch{pytorch_version.replace('.', '')}",
            scorecard_key="sc", score_key="score",
            model_s3_uri="s3://bucket/model.tar.gz",
            pytorch_version=pytorch_version
        )
        assert stack is not None

    print("✓ All parameter combinations synthesized successfully")


if __name__ == "__main__":
    test_sagemaker_stack_imports()
    test_sagemaker_stack_synthesis()
    test_sagemaker_stack_validation()
    test_sagemaker_stack_with_different_parameters()
    print("\n✅ All CDK synthesis tests passed!")
