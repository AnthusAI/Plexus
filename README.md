# Plexus

An orchestration system for AI/ML classification at scale.

## Overview

If you need to score call center transcripts for QA, rank content items, detect things in security video footage or audio streams, then you need an orchestration platform. You need a way to run sequences of LLM API requests for scores that use AI models, a way to run machine-learning models for inference at scale for scores that use those, and a way to handle scores that use numerical or heuristic or logical methods. 

Plexus is an opinionated framework for doing that. Among its opinions:

### Scorecards
Classifications should revolve around "scores", which can be "questions" or yes/no detection, or any task that can be reduced to binary or multi-class classification. Scores are grouped into "scorecards".

### MLFlow 
You can't optimize a metric you're not measuring and tracking. Plexus uses MLFlow during model development for optimizing metrics like accuracy, precision, recall, and F1 score. The overall model lifecycle revolves around the MLFlow model registry.

### Apache Spark
Plexus is designed to run on Apache Spark, a powerful option for processing training or inference or both at scale.

### LLM Orchestration
Based on the principle of formulating the problem in terms that the model can solve, Plexus orchestrates scoring using large language models using a decision tree and a set of fine-grained prompts for computing the classification in multiple, small steps. It also handles filtering transcripts for relevance and chunking longer text content into smaller pieces and computing an overall score from the chunks.

### Classifier Commodification 
To avoid when-you-have-a-hammer-everything-looks-like-a-nail syndrome, Plexus makes it easy to swap out different types of machine-learning or computational or AI classifiers for different scores, so that users can experiment to find the ideal configuration for their own scorecards.

## Status

Plexus is a work in progress, with gaps in test coverage and documentation, and with a rapidly-evolving feature set. Use at your own risk.

## About

Plexus is developed and maintained by [Anthus AI Solutions](https://www.anth.us). Please [contact us](https://forms.gle/KqpKt8ERsr2QcaP1A) if you need help using Plexus for your classification needs.

## Getting Started

Instructions for installation, configuration, and basic usage.

## Documentation 

Links to more detailed documentation.

## Contributing

Instructions for contributing to the project.

## License

Plexus is open-source under the MIT license.