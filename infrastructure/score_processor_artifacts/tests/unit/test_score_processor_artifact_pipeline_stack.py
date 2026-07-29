import json
import tomllib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import aws_cdk as cdk
import aws_cdk.assertions as assertions

from stacks.score_processor_artifact_pipeline_stack import (
    ScoreProcessorArtifactPipelineStack,
)


def _build_template():
    app = cdk.App()
    stack = ScoreProcessorArtifactPipelineStack(
        app,
        "TestScoreProcessorArtifactPipeline",
        channel="development",
        branch="develop",
        github_owner="AnthusAI",
        github_repo="Plexus",
        trigger_on_push=True,
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    return assertions.Template.from_stack(stack)


def _template_json():
    return _build_template().to_json()


def test_artifact_pipeline_creates_private_ecr_repository():
    template = _build_template()

    template.has_resource_properties(
        "AWS::ECR::Repository",
        {
            "RepositoryName": "plexus/score-processor-artifacts-development",
            "ImageScanningConfiguration": {"ScanOnPush": True},
            "LifecyclePolicy": assertions.Match.object_like(
                {
                    "LifecyclePolicyText": assertions.Match.serialized_json(
                        assertions.Match.object_like(
                            {
                                "rules": assertions.Match.array_with(
                                    [
                                        assertions.Match.object_like(
                                            {
                                                "selection": assertions.Match.object_like(
                                                    {
                                                        "tagPrefixList": ["git-"],
                                                        "countNumber": 100,
                                                    }
                                                )
                                            }
                                        )
                                    ]
                                )
                            }
                        )
                    )
                }
            ),
        },
    )


def test_artifact_pipeline_uses_v2_pipeline_and_configured_source():
    template_json = _template_json()
    template_text = json.dumps(template_json)

    assert "AnthusAI" in template_text
    assert "Plexus" in template_text
    assert "develop" in template_text
    assert "/plexus/github-connection-arn" in template_text
    template = assertions.Template.from_json(template_json)
    template.has_resource_properties(
        "AWS::CodePipeline::Pipeline",
        {
            "Name": "plexus-score-processor-artifacts-development-pipeline",
            "PipelineType": "V2",
        },
    )


def test_build_publishes_only_immutable_image_tag_and_digest_metadata():
    template_text = json.dumps(_template_json())

    assert "score-processor-lambda/Dockerfile.scoring-runtime" in template_text
    assert "git-${SHORT_REVISION}" in template_text
    assert "$ECR_REPOSITORY_URI:$IMAGE_TAG" in template_text
    assert "$ECR_REPOSITORY_URI:latest" not in template_text
    assert "aws ecr describe-images" in template_text
    assert "$ECR_REPOSITORY_URI@$IMAGE_DIGEST" in template_text
    assert "image-detail.json" in template_text


def test_scoring_runtime_dockerfile_is_isolated_from_legacy_build():
    repository_root = Path(__file__).resolve().parents[4]
    legacy_dockerfile = (
        repository_root / "score-processor-lambda" / "Dockerfile"
    ).read_text()
    scoring_dockerfile = (
        repository_root / "score-processor-lambda" / "Dockerfile.scoring-runtime"
    ).read_text()
    scoring_dockerignore = (
        repository_root
        / "score-processor-lambda"
        / "Dockerfile.scoring-runtime.dockerignore"
    ).read_text()

    assert '"/workspace[all]"' in legacy_dockerfile
    assert '"/workspace[scoring]"' in scoring_dockerfile
    assert "COPY . /workspace" not in scoring_dockerfile
    assert "!plexus/**" in scoring_dockerignore
    assert "!MCP/**" in scoring_dockerignore
    assert "!score-processor-lambda/handler.py" in scoring_dockerignore


def test_scoring_runtime_avoids_unnecessary_system_packages():
    repository_root = Path(__file__).resolve().parents[4]
    scoring_dockerfile = (
        repository_root / "score-processor-lambda" / "Dockerfile.scoring-runtime"
    ).read_text()
    with (repository_root / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert scoring_dockerfile.startswith(
        "FROM public.ecr.aws/lambda/python:3.12@sha256:"
    )
    assert "apt-get" not in scoring_dockerfile
    assert "pip install --no-cache-dir awslambdaric" not in scoring_dockerfile
    assert "ENTRYPOINT" not in scoring_dockerfile
    assert " graphviz" not in scoring_dockerfile
    assert " git" not in scoring_dockerfile
    assert "graphviz" not in pyproject["tool"]["poetry"]["extras"]["scoring"]
    assert (
        "openai-cost-calculator" not in pyproject["tool"]["poetry"]["extras"]["scoring"]
    )
    assert pyproject["tool"]["poetry"]["dependencies"]["openai-cost-calculator"][
        "optional"
    ]
    assert "openai-cost-calculator" in pyproject["tool"]["poetry"]["extras"]["all"]


def test_build_writes_generic_plexus_metadata_parameters():
    template_text = json.dumps(_template_json())

    assert "/plexus/score-processor-artifacts/development/image-uri" in template_text
    assert "/plexus/score-processor-artifacts/development/image-digest" in template_text
    assert "/plexus/score-processor-artifacts/development/image-tag" in template_text
    assert (
        "/plexus/score-processor-artifacts/development/source-revision" in template_text
    )
    assert "aws ssm put-parameter" in template_text
    assert "capacity" not in template_text.lower()
    assert "aqa" not in template_text.lower()


def test_build_role_can_only_write_score_processor_artifact_parameters():
    template = _build_template()
    template_json = template.to_json()
    template_text = json.dumps(template_json)

    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Action": "ssm:PutParameter",
                                "Resource": (
                                    "arn:aws:ssm:us-east-1:123456789012:"
                                    "parameter/plexus/score-processor-artifacts/"
                                    "development/*"
                                ),
                            }
                        )
                    ]
                )
            }
        },
    )
    assert "ecr:DescribeImages" in template_text
