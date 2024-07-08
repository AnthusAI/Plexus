# Plexus

An orchestration system for AI/ML classification at scale.

## Purpose

Maybe you need to comb through a million telephone call transcripts, looking for customers saying, "Take me off your list and don't call me again".

Maybe you need to detect Russian land mines in images.

Maybe you need to rank a million content items in a search engine.

Maybe you need to detect bored telephone operators speaking in a monotone voice in audio recordings.

Building classifiers is easy, but wrangling lots of them at scale is hard.  You can find a Jupyter notebook in a few minutes that you can use to train a machine-learning model.  But you need to get your training data into it.  You'll need to fiddle with your model's parameters to get good performance.  You'll need to be able to evaluate it to see how well it's doing.  You'll need to be able to deploy it to production and operate it.  You'll need to make notes somewhere about how you did that since you'll have to repeat the process over and over and over.

Plexus is not technology for helping you build models.  It's technology for helping you manage models at scale.  In biology, a "plexus" is an interconnected structure that fans out into many branches, and this Plexus is a way to fan out classification on a massive scale through standardization.

To do classification at scale, you'll need a way to select appropriate models from a toolbox, configure setup and hyperparameters for training, handle training and evaluation, and deploy models to production.  You'll need a process for implementing a solution for each new classification problem using as many reusable tools as possible.  And you'll need to be able to repeat that process over and over again.

Plexus provides some tools built around classic machine-learning models, others builts on agentic processes using sequences of LLM API requests, and others based on numerical or heuristic methods for scoring.  And most importantly, it provides a standard framework where you can plug in your own custom models.

## Opinions

Plexus is an opinionated framework for doing that sort of classification work. Among its opinions:

### Scorecards
Classifications revolve around "scores", which can be "questions" or yes/no detection, or assigning a scalar value to a piece of content.  Or any task that can be reduced to binary or multi-class classification or, generally, "scoring". Scores are grouped into "scorecards".

### DevOps/IaC

All mission-critical functionality should always revolve around versioned code and automated testing and deployment pipelines.  Including infrastructure.

### MLFlow 
You can't optimize a metric you're not measuring and tracking. Plexus uses MLFlow during model development for optimizing metrics like accuracy, precision, recall, and F1 score. The overall model lifecycle revolves around the MLFlow model registry.

### Open ML Models

There are a lot of valuable ideas out there for doing ML classification, and Plexus serves as a curated collection of some of the best models and tools for doing that.  For example, the `DeepLearningSemanticClassifier` is an implementation of Google's BERT For Sequence Classification that supports the HuggingFace Auto Classes, so that you can plug in other embedding models like DistilBERT or RoBERTa.  Whereas the `FastTextClassifer` is a wrapper around Meta's fastText.  Plexus provides a growing toolkit of options to help you build scorecards quickly.

### LLM Orchestration
Based on the principle of formulating the problem in terms that the model can solve, Plexus orchestrates scoring using large language models using an agentic decision tree and a set of fine-grained prompts for computing the classification in multiple, small steps. It also handles filtering transcripts for relevance and chunking longer text content into smaller pieces and computing an overall score from the chunks.

### Custom Classifiers

For the best results, you can also build custom classifiers.  Plexus provides a framework for doing that, and it's designed to be easy to use.  You can define your own classifier by subclassing the `Score` class and following the [standard](documentation/classifier-interface-standard.md) `ModelInput` and `ModelOutput` Pydantic classes.  And you can define your own data processors by subclassing the `Processor` class.  You can then use your custom classifier and processor in your scorecard.

### Classifier Commodification 
To avoid when-you-have-a-hammer-everything-looks-like-a-nail syndrome, Plexus makes it easy to swap out different types of machine-learning or computational or AI classifiers for different scores, so that users can experiment to find the ideal configuration for their own scorecards.

### Apache Spark
Plexus is designed to run on Apache Spark, a powerful option for processing training or inference or both at scale. [Spark support is still under development]

## Scorecard Configuration

