"""
Lambda handler for Custom Resource to create SageMaker Inference Components.

This works around CloudFormation handler bugs by using boto3 directly.
"""
import json
import boto3
import cfnresponse
import time

sagemaker = boto3.client('sagemaker')


def handler(event, context):
    """Handle CloudFormation Custom Resource lifecycle events."""
    print(f"Event: {json.dumps(event)}")

    request_type = event['RequestType']
    properties = event['ResourceProperties']

    inference_component_name = properties['InferenceComponentName']
    physical_resource_id = inference_component_name

    try:
        if request_type == 'Create':
            create_inference_component(properties)
            wait_for_component(inference_component_name)
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_resource_id)

        elif request_type == 'Update':
            # For now, updates require replacement
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_resource_id)

        elif request_type == 'Delete':
            delete_inference_component(inference_component_name)
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_resource_id)

    except Exception as e:
        print(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)}, physical_resource_id)


def create_inference_component(properties):
    """Create inference component using boto3."""
    params = {
        'InferenceComponentName': properties['InferenceComponentName'],
        'EndpointName': properties['EndpointName'],
        'Specification': {
            'BaseInferenceComponentName': properties['BaseInferenceComponentName'],
            'Container': {
                'ArtifactUrl': properties['ArtifactUrl']
            }
            # No ComputeResourceRequirements - adapter automatically inherits from base
        }
    }

    print(f"Creating inference component: {json.dumps(params)}")
    sagemaker.create_inference_component(**params)


def wait_for_component(component_name, timeout=600):
    """Wait for inference component to be InService."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = sagemaker.describe_inference_component(
                InferenceComponentName=component_name
            )
            status = response['InferenceComponentStatus']
            print(f"Component {component_name} status: {status}")

            if status == 'InService':
                return
            elif status == 'Failed':
                raise Exception(f"Component failed: {response.get('FailureReason', 'Unknown')}")

        except sagemaker.exceptions.ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFound':
                raise

        time.sleep(10)

    raise Exception(f"Timeout waiting for component {component_name}")


def delete_inference_component(component_name):
    """Delete inference component."""
    try:
        print(f"Deleting inference component: {component_name}")
        sagemaker.delete_inference_component(InferenceComponentName=component_name)

        # Wait for deletion
        while True:
            try:
                response = sagemaker.describe_inference_component(
                    InferenceComponentName=component_name
                )
                status = response['InferenceComponentStatus']
                print(f"Component {component_name} deletion status: {status}")
                time.sleep(5)
            except sagemaker.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFound':
                    print(f"Component {component_name} deleted successfully")
                    return
                raise

    except sagemaker.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFound':
            print(f"Component {component_name} already deleted")
            return
        raise
