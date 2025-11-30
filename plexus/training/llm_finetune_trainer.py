"""
LLM fine-tuning data generator.

This trainer generates JSON-L training files for third-party LLM fine-tuning platforms
(OpenAI, Anthropic, etc.) by extracting prompt templates from LangGraphScore nodes
and generating completions from ground truth labels.
"""

import os
import json
import logging
import concurrent.futures
from typing import Dict, Any, Optional, List
from langchain_core.prompts import PromptTemplate

from plexus.training.trainer import Trainer

# Import helper functions from training utils module
from plexus.training.utils import (
    verify_quotes_in_completion,
    generate_llm_completion,
    create_hallucination_feedback,
    create_no_quotes_feedback,
    append_feedback_to_conversation,
    contains_disagreement,
    get_output_dir,
    get_file_path,
    get_id_file_path
)

logger = logging.getLogger(__name__)


class LLMFineTuneTrainer(Trainer):
    """
    Trainer for LLM fine-tuning data generation.

    Generates JSON-L files from LangGraphScore prompt templates + ground truth labels.
    Supports both template-based and LLM-generated completions with quote verification.

    Compatible Score classes:
        - LangGraphScore (with completion_template in graph nodes)

    Training artifacts:
        - tuning/{scorecard_name}/{score_name}/training.jsonl
        - tuning/{scorecard_name}/{score_name}/validation.jsonl
        - tuning/{scorecard_name}/{score_name}/training_ids.txt
        - tuning/{scorecard_name}/{score_name}/validation_ids.txt
    """

    def __init__(self, scorecard_class, score_config: dict,
                 fresh: bool = False, **kwargs):
        """
        Initialize LLM fine-tuning trainer.

        Additional kwargs:
            maximum_number (int): Total examples to generate (default: 100)
            train_ratio (float): Training/validation split (default: 0.8)
            threads (int): Parallel processing threads (default: 20)
            clean_existing (bool): Remove existing files first (default: False)
            verbose (bool): Enable verbose logging (default: False)
        """
        super().__init__(scorecard_class, score_config, fresh, **kwargs)

        # Extract LLM fine-tuning configuration
        finetune_config = score_config.get('training', {}).get('llm_finetune', {})

        self.max_examples = self.extra_params.get('maximum_number',
                                                   finetune_config.get('max_examples', 100))
        self.train_ratio = self.extra_params.get('train_ratio',
                                                  finetune_config.get('train_ratio', 0.8))
        self.threads = self.extra_params.get('threads', 20)
        self.clean_existing = self.extra_params.get('clean_existing', False)
        self.verbose = self.extra_params.get('verbose', False)

        self.training_examples = []
        self.validation_examples = []
        self.training_ids = []
        self.validation_ids = []

    def get_training_type(self) -> str:
        """Return training type identifier."""
        return "llm-finetune"

    def get_platform(self) -> Optional[str]:
        """Return training platform (not applicable for data generation)."""
        return None

    def validate(self):
        """
        Validate that Score has prompt templates and completion templates.

        Raises:
            ValueError: If Score doesn't support fine-tuning
        """
        score_class_name = self.score_config['class']

        # Check that Score has get_prompt_templates method
        if not hasattr(self.score_instance, 'get_prompt_templates'):
            raise ValueError(
                f"Score class '{score_class_name}' does not have 'get_prompt_templates' method. "
                f"LLM fine-tuning requires LangGraphScore or similar with prompt templates."
            )

        # Check for completion_template in graph nodes
        if 'graph' not in self.score_config or not self.score_config['graph']:
            raise ValueError(
                f"Score '{self.score_config.get('name')}' has no graph configuration. "
                f"LLM fine-tuning requires graph nodes with completion_template."
            )

        # Check first node has completion_template
        first_node = self.score_config['graph'][0]
        if 'completion_template' not in first_node:
            raise ValueError(
                f"Graph node '{first_node.get('name', 'Unknown')}' has no completion_template. "
                f"LLM fine-tuning requires completion_template in graph nodes."
            )

    def prepare_data(self):
        """
        Load and process training data using Score methods.

        Calls Score.load_data() and Score.process_data() to prepare the DataFrame
        with ground truth labels.
        """
        # Load data using Score's load_data method
        self.score_instance.load_data(
            data=self.score_config.get('data'),
            fresh=self.fresh
        )

        # Process data using Score's process_data method
        self.score_instance.process_data()

        logger.info(f"Data prepared: {len(self.score_instance.dataframe)} samples")

        # Clean existing files if requested
        if self.clean_existing:
            output_dir = get_output_dir(
                scorecard_name=self.scorecard_name,
                score_config=self.score_config
            )
            if os.path.exists(output_dir):
                for file in os.listdir(output_dir):
                    if file.endswith('.jsonl') or file.endswith('_ids.txt'):
                        file_path = os.path.join(output_dir, file)
                        os.remove(file_path)
                        logger.info(f"Removed existing file: {file_path}")

    def train(self):
        """
        Generate training and validation JSON-L files.

        This is not traditional "training" - it's data generation for external
        LLM fine-tuning. Processes rows in parallel to generate JSON-L examples.
        """
        num_train = round(self.max_examples * self.train_ratio)
        num_val = self.max_examples - num_train

        logger.info(f"Generating {num_train} training + {num_val} validation examples")

        # Get prompt templates from Score
        nodes = self.score_instance.get_prompt_templates()
        if not nodes:
            raise ValueError("No prompt templates found in Score")

        # Use first node for fine-tuning
        node_config = nodes[0]

        # Process rows in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = []
            for idx, row in self.score_instance.dataframe.iterrows():
                if len(self.training_examples) + len(self.validation_examples) >= self.max_examples:
                    break

                future = executor.submit(
                    self._process_row,
                    row,
                    node_config
                )
                futures.append(future)

            # Collect results
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        example, content_id = result

                        # Add to training or validation set
                        if len(self.training_examples) < num_train:
                            self.training_examples.append(example)
                            self.training_ids.append(content_id)
                        elif len(self.validation_examples) < num_val:
                            self.validation_examples.append(example)
                            self.validation_ids.append(content_id)

                except Exception as e:
                    logger.error(f"Error processing row: {e}")
                    if self.verbose:
                        logger.error(f"Error details:", exc_info=True)

        logger.info(f"Generated {len(self.training_examples)} training examples")
        logger.info(f"Generated {len(self.validation_examples)} validation examples")

    def _process_row(self, row, node_config) -> Optional[tuple]:
        """
        Process a single row to generate a fine-tuning example.

        Args:
            row: DataFrame row with transcript and labels
            node_config: Graph node configuration

        Returns:
            Tuple of (example_dict, content_id) or None if example should be skipped
        """
        try:
            # Extract templates
            system_message = node_config['system_message']
            user_message = node_config['user_message']
            completion_template = node_config.get('completion_template')

            # Format user message with transcript
            formatted_user_message = PromptTemplate.from_template(
                user_message,
                template_format="jinja2"
            ).format(**{"text": row['text']})

            # Generate completion
            completion = None
            conversation_history = None

            # Check if LLM-based completion is enabled
            if node_config.get('llm_completion_enabled', False):
                # Generate completion using LLM
                completion, conversation_history = generate_llm_completion(
                    self.score_instance, row, completion_template
                )

                # Quote verification if enabled
                if node_config.get('completion_quote_verification', True):
                    verification = verify_quotes_in_completion(
                        completion, row['text'],
                        fuzzy_threshold=node_config.get('quote_verification_fuzzy_threshold', 0.8)
                    )

                    if not verification['is_valid']:
                        # Handle based on failure_action
                        action = node_config.get('quote_verification_failure_action', 'skip')

                        if action == 'skip':
                            if self.verbose:
                                logger.warning(f"Skipping example due to hallucinated quotes")
                            return None

                        elif action == 'retry':
                            # Retry with feedback
                            max_retries = node_config.get('quote_verification_max_retries', 2)
                            for retry_attempt in range(max_retries):
                                feedback = create_hallucination_feedback(verification, row['text'])
                                conversation_history = append_feedback_to_conversation(
                                    conversation_history, feedback
                                )

                                # Retry generation
                                completion, conversation_history = generate_llm_completion(
                                    self.score_instance, row, completion_template,
                                    conversation_history=conversation_history
                                )

                                # Re-verify
                                verification = verify_quotes_in_completion(
                                    completion, row['text'],
                                    fuzzy_threshold=node_config.get('quote_verification_fuzzy_threshold', 0.8)
                                )

                                if verification['is_valid']:
                                    break
                            else:
                                # All retries failed - try no-quotes strategy
                                feedback = create_no_quotes_feedback()
                                conversation_history = append_feedback_to_conversation(
                                    conversation_history, feedback
                                )
                                completion, _ = generate_llm_completion(
                                    self.score_instance, row, completion_template,
                                    conversation_history=conversation_history
                                )

                        elif action == 'use_template':
                            # Fallback to template-based completion
                            completion = self._generate_template_completion(
                                row, completion_template, node_config
                            )

                        elif action == 'use_anyway':
                            # Use completion despite issues
                            pass

                # Check for disagreement
                if contains_disagreement(completion):
                    if self.verbose:
                        logger.warning(f"Skipping example - LLM disagreed with gold standard")
                    return None

            else:
                # Template-based completion
                completion = self._generate_template_completion(
                    row, completion_template, node_config
                )

            # Construct messages array for JSON-L
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": formatted_user_message},
                {"role": "assistant", "content": completion}
            ]

            example = {"messages": messages}
            content_id = row.get('content_id', row.get('feedback_item_id', 'unknown'))

            return (example, content_id)

        except Exception as e:
            if self.verbose:
                logger.error(f"Error processing row: {e}", exc_info=True)
            return None

    def _generate_template_completion(self, row, completion_template, node_config):
        """Generate completion using template interpolation."""
        labels = row.copy()

        # Apply massage_labels if present
        if 'massage_labels' in node_config:
            massage_labels_code = node_config['massage_labels']
            # Execute massage_labels transformation
            exec_globals = {'labels': labels}
            exec(f"def massage_labels(labels):\n{massage_labels_code}\n\nmassage_labels(labels)", exec_globals)
            labels = exec_globals['labels']

        # Format completion template with labels
        completion = PromptTemplate.from_template(
            completion_template,
            template_format="jinja2"
        ).format(labels=labels, **row)

        return completion.strip()

    def save_artifacts(self) -> Dict[str, str]:
        """
        Save JSON-L files and ID tracking files.

        Returns:
            Dictionary with paths to training and validation files
        """
        output_dir = get_output_dir(
            scorecard_name=self.scorecard_name,
            score_config=self.score_config
        )
        os.makedirs(output_dir, exist_ok=True)

        # File paths
        train_file = get_file_path(output_dir, 'training')
        val_file = get_file_path(output_dir, 'validation')
        train_ids_file = get_id_file_path(output_dir, 'training')
        val_ids_file = get_id_file_path(output_dir, 'validation')

        # Save training JSON-L
        with open(train_file, 'w') as f:
            for example in self.training_examples:
                json.dump(example, f)
                f.write('\n')
        logger.info(f"Saved training file: {train_file}")

        # Save validation JSON-L
        with open(val_file, 'w') as f:
            for example in self.validation_examples:
                json.dump(example, f)
                f.write('\n')
        logger.info(f"Saved validation file: {val_file}")

        # Save ID tracking files
        with open(train_ids_file, 'w') as f:
            f.write('\n'.join(self.training_ids))
        logger.info(f"Saved training IDs: {train_ids_file}")

        with open(val_ids_file, 'w') as f:
            f.write('\n'.join(self.validation_ids))
        logger.info(f"Saved validation IDs: {val_ids_file}")

        return {
            'training_file': train_file,
            'validation_file': val_file,
            'training_ids_file': train_ids_file,
            'validation_ids_file': val_ids_file,
            'output_directory': output_dir
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Return generation metrics.

        Returns:
            Dictionary with example counts
        """
        return {
            'training_examples': len(self.training_examples),
            'validation_examples': len(self.validation_examples),
            'total_examples': len(self.training_examples) + len(self.validation_examples),
            'requested_examples': self.max_examples,
            'train_ratio': self.train_ratio
        }