Plexus is a Python module that you install in your Python project that contains your proprietary code for accessing your data.  It uses a `scorecards/` folder in your project to define the configuration for your scoring.  Each scorecard is represented by a YAML configuration file.  For example, if you have a scorecard for QA, you would have a YAML file in `scorecards/qa.yaml` that defines the scoring for QA, and it might look like this:
```
name: Call Center QA
key: contactics
metadata:
  foreign_id: 012
transcript_column: Transcription

scores:

  IVR Answered:
    id: 1234
    tags:
      - sales
      - IVR
    class: DeepLearningSemanticClassifier
    embeddings_model: 'distilbert-base-uncased'
    multiple_windows: true
    maximum_windows: 8
    maximum_tokens_per_window: 512
    start_from_end: true
    embeddings_model_trainable_layers: 2
    batch_size: 20
    number_of_epochs: 10
    warmup_learning_rate: 0.000000125
    number_of_warmup_epochs: 1
    plateau_learning_rate: 0.000042
    number_of_plateau_epochs: 5
    learning_rate_decay: 0.75
    early_stop_patience: 3
    l2_regularization_strength: 0.001
    dropout_rate: 0.05
    data:
      class: AWSDataLakeCache
      queries:
        - scorecard-id: 012
          score-id: 1234
          value: 'Yes'
          number: 10000
        - scorecard-id: 012
          score-id: 1234
          value: 'No'
          number: 10000
      processors:
        - class: RemoveSpeakerIdentifiersTranscriptFilter
        - class: RemoveStopWordsTranscriptFilter

  Do Not Call Request:
    id: 5678
    tags:
      - compliance
    class: ExplainableClassifier
    top_n_features: 50000
    leaderboard_n_features: 10
    target_score_name: 'Do Not Call Request'
    target_score_value: 'Yes'
    ngram_range: "1,4"
    scale_pos_weight_index: 1
    data:
      class: AWSDataLakeCache
      queries:
        - scorecard-id: 012
          score-id: 5678
          value: 'Yes'
          number: 10000
        - scorecard-id: 012
          score-id: 5678
          value: 'No'
          number: 10000
      processors:
        - class: RemoveSpeakerIdentifiersTranscriptFilter
        - class: ExpandContractionsProcessor
```

### Score Interface Standard

Each `Score` implementation must follow the [standard](documentation/classifier-interface-standard.md), based on the MLFLow standard for model interface.  Standard MLFlow models handle inference through a `predict()` function, and Plexus specifies standard  `ModelInput` and `ModelOutput` Pydantic classes that are extensible for custom models.  For example, the standard `Score.ModelInput` class contains fields for the classification and the confidence of the classification, whereas the `ExplainableClassifier` extends that to include an explanation field.

## Functionality

### Training

Train a whole scorecard:

`plexus train --scorecard-name "Call Center QA"`

Train an individual score:

`plexus train --scorecard-name "Call Center QA" --score-name "IVR Answered"`

The training process will produce a trained model and save it to the MLFlow model registry.  It will also evaluate the model and log the metrics and artifacts like confusion matrices and ROC curves to MLFlow.

### Evaluation

Some classifiers might support evaluation without supporting training, like classifiers built using agentic LLM processes.  You can evaluate these classifiers for different metrics, separately from training.

`plexus evaluate accuracy --scorecard-name "Call Center QA" --score-name "Subjective Customer Engagement Score"`

## Status

Plexus is a work in progress, with gaps in test coverage and documentation, and with a rapidly-evolving feature set. Use at your own risk, and please feel free to contact us for help.

## About

Plexus is developed and maintained by [Anthus AI Solutions](https://www.anth.us). Please [contact us](https://forms.gle/KqpKt8ERsr2QcaP1A) if you need help using Plexus for your classification needs.

## Getting Started

### Installation

Clone this repository.  We're not in PyPi yet, so you'll have to install it locally.

`pip install -e .`

### Testing

Run all the tests:

    pytest

Run a single test:

    pytest plexus/processors/RelevantWindowsTranscriptFilter_test.py -k test_multiple_keywords

or:

    pytest -k test_multiple_keywords

#### Test Coverage

Run tests with coverage:

    pytest --cov=plexus

Generate an HTML coverage report:

    pytest --cov=plexus --cov-report=html

That will generate a folder called `htmlcov` with an HTML coverage report.  One way to view that is to run:

    python -m http.server

And then go to [http://localhost:8000](http://localhost:8000)

Run tests with watch:

    ptw

## Documentation 

We build the Sphinx documentation at [https://anthusai.github.io/Plexus/](https://anthusai.github.io/Plexus/) with the files in the `documentation/` folder.

## Contributing

TODO: Instructions for contributing to the project.

## License

Plexus is open-source under the MIT license.
