from typing import Any, Dict, Optional, Tuple, List
import logging
import asyncio
import tempfile
import os
import shutil
from pathlib import Path
import pandas as pd # Added for inspect_data if called directly
import json # For potentially writing a summary JSON
import yaml # For YAML formatted output with contextual comments
import traceback

# Load environment variables from .env file
try:
    import dotenv
    # Try to find .env file in common locations
    env_paths = [
        '.env',
        os.path.join(os.path.dirname(__file__), '../../../.env'),  # From blocks/ to project root
        '/Users/ryan.porter/Projects/Plexus/.env'  # Absolute path as fallback
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            dotenv.load_dotenv(env_path, override=True)
            break
except ImportError:
    pass  # dotenv not available, environment variables must be set externally

from plexus.analysis.topics.transformer import (
    transform_transcripts, 
    transform_transcripts_llm, 
    transform_transcripts_itemize,
    inspect_data # If we decide to allow inspection via block
)
# Lazy import: from plexus.analysis.topics.analyzer import analyze_topics  # Avoid loading PyTorch at startup
from plexus.dashboard.api.models.report_block import ReportBlock # For type hinting if needed
from plexus.processors.ProcessorFactory import ProcessorFactory
from plexus.reports.s3_utils import download_report_block_file
from plexus.dashboard.api.client import PlexusDashboardClient
from .data_utils import DatasetResolver

from .base import BaseReportBlock

logger = logging.getLogger(__name__)

# Supported text-based extensions for attachment
SUPPORTED_TEXT_EXTENSIONS = ['.html', '.csv', '.json', '.txt', '.md']
# Add PNG for image attachments
SUPPORTED_IMAGE_EXTENSIONS = ['.png']

class TopicAnalysis(BaseReportBlock):
    DEFAULT_NAME = "Topic Analysis"
    
    # Default prompts that can be overridden in configuration
    DEFAULT_PROMPT = """
    I have a topic from call center transcripts that is described by the following keywords: [KEYWORDS]
    In this topic, these customer-agent conversations are representative examples:
    [DOCUMENTS]

    Based on the keywords and representative examples above, provide a short, descriptive label for this topic in customer service context. Return only the label, no other text or formatting.
    """

    def __init__(self, config: Dict[str, Any], params: Optional[Dict[str, Any]], api_client: 'PlexusDashboardClient'):
        super().__init__(config, params, api_client)
        
        # Extract fine-tuning configuration
        self.fine_tuning_config = config.get("fine_tuning", {})
        
        # Extract task configuration for optional summarization feature
        self.task_config = config.get("task")
        
        # Extract final summarization configuration
        self.final_summarization_config = config.get("final_summarization", {})
        
        # Set up representation model configuration with custom prompts
        self.use_representation_model = self.fine_tuning_config.get("use_representation_model", True)
        self.representation_model_provider = self.fine_tuning_config.get("provider", "openai")
        self.representation_model_name = self.fine_tuning_config.get("model", "gpt-4o-mini")
        
        # Custom prompt (with fallback to default)
        self.representation_prompt = self.fine_tuning_config.get("prompt", self.DEFAULT_PROMPT)
        
        # Task-based system prompt (if task is provided)
        self.system_prompt = None
        if self.task_config:
            self.system_prompt = self.task_config
            # When task is provided, use it as context for the LLM fine-tuning
            self.use_representation_model = True  # Ensure representation model is enabled
        
        # Force single representation model to avoid duplicate titles
        self.force_single_representation = self.fine_tuning_config.get("force_single_representation", True)

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages: List[str] = []
        final_output_data: Dict[str, Any] = {
            "skipped_files": [],
            "errors": [],
            "summary": "Topic analysis block execution."
        }
        
        # --- 0. Get ReportBlock ID (if available) ---
        report_block_id = None
        if hasattr(self, 'report_block_id') and self.report_block_id:
            report_block_id = self.report_block_id
            self._log(f"ReportBlock ID: {report_block_id}", level="DEBUG")
        else:
            self._log("ReportBlock ID not available on self. Will not be able to attach files if this persists.", level="WARNING")


        # Create a main temporary directory for all operations of this block
        main_temp_dir = tempfile.mkdtemp(prefix="plexus_report_topic_analysis_")
        self._log(f"Created main temporary directory for block operations: {main_temp_dir}")

        try:
            # --- 1. Extract and Validate Configuration ---
            self._log("="*60)
            self._log("🚀 STAGE 1: CONFIGURATION EXTRACTION AND VALIDATION")
            self._log("="*60)
            
            # Data configuration
            data_config = self.config.get("data")
            
            # Debug logging to understand the configuration structure
            self._log(f"🔍 DEBUG: Full config keys: {list(self.config.keys())}", level="DEBUG")
            self._log(f"🔍 DEBUG: data_config type: {type(data_config)}", level="DEBUG")
            self._log(f"🔍 DEBUG: data_config value: {data_config}", level="DEBUG")
            
            if not data_config:
                msg = "'data' configuration section is required"
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Configuration error."
                shutil.rmtree(main_temp_dir)
                return final_output_data, self._get_log_string()
            
            if not isinstance(data_config, dict):
                msg = f"'data' configuration must be a dictionary, got {type(data_config).__name__}: {data_config}"
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Configuration error."
                shutil.rmtree(main_temp_dir)
                return final_output_data, self._get_log_string()
            
            # Extract data resolution parameters
            source_identifier = data_config.get("source")
            dataset_identifier = data_config.get("dataset")
            fresh_data = data_config.get("fresh", False)
            
            # Check if CLI fresh flag should override config fresh setting
            if hasattr(self, 'params') and self.params:
                # Check for various fresh parameter names that might come from CLI
                for param_name in ['fresh', 'fresh_data_cache', 'fresh_transform_cache']:
                    if param_name in self.params:
                        cli_fresh = str(self.params[param_name]).lower() in ('true', '1', 'yes')
                        if cli_fresh:
                            fresh_data = True
                            self._log(f"Fresh data cache enabled via CLI --fresh flag (param: {param_name})")
                            break
            
            if not source_identifier and not dataset_identifier:
                msg = "Must specify either 'source' or 'dataset' in data configuration"
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Configuration error."
                shutil.rmtree(main_temp_dir)
                return final_output_data, self._get_log_string()
                
            if source_identifier and dataset_identifier:
                msg = "Cannot specify both 'source' and 'dataset' in data configuration"
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Configuration error."
                shutil.rmtree(main_temp_dir)
                return final_output_data, self._get_log_string()
            
            # Resolve dataset
            self._log("📊 Resolving dataset from DataSource/Dataset")
            try:
                client = PlexusDashboardClient()
                resolver = DatasetResolver(client)
                
                self._log(f"Resolving: source='{source_identifier}' dataset='{dataset_identifier}' fresh={fresh_data}")
                input_file_path, dataset_metadata = await resolver.resolve_and_cache_dataset(
                    source=source_identifier,
                    dataset=dataset_identifier,
                    fresh=fresh_data
                )
                
                if not input_file_path:
                    msg = f"Failed to resolve dataset. Source: {source_identifier}, Dataset: {dataset_identifier}"
                    self._log(msg, level="ERROR")
                    final_output_data["errors"].append(msg)
                    final_output_data["summary"] = "Dataset resolution error."
                    shutil.rmtree(main_temp_dir)
                    return final_output_data, self._get_log_string()
                    
                self._log(f"✅ Resolved dataset to: {input_file_path}")
                if dataset_metadata:
                    self._log(f"   • Source Type: {dataset_metadata.get('source_type', 'unknown')}")
                    self._log(f"   • Name: {dataset_metadata.get('name', 'unknown')}")
                    
                    # Record the resolved dataset ID for report block association
                    if 'id' in dataset_metadata:
                        self.set_resolved_dataset_id(dataset_metadata['id'])
                    
            except Exception as e:
                msg = f"Error resolving dataset: {str(e)}"
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Dataset resolution error."
                shutil.rmtree(main_temp_dir)
                return final_output_data, self._get_log_string()

            content_column = data_config.get("content_column", "text")
            sample_size = data_config.get("sample_size")
            
            # LLM extraction configuration
            llm_extraction = self.config.get("llm_extraction", {})
            transform_method = llm_extraction.get("method", self.config.get("transform_method", "chunk"))
            llm_provider = llm_extraction.get("provider", self.config.get("llm_provider", "ollama"))
            llm_model = llm_extraction.get("model", self.config.get("llm_model", "gemma3:27b"))
            system_prompt = llm_extraction.get("system_prompt")
            user_prompt = llm_extraction.get("user_prompt")
            # Legacy support for old prompt fields
            prompt_template_path = llm_extraction.get("prompt_template_path", self.config.get("prompt_template_path"))
            prompt_template = llm_extraction.get("prompt_template", self.config.get("prompt_template"))
            
            api_key_env_var = llm_extraction.get("api_key_env_var", self.config.get("openai_api_key_env_var", "OPENAI_API_KEY"))
            max_retries_itemize = llm_extraction.get("max_retries", self.config.get("max_retries_itemize", 2))
            
            # Parallelization configuration
            max_workers = llm_extraction.get("max_workers", self.config.get("max_workers"))  # None = use provider defaults
            
            # Add support for simple_format option to avoid validation errors
            simple_format = llm_extraction.get("simple_format", self.config.get("simple_format", True))
            
            # Check for fresh_transform_cache in both config and runtime params (CLI --fresh flag)
            # Runtime params take precedence over config
            fresh_transform_cache = llm_extraction.get("fresh_cache", self.config.get("fresh_transform_cache", False))
            if hasattr(self, 'params') and self.params and 'fresh_transform_cache' in self.params:
                fresh_transform_cache = self.params['fresh_transform_cache'].lower() in ('true', '1', 'yes')
                self._log(f"Fresh transform cache enabled via CLI --fresh flag")
            elif fresh_transform_cache:
                self._log(f"Fresh transform cache enabled via configuration")

            # Fine-tuning configuration (define early since it's needed for API key handling)
            fine_tuning = self.config.get("fine_tuning", {})
            use_representation_model = fine_tuning.get("use_representation_model", self.config.get("use_representation_model", False))
            representation_model_provider = fine_tuning.get("provider", self.config.get("representation_model_provider", "openai"))
            representation_model_name = fine_tuning.get("model", self.config.get("representation_model_name", "gpt-4o-mini"))
            representation_system_prompt = fine_tuning.get("system_prompt")
            representation_user_prompt = fine_tuning.get("user_prompt")
            
            # Document selection parameters for representation model
            nr_docs = fine_tuning.get("nr_docs", 100)  # Number of documents per topic
            diversity = fine_tuning.get("diversity", 0.1)  # Diversity factor (0-1)
            doc_length = fine_tuning.get("doc_length", 500)  # Max chars per document
            tokenizer = fine_tuning.get("tokenizer", "whitespace")  # Tokenization method

            # API key handling
            openai_api_key = os.environ.get(api_key_env_var) if llm_provider == "openai" or use_representation_model else None
            if (llm_provider == "openai" or use_representation_model) and not openai_api_key:
                self._log(f"OpenAI API key not found in env var '{api_key_env_var}'. Certain features might fail.", level="WARNING")
            
            # BERTopic analysis configuration
            bertopic_analysis = self.config.get("bertopic_analysis", {})
            self._log(f"🔍 CONFIG_DEBUG: bertopic_analysis keys = {list(bertopic_analysis.keys())}")
            skip_analysis = bertopic_analysis.get("skip_analysis", self.config.get("skip_analysis", False))
            num_topics = bertopic_analysis.get("num_topics", self.config.get("num_topics"))  # Default is None (auto)
            min_ngram = bertopic_analysis.get("min_ngram", self.config.get("min_ngram", 1))
            max_ngram = bertopic_analysis.get("max_ngram", self.config.get("max_ngram", 2))
            min_topic_size = bertopic_analysis.get("min_topic_size", self.config.get("min_topic_size", 10))
            top_n_words = bertopic_analysis.get("top_n_words", self.config.get("top_n_words", 10))
            
            # Stop words filtering configuration
            remove_stop_words = bertopic_analysis.get("remove_stop_words", False)
            # Support both old (singular) and new (plural) parameter names for backward compatibility
            stop_words_languages = bertopic_analysis.get("stop_words_languages")
            if stop_words_languages is None:
                # Check for old singular parameter name
                stop_words_languages = bertopic_analysis.get("stop_words_language")
            custom_stop_words = bertopic_analysis.get("custom_stop_words", [])
            min_df = bertopic_analysis.get("min_df", 1)
            
            # N-gram export configuration
            max_ngrams_per_topic = bertopic_analysis.get("max_ngrams_per_topic", 100)
            
            # Topic stability assessment configuration
            stability_config = bertopic_analysis.get("stability", {})
            compute_stability = stability_config.get("enabled", False)
            stability_n_runs = stability_config.get("n_runs", 10)
            stability_sample_fraction = stability_config.get("sample_fraction", 0.8)
            
            # Hierarchical topic modeling configuration (opt-in)
            hierarchical_config = bertopic_analysis.get("hierarchical", {})
            compute_hierarchical = hierarchical_config.get("enabled", False)
            hierarchical_linkage = hierarchical_config.get("linkage", "average")
            hierarchical_orientation = hierarchical_config.get("orientation", "left")
            
            # Debug logging for hierarchical configuration
            self._log(f"🔍 HIERARCHICAL_DEBUG: hierarchical_config = {hierarchical_config}")
            self._log(f"🔍 HIERARCHICAL_DEBUG: compute_hierarchical = {compute_hierarchical}")
            self._log(f"🔍 HIERARCHICAL_DEBUG: hierarchical_linkage = {hierarchical_linkage}")
            self._log(f"🔍 HIERARCHICAL_DEBUG: hierarchical_orientation = {hierarchical_orientation}")

            # Preprocessing configuration
            preprocessing = self.config.get("preprocessing", {})
            preprocessing_config = preprocessing.get("steps", [])
            customer_only = preprocessing.get("customer_only", False)
            
            # Log comprehensive configuration summary
            self._log("📋 CONFIGURATION SUMMARY:")
            self._log(f"   • Input File: {input_file_path}")
            if dataset_metadata:
                self._log(f"   • Dataset Source: {dataset_metadata.get('source_type', 'unknown')}")
                self._log(f"   • Dataset Name: {dataset_metadata.get('name', 'unknown')}")
                if source_identifier:
                    self._log(f"   • DataSource Identifier: {source_identifier}")
                if dataset_identifier:
                    self._log(f"   • DataSet ID: {dataset_identifier}")
            self._log(f"   • Content Column: {content_column}")
            self._log(f"   • Transform Method: {transform_method}")
            self._log(f"   • LLM Provider: {llm_provider}")
            self._log(f"   • LLM Model: {llm_model}")
            self._log(f"   • Sample Size: {sample_size or 'All data'}")
            self._log(f"   • Customer Only: {customer_only}")
            self._log(f"   • Simple Format: {simple_format}")
            self._log(f"   • Skip Analysis: {skip_analysis}")
            self._log(f"   • Min Topic Size: {min_topic_size}")
            self._log(f"   • Use Representation Model: {use_representation_model}")
            self._log(f"   • Preprocessing Steps: {len(preprocessing_config)}")
            self._log(f"   • Fresh Data Fetch: {fresh_data}")
            self._log(f"   • Remove Stop Words: {remove_stop_words}")
            if custom_stop_words:
                self._log(f"   • Custom Stop Words: {len(custom_stop_words)} additional words")
            if min_df > 1:
                self._log(f"   • Min Document Frequency: {min_df}")
            self._log("="*60)

            # --- 2. Apply Preprocessing (if configured) ---
            if preprocessing_config:
                self._log("🔧 STAGE 2: DATA PREPROCESSING")
                self._log("="*60)
                self._log(f"Applying {len(preprocessing_config)} preprocessing steps...")
                # Load the input data for preprocessing
                df = pd.read_parquet(input_file_path)
                self._log(f"Loaded {len(df)} rows for preprocessing")
                
                preprocessing_steps_info = []
                for i, step_config in enumerate(preprocessing_config, 1):
                    processor_class = step_config.get("class")
                    processor_params = step_config.get("parameters", {})
                    
                    if not processor_class:
                        self._log(f"Skipping preprocessing step {i}: no class specified", level="WARNING")
                        continue
                    
                    try:
                        self._log(f"Applying preprocessing step {i}: {processor_class}")
                        processor = ProcessorFactory.create_processor(processor_class, **processor_params)
                        df = processor.process(df)
                        preprocessing_steps_info.append({
                            "step": i,
                            "class": processor_class,
                            "parameters": processor_params
                        })
                        self._log(f"Preprocessing step {i} completed, {len(df)} rows remaining")
                    except Exception as e:
                        error_msg = f"Error in preprocessing step {i} ({processor_class}): {e}"
                        self._log(error_msg, level="ERROR")
                        final_output_data["errors"].append(error_msg)
                        # Continue with other preprocessing steps
                
                # Save preprocessed data to a temporary file
                temp_preprocessed_file = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
                df.to_parquet(temp_preprocessed_file.name, index=False)
                input_file_path = temp_preprocessed_file.name  # Use preprocessed file for transformation
                self._log(f"Preprocessed data saved to temporary file: {input_file_path}")
                
                # Store preprocessing info for later use in final output
                preprocessing_steps_applied = preprocessing_steps_info
                original_input_file = self.config.get("data_source", {}).get("input_file_path") or self.config.get("input_file_path")
                preprocessed_rows_count = len(df)
            else:
                self._log("🔧 STAGE 2: DATA PREPROCESSING")
                self._log("="*60)
                self._log("No preprocessing steps configured, using original input file directly")
                self._log("="*60)

            # --- 3. Transform Transcripts ---
            self._log("⚡ STAGE 3: TRANSCRIPT TRANSFORMATION") 
            self._log("="*60)
            text_file_path_str: Optional[str] = None # Path to the text file for BERTopic
            transformed_parquet_path: Optional[str] = None # Path to the parquet file with metadata
            
            # The transformer functions create their own temp subdirectories.
            # We pass `main_temp_dir` to them so their caches are contained and cleaned up.
            # However, the transformer functions from `plexus.analysis.topics.transformer`
            # currently manage their own temp directory creation internally using `tempfile.mkdtemp()`
            # and don't take an output_dir parameter for the transformed text file itself.
            # They return the path to the text file, which might be in a system-wide temp location.
            # This is acceptable, as BERTopic will read from it, and it will be cleaned up eventually by the OS or on reboot.
            # The BERTopic *output* artifacts are what we need to control into our `main_temp_dir`.

            if transform_method == 'itemize':
                self._log(f"🤖 TRANSFORMATION METHOD: Itemized LLM")
                self._log(f"   • Provider: {llm_provider}")
                self._log(f"   • Model: {llm_model}")
                if system_prompt:
                    self._log("   • System Prompt:")
                    self._log("     " + "\n     ".join(system_prompt.split('\n')))
                if user_prompt:
                    self._log("   • User Prompt:")
                    self._log("     " + "\n     ".join(user_prompt.split('\n')))
                self._log("-" * 40)
                transformed_parquet_path, text_file_path_str, preprocessing_info, transformed_df = await transform_transcripts_itemize(
                    input_file=input_file_path,
                    content_column=content_column,
                    prompt_template_file=prompt_template_path,
                    prompt_template=prompt_template,
                    model=llm_model,
                    provider=llm_provider,
                    customer_only=customer_only,
                    fresh=fresh_transform_cache,
                    max_retries=max_retries_itemize,
                    simple_format=simple_format,
                    openai_api_key=openai_api_key,
                    sample_size=sample_size,
                    max_workers=max_workers
                )
            elif transform_method == 'llm':
                self._log(f"🤖 TRANSFORMATION METHOD: LLM")
                self._log(f"   • Provider: {llm_provider}")
                self._log(f"   • Model: {llm_model}")
                if system_prompt:
                    self._log("   • System Prompt:")
                    self._log("     " + "\n     ".join(system_prompt.split('\n')))
                if user_prompt:
                    self._log("   • User Prompt:")
                    self._log("     " + "\n     ".join(user_prompt.split('\n')))
                self._log("-" * 40)
                transformed_parquet_path, text_file_path_str, preprocessing_info, transformed_df = await transform_transcripts_llm(
                    input_file=input_file_path,
                    content_column=content_column,
                    prompt_template_file=prompt_template_path,
                    prompt_template=prompt_template,
                    model=llm_model,
                    provider=llm_provider,
                    customer_only=customer_only,
                    fresh=fresh_transform_cache,
                    openai_api_key=openai_api_key,
                    sample_size=sample_size
                )
            else: # 'chunk'
                self._log(f"🤖 TRANSFORMATION METHOD: Chunking (default)")
                self._log(f"   • No LLM processing - direct text chunking")
                self._log("-" * 40)
                transformed_parquet_path, text_file_path_str, preprocessing_info, transformed_df = await asyncio.to_thread(
                    transform_transcripts,
                    input_file=input_file_path,
                    content_column=content_column,
                    customer_only=customer_only,
                    fresh=fresh_transform_cache,
                    sample_size=sample_size
                )
            
            if not text_file_path_str or not Path(text_file_path_str).exists():
                msg = "Transcript transformation failed to produce a text file."
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Transformation error."
                shutil.rmtree(main_temp_dir)
                self._log(f"Cleaned up main temporary directory: {main_temp_dir}")
                return final_output_data, self._get_log_string()

            self._log("✅ TRANSFORMATION COMPLETED")
            self._log(f"   • Output file: {text_file_path_str}")
            self._log(f"   • Extraction method: {preprocessing_info.get('method', 'unknown')}")
            self._log(f"   • Examples generated: {len(preprocessing_info.get('examples', []))}")
            self._log("="*60)
            final_output_data["transformed_text_file"] = text_file_path_str
            
            # Restructure output to match UI stages
            # 1. Preprocessing (programmatic steps)
            final_output_data["preprocessing"] = {
                "method": transform_method,
                "input_file": input_file_path,
                "content_column": content_column,
                "sample_size": sample_size,
                "customer_only": customer_only,
                "data": {
                    "source_identifier": source_identifier,
                    "dataset_identifier": dataset_metadata.get('id') if dataset_metadata else dataset_identifier,  # Use resolved dataset ID
                    "fresh_data": fresh_data,
                    "metadata": dataset_metadata
                }
            }
            
            # Add preprocessing steps info if they were applied
            if 'preprocessing_steps_applied' in locals():
                final_output_data["preprocessing"]["steps"] = preprocessing_steps_applied
                final_output_data["preprocessing"]["original_input_file"] = original_input_file  
                final_output_data["preprocessing"]["preprocessed_rows"] = preprocessed_rows_count
            
            # 2. LLM Extraction (what was previously called preprocessing)
            final_output_data["llm_extraction"] = preprocessing_info

            # Add debug logging to verify hit rate stats are included
            self._log("🔍 DEBUG: LLM Extraction preprocessing_info contents:")
            self._log(f"   • Method: {preprocessing_info.get('method', 'unknown')}")
            self._log(f"   • Hit rate stats present: {'hit_rate_stats' in preprocessing_info}")
            if 'hit_rate_stats' in preprocessing_info:
                hit_stats = preprocessing_info['hit_rate_stats']
                self._log(f"   • Total processed: {hit_stats.get('total_processed', 'unknown')}")
                self._log(f"   • Successful: {hit_stats.get('successful_extractions', 'unknown')}")
                self._log(f"   • Failed: {hit_stats.get('failed_extractions', 'unknown')}")
                self._log(f"   • Hit rate: {hit_stats.get('hit_rate_percentage', 'unknown')}%")
            else:
                self._log("   • No hit_rate_stats found in preprocessing_info")
                self._log(f"   • Available keys: {list(preprocessing_info.keys())}")
            
            # 3. Add debugging information - show sample of transformed text file
            debug_info = {}
            if text_file_path_str and Path(text_file_path_str).exists():
                try:
                    with open(text_file_path_str, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        debug_info["transformed_text_lines_count"] = len(lines)
                        debug_info["transformed_text_sample"] = lines[:5] if lines else []
                        # Count unique lines to detect repetition
                        unique_lines = set(lines)
                        debug_info["unique_lines_count"] = len(unique_lines)
                        debug_info["repetition_detected"] = len(unique_lines) < len(lines) / 2
                        
                        # Show most common lines if there's repetition
                        if debug_info["repetition_detected"]:
                            from collections import Counter
                            line_counts = Counter(lines)
                            debug_info["most_common_lines"] = [
                                {"line": line.strip(), "count": count} 
                                for line, count in line_counts.most_common(3)
                            ]
                except Exception as e:
                    debug_info["error_reading_transformed_file"] = str(e)
            
            final_output_data["debug_info"] = debug_info


            # --- 4. Perform BERTopic Analysis (if not skipped) ---
            if skip_analysis:
                self._log("🔬 STAGE 4: BERTOPIC ANALYSIS")
                self._log("="*60)
                self._log("⚠️  BERTopic analysis SKIPPED as requested in configuration")
                self._log("="*60)
                final_output_data["summary"] = "Transformation completed, analysis skipped."
            else:
                self._log("🔬 STAGE 4: BERTOPIC ANALYSIS")
                self._log("="*60)
                self._log("📊 BERTOPIC PARAMETERS:")
                self._log(f"   • Min Topic Size: {min_topic_size}")
                self._log(f"   • N-gram Range: {min_ngram}-{max_ngram}")
                self._log(f"   • Top N Words: {top_n_words}")
                self._log(f"   • Requested Topics: {num_topics or 'Auto-determined'}")
                self._log("-" * 40)
                # BERTopic analysis will write its outputs into a subdirectory of `main_temp_dir`
                # The `analyze_topics` function from `plexus.analysis.topics.analyzer`
                # creates its own descriptive subdirectory based on parameters.
                # So, we pass `main_temp_dir` as the base for `analyze_topics`'s output.
                
                # Set OpenMP environment variables for BERTopic if not already set by CLI layer
                # This is crucial for preventing oversubscription of threads.
                os.environ["OMP_NUM_THREADS"] = "1"
                os.environ["OPENBLAS_NUM_THREADS"] = "1"
                os.environ["MKL_NUM_THREADS"] = "1"
                os.environ["NUMEXPR_NUM_THREADS"] = "1"
                self._log(f"Set OMP_NUM_THREADS for BERTopic: {os.environ.get('OMP_NUM_THREADS')}", level="DEBUG")

                # Capture the return value from analyze_topics (it returns just one value, not a tuple)
                # 4. Fine-tuning section (representation model configuration)
                final_output_data["fine_tuning"] = {
                    "use_representation_model": self.use_representation_model,
                    "representation_model_provider": self.representation_model_provider if self.use_representation_model else None,
                    "representation_model_name": self.representation_model_name if self.use_representation_model else None,
                    "force_single_representation": self.force_single_representation,
                    "prompt": self.representation_prompt,
                    "system_prompt": self.system_prompt  # Include task-based system prompt
                }
                
                # 4.5. Task configuration section
                if self.task_config:
                    final_output_data["task_configuration"] = {
                        "task_provided": True,
                        "task_context": self.task_config,
                        "final_summarization_enabled": True
                    }
                else:
                    final_output_data["task_configuration"] = {
                        "task_provided": False,
                        "final_summarization_enabled": False
                    }
                
                # 4.6. Final summarization configuration section
                final_output_data["final_summarization_configuration"] = {
                    "model": self.final_summarization_config.get("model", "gpt-4o-mini"),
                    "provider": self.final_summarization_config.get("provider", "openai"),
                    "custom_prompt_provided": bool(self.final_summarization_config.get("prompt")),
                    "temperature": self.final_summarization_config.get("temperature", 0.1)
                }
                
                # Log what we're passing to analyze_topics
                self._log(f"🔍 ALIGNMENT_CHECK: Calling analyze_topics with:")
                self._log(f"🔍 ALIGNMENT_CHECK:   text_file_path: {text_file_path_str}")
                self._log(f"🔍 ALIGNMENT_CHECK:   transformed_df: {len(transformed_df) if transformed_df is not None else 'None'} rows")
                if transformed_df is not None:
                    self._log(f"🔍 ALIGNMENT_CHECK:   transformed_df columns: {list(transformed_df.columns)}")
                    has_ids = any(col.lower() in ['id', 'ids'] for col in transformed_df.columns)
                    self._log(f"🔍 ID_DEBUG:   transformed_df has ID column: {has_ids}")
                
                # DEBUG: Log representation model configuration
                self._log(f"🔥 REPR_CONFIG_DEBUG: ========== REPRESENTATION MODEL CONFIG ==========")
                self._log(f"🔥 REPR_CONFIG_DEBUG: use_representation_model = {self.use_representation_model}")
                self._log(f"🔥 REPR_CONFIG_DEBUG: representation_model_provider = {self.representation_model_provider}")
                self._log(f"🔥 REPR_CONFIG_DEBUG: representation_model_name = {self.representation_model_name}")
                self._log(f"🔥 REPR_CONFIG_DEBUG: force_single_representation = {self.force_single_representation}")
                self._log(f"🔥 REPR_CONFIG_DEBUG: openai_api_key available = {bool(openai_api_key)}")
                self._log(f"🔥 REPR_CONFIG_DEBUG: fine_tuning_config = {self.fine_tuning_config}")
                self._log(f"🔥 REPR_CONFIG_DEBUG: representation_prompt length = {len(self.representation_prompt)}")
                
                # Lazy import to avoid loading PyTorch unless actually needed
                from plexus.analysis.topics.analyzer import analyze_topics
                
                # Debug logging before calling analyze_topics
                self._log(f"🔍 HIERARCHICAL_DEBUG: Calling analyze_topics with compute_hierarchical={compute_hierarchical}")
                
                analysis_results = await asyncio.to_thread(
                    analyze_topics,
                    text_file_path=text_file_path_str,
                    output_dir=main_temp_dir, # analyze_topics will create subdirs here
                    nr_topics=num_topics,
                    n_gram_range=(min_ngram, max_ngram),
                    min_topic_size=min_topic_size,
                    top_n_words=top_n_words,
                    use_representation_model=self.use_representation_model,
                    openai_api_key=openai_api_key, # Passed directly
                    representation_model_provider=self.representation_model_provider,
                    representation_model_name=self.representation_model_name,
                    transformed_df=transformed_df,
                    prompt=self.representation_prompt,
                    system_prompt=self.system_prompt,  # Pass task as system prompt
                    force_single_representation=self.force_single_representation,
                    # Document selection parameters
                    nr_docs=nr_docs,
                    diversity=diversity,
                    doc_length=doc_length,
                    tokenizer=tokenizer,
                    # Stop words filtering parameters
                    remove_stop_words=remove_stop_words,
                    stop_words_languages=stop_words_languages,
                    custom_stop_words=custom_stop_words,
                    min_df=min_df,
                    # N-gram export configuration
                    max_ngrams_per_topic=max_ngrams_per_topic,
                    # Topic stability assessment configuration
                    compute_stability=compute_stability,
                    stability_n_runs=stability_n_runs,
                    stability_sample_fraction=stability_sample_fraction,
                    # Hierarchical topic modeling configuration
                    compute_hierarchical=compute_hierarchical,
                    hierarchical_linkage=hierarchical_linkage,
                    hierarchical_orientation=hierarchical_orientation
                )

                # Unpack results; handle None if analysis failed internally
                if analysis_results:
                    topic_model = analysis_results.get('topic_model')
                    topic_info = analysis_results.get('topic_info')
                    topic_similarity_metrics = analysis_results.get('topic_similarity_metrics')
                    topic_stability = analysis_results.get('topic_stability')
                    hierarchical_topics = analysis_results.get('hierarchical_topics')
                else:
                    topic_model, topic_info = None, None
                    topic_similarity_metrics, topic_stability = None, None
                    hierarchical_topics = None

                self._log("✅ BERTopic analysis completed successfully")
                self._log("="*60)
                
                # Load "before" topics data if it exists (for fine-tuning comparison)
                before_topics_data = None
                if self.use_representation_model:
                    try:
                        import json
                        
                        # Look for the before fine-tuning file in the temp directory
                        for root, dirs, files in os.walk(main_temp_dir):
                            if "topics_before_fine_tuning.json" in files:
                                before_topics_path = os.path.join(root, "topics_before_fine_tuning.json")
                                with open(before_topics_path, 'r', encoding='utf-8') as f:
                                    before_topics_data = json.load(f)
                                    
                                self._log(f"✅ Loaded 'before' topics data from {before_topics_path}")
                                self._log(f"🔍 Found {len(before_topics_data)} topics before fine-tuning")
                                break
                        
                        if not before_topics_data:
                            self._log("⚠️  No 'before' topics data found for fine-tuning comparison")
                    except Exception as e:
                        self._log(f"❌ Failed to load 'before' topics data: {e}", level="ERROR")
                
                # Load topic stability results if they exist
                stability_data = None
                if compute_stability:
                    try:
                        import json
                        
                        # Look for the stability file in the temp directory
                        for root, dirs, files in os.walk(main_temp_dir):
                            if "topic_stability.json" in files:
                                stability_path = os.path.join(root, "topic_stability.json")
                                with open(stability_path, 'r', encoding='utf-8') as f:
                                    stability_data = json.load(f)
                                    
                                self._log(f"✅ Loaded topic stability data from {stability_path}")
                                self._log(f"🔍 Mean stability score: {stability_data.get('mean_stability', 'N/A'):.3f}")
                                self._log(f"🔍 Number of runs: {stability_data.get('n_runs', 'N/A')}")
                                break
                        
                        if not stability_data:
                            self._log("⚠️  No stability data found (stability assessment may have failed)")
                    except Exception as e:
                        self._log(f"❌ Failed to load stability data: {e}", level="ERROR")
                
                # 3. BERTopic Analysis section
                final_output_data["bertopic_analysis"] = {
                    "num_topics_requested": num_topics,
                    "min_topic_size": min_topic_size,
                    "top_n_words": top_n_words,
                    "min_ngram": min_ngram,
                    "max_ngram": max_ngram,
                    "skip_analysis": skip_analysis
                }
                
                # Add stability data to output if available
                if stability_data:
                    final_output_data["topic_stability"] = stability_data
                    self._log(f"✅ Added stability data to report output")
                    self._log(f"   • Mean stability: {stability_data.get('mean_stability', 0):.3f}")
                    self._log(f"   • Per-topic stability scores: {len(stability_data.get('per_topic_stability', {}))}")
                
                # Extract topic information and add to the final output data
                if topic_model and topic_info is not None:
                    try:
                        self._log(f"🔍 BERTopic topic_info shape: {topic_info.shape}")
                        self._log(f"🔍 BERTopic topic_info columns: {list(topic_info.columns)}")
                        self._log(f"🔍 BERTopic topic IDs found: {topic_info['Topic'].tolist()}")
                        
                        # Add debugging info to the output so it shows up in universal code
                        final_output_data["bertopic_debug"] = {
                            "topic_info_shape": list(topic_info.shape),
                            "topic_info_columns": list(topic_info.columns),
                            "topic_ids_found": topic_info['Topic'].tolist(),
                            "topic_info_empty": topic_info.empty
                        }
                        
                        if not topic_info.empty:
                            # Convert to dictionary format suitable for JSON
                            topics_list = []
                            valid_topic_count = 0
                            noise_topic_count = 0
                            
                            for _, row in topic_info.iterrows():
                                topic_id = row.get('Topic', -1)
                                if topic_id != -1:  # Skip the -1 topic which is usually "noise"
                                    valid_topic_count += 1
                                    # Get TWO types of keywords:
                                    # 1. Fine-tuned keywords (from representation model / LLM)
                                    # 2. Raw c-TF-IDF keywords (statistical, pre-LLM)
                                    
                                    keywords_fine_tuned = []  # LLM-refined, semantic keywords
                                    keywords_raw = []  # Raw statistical c-TF-IDF keywords
                                    
                                    # Get fine-tuned keywords (after LLM representation)
                                    if before_topics_data and str(topic_id) in before_topics_data:
                                        before_topic = before_topics_data[str(topic_id)]
                                        keywords_fine_tuned = before_topic.get('keywords', [])
                                    else:
                                        # Get keywords from BERTopic's get_topic method
                                        try:
                                            if hasattr(topic_model, 'get_topic'):
                                                words_weights = topic_model.get_topic(topic_id)
                                                if words_weights:
                                                    keywords_fine_tuned = [word for word, _ in words_weights[:8]]  # Top 8 keywords
                                                    self._log(f"🔍 KEYWORDS_DEBUG: Topic {topic_id} extracted {len(keywords_fine_tuned)} fine-tuned keywords: {keywords_fine_tuned[:5]}")
                                        except Exception as e:
                                            self._log(f"🔍 KEYWORDS_DEBUG: Failed to extract fine-tuned keywords for topic {topic_id}: {e}")
                                            keywords_fine_tuned = []
                                    
                                    # Get raw c-TF-IDF keywords (before LLM representation)
                                    # These come directly from the c-TF-IDF matrix
                                    try:
                                        if hasattr(topic_model, 'c_tf_idf_') and hasattr(topic_model, 'vectorizer_model'):
                                            # Find the index for this topic in the c-TF-IDF matrix
                                            topic_idx = None
                                            for idx, row_topic_id in enumerate(topic_info['Topic']):
                                                if row_topic_id == topic_id:
                                                    topic_idx = idx
                                                    break
                                            
                                            if topic_idx is not None:
                                                feature_names = topic_model.vectorizer_model.get_feature_names_out()
                                                c_tf_idf_row = topic_model.c_tf_idf_[topic_idx].toarray().flatten()
                                                # Get top keywords by c-TF-IDF score
                                                top_indices = c_tf_idf_row.argsort()[-8:][::-1]  # Top 8
                                                keywords_raw = [feature_names[i] for i in top_indices if c_tf_idf_row[i] > 0]
                                                self._log(f"🔍 KEYWORDS_DEBUG: Topic {topic_id} extracted {len(keywords_raw)} raw c-TF-IDF keywords: {keywords_raw[:5]}")
                                    except Exception as e:
                                        self._log(f"🔍 KEYWORDS_DEBUG: Failed to extract raw keywords for topic {topic_id}: {e}")
                                        keywords_raw = []
                                    
                                    # For backward compatibility, use fine-tuned as default "keywords"
                                    keywords = keywords_fine_tuned
                                    
                                    # Clean up topic name by removing ID prefix and quotes
                                    raw_name = row.get('Name', f'Topic {topic_id}')
                                    clean_name = raw_name
                                    
                                    # Remove topic ID prefix (e.g., "0_" or "-1_")
                                    if '_' in raw_name and raw_name.split('_')[0].lstrip('-').isdigit():
                                        clean_name = '_'.join(raw_name.split('_')[1:])
                                    
                                    # Remove surrounding quotes if present
                                    if clean_name.startswith('"') and clean_name.endswith('"'):
                                        clean_name = clean_name[1:-1]
                                    elif clean_name.startswith("'") and clean_name.endswith("'"):
                                        clean_name = clean_name[1:-1]
                                    
                                    # Fallback if cleaning resulted in empty string
                                    if not clean_name.strip():
                                        clean_name = f'Topic {topic_id}'
                                    
                                    topics_list.append({
                                        "id": int(topic_id),
                                        "name": clean_name.strip(),
                                        "count": int(row.get('Count', 0)),
                                        "representation": row.get('Representation', ''),
                                        "keywords": keywords,  # Fine-tuned keywords (for backward compatibility)
                                        "keywords_fine_tuned": keywords_fine_tuned,  # LLM-refined semantic keywords
                                        "keywords_raw": keywords_raw,  # Raw c-TF-IDF statistical keywords
                                        "examples": []  # Will be populated later
                                    })
                                else:
                                    noise_topic_count += 1
                            
                            # Add topic processing debug info to output
                            final_output_data["bertopic_debug"]["valid_topic_count"] = valid_topic_count
                            final_output_data["bertopic_debug"]["noise_topic_count"] = noise_topic_count
                            final_output_data["bertopic_debug"]["topics_list_length"] = len(topics_list)
                            
                            self._log(f"🔍 Topic processing: {valid_topic_count} valid topics, {noise_topic_count} noise topics")
                            
                            # --- Load Representative Documents ---
                            # Try to load representative documents from the JSON file created by analyzer
                            representative_docs_loaded = False
                            try:
                                import json
                                
                                # First, look for representative_documents.json in the temp directory structure
                                # (this works for new reports currently being generated)
                                for root, dirs, files in os.walk(main_temp_dir):
                                    if "representative_documents.json" in files:
                                        repr_docs_path = os.path.join(root, "representative_documents.json")
                                        with open(repr_docs_path, 'r', encoding='utf-8') as f:
                                            repr_docs_data = json.load(f)
                                        
                                        # Debug: Show what's actually in the representative documents file
                                        self._log(f"🔍 DEBUG: Representative documents file structure:")
                                        for topic_id_str, examples in list(repr_docs_data.items())[:2]:  # Show first 2 topics
                                            self._log(f"   • Topic {topic_id_str}: {len(examples)} examples")
                                            if examples:
                                                first_example = examples[0]
                                                self._log(f"     - First example type: {type(first_example)}")
                                                if isinstance(first_example, dict):
                                                    self._log(f"     - First example keys: {list(first_example.keys())}")
                                                    if 'id' in first_example:
                                                        self._log(f"     - First example id: {first_example['id']}")
                                                    if 'ids' in first_example:
                                                        self._log(f"     - First example ids: {first_example['ids']}")
                                                    if 'text' in first_example:
                                                        self._log(f"     - First example text: '{first_example['text'][:50]}...'")
                                                else:
                                                    self._log(f"     - First example value: '{str(first_example)[:50]}...'")
                                        
                                        # Add representative documents to each topic
                                        examples_added = 0
                                        for topic in topics_list:
                                            topic_id_str = str(topic["id"])
                                            if topic_id_str in repr_docs_data:
                                                # Handle both old format (strings) and new format (objects with text and ids)
                                                raw_examples = repr_docs_data[topic_id_str][:20]  # Limit to 20 examples for UI
                                                formatted_examples = []
                                                
                                                for example in raw_examples:
                                                    if isinstance(example, str):
                                                        # Old format: just text
                                                        formatted_examples.append({"text": example})
                                                    elif isinstance(example, dict) and "text" in example:
                                                        # New format: object with text and possibly ids
                                                        formatted_examples.append(example)
                                                    else:
                                                        # Fallback: convert to string
                                                        formatted_examples.append({"text": str(example)})
                                                
                                                topic["examples"] = formatted_examples
                                                examples_added += 1
                                                
                                                # Count how many examples have ids
                                                examples_with_ids = sum(1 for ex in formatted_examples if "id" in ex and ex["id"])
                                                self._log(f"🔍 Added {len(topic['examples'])} examples to topic {topic_id_str}: {topic.get('name', 'Unnamed')} ({examples_with_ids} with IDs)")
                                        
                                        self._log(f"✅ Added examples to {examples_added}/{len(topics_list)} topics from temp directory")
                                        
                                        representative_docs_loaded = True
                                        self._log(f"✅ Loaded representative documents from {repr_docs_path}")
                                        break
                                
                                # If not found in temp directory, try attached files (for older reports)
                                if not representative_docs_loaded and hasattr(self, '_orm') and hasattr(self._orm, 'attached_files'):
                                    attached_files = self._orm.get_attached_files()
                                    self._log(f"🔍 Checking {len(attached_files)} attached files for representative_documents.json")
                                    
                                    for file_path in attached_files:
                                        if file_path.endswith('representative_documents.json'):
                                            self._log(f"🔍 Found representative_documents.json in attached files: {file_path}")
                                            try:
                                                # Download the file from S3
                                                content, temp_path = download_report_block_file(file_path)
                                                repr_docs_data = json.loads(content)
                                                
                                                # Add representative documents to each topic
                                                examples_added = 0
                                                for topic in topics_list:
                                                    topic_id_str = str(topic["id"])
                                                    if topic_id_str in repr_docs_data:
                                                        # Handle both old format (strings) and new format (objects with text and ids)
                                                        raw_examples = repr_docs_data[topic_id_str][:20]  # Limit to 20 examples for UI
                                                        formatted_examples = []
                                                        
                                                        for example in raw_examples:
                                                            if isinstance(example, str):
                                                                # Old format: just text
                                                                formatted_examples.append({"text": example})
                                                            elif isinstance(example, dict) and "text" in example:
                                                                # New format: object with text and possibly ids
                                                                formatted_examples.append(example)
                                                            else:
                                                                # Fallback: convert to string
                                                                formatted_examples.append({"text": str(example)})
                                                        
                                                        topic["examples"] = formatted_examples
                                                        examples_added += 1
                                                        
                                                        # Count how many examples have ids
                                                        examples_with_ids = sum(1 for ex in formatted_examples if "id" in ex and ex["id"])
                                                        self._log(f"🔍 Added {len(topic['examples'])} examples to topic {topic_id_str}: {topic.get('name', 'Unnamed')} ({examples_with_ids} with IDs)")
                                                
                                                self._log(f"✅ Added examples to {examples_added}/{len(topics_list)} topics from attached files")
                                                
                                                representative_docs_loaded = True
                                                self._log(f"✅ Loaded representative documents from attached file: {file_path}")
                                                
                                                # Clean up temp file
                                                try:
                                                    if temp_path and os.path.exists(temp_path):
                                                        os.remove(temp_path)
                                                except Exception as cleanup_error:
                                                    self._log(f"Warning: Failed to clean up temp file {temp_path}: {cleanup_error}", level="WARNING")
                                                break
                                            except Exception as download_error:
                                                self._log(f"❌ Failed to download/parse representative documents from {file_path}: {download_error}", level="ERROR")
                                                continue
                                
                                if not representative_docs_loaded:
                                    self._log("⚠️  No representative_documents.json file found in temp directory or attached files")
                                    
                            except Exception as e:
                                self._log(f"❌ Failed to load representative documents: {e}", level="ERROR")
                                # Continue without representative documents
                            
                            # Enrich topics with per-topic similarity and stability metrics
                            if topic_similarity_metrics or topic_stability:
                                self._log("🔍 Enriching topics with similarity and stability metrics...")
                                
                                # Add similarity information to each topic
                                if topic_similarity_metrics and topic_similarity_metrics.get('high_similarity_pairs'):
                                    for topic in topics_list:
                                        topic_id = topic['id']
                                        similar_topics = []
                                        
                                        # Find all topics similar to this one
                                        for pair in topic_similarity_metrics['high_similarity_pairs']:
                                            if pair['topic_1_id'] == topic_id:
                                                similar_topics.append({
                                                    'topic_id': pair['topic_2_id'],
                                                    'similarity': pair['similarity']
                                                })
                                            elif pair['topic_2_id'] == topic_id:
                                                similar_topics.append({
                                                    'topic_id': pair['topic_1_id'],
                                                    'similarity': pair['similarity']
                                                })
                                        
                                        if similar_topics:
                                            # Add topic names to similar topics
                                            for sim_topic in similar_topics:
                                                matching_topic = next((t for t in topics_list if t['id'] == sim_topic['topic_id']), None)
                                                if matching_topic:
                                                    sim_topic['name'] = matching_topic['name']
                                            
                                            topic['similar_topics'] = similar_topics
                                            self._log(f"   Topic {topic_id} has {len(similar_topics)} similar topics")
                                
                                # Add stability score to each topic with interpretation
                                if topic_stability and topic_stability.get('per_topic_stability'):
                                    per_topic_stability = topic_stability['per_topic_stability']
                                    for topic in topics_list:
                                        topic_id = topic['id']
                                        if topic_id in per_topic_stability:
                                            stability_score = per_topic_stability[topic_id]
                                            topic['stability_score'] = stability_score
                                            
                                            self._log(f"   Topic {topic_id} stability: {stability_score:.3f}")
                                
                                self._log("✅ Topic enrichment complete")
                            
                            # Store full topic data as attached file to avoid DynamoDB size limits
                            # Create a summary for the main record with just essential info
                            topics_summary = []
                            for topic in topics_list:
                                summary_topic = {
                                    "id": topic["id"],
                                    "name": topic["name"],
                                    "count": topic["count"],
                                    "keywords": topic["keywords"][:5],  # Limit keywords to reduce size
                                    "examples_count": len(topic.get("examples", []))  # Just count, not full examples
                                }
                                
                                # Include metrics in summary if present
                                if 'stability_score' in topic:
                                    summary_topic['stability_score'] = topic['stability_score']
                                if 'similar_topics' in topic:
                                    summary_topic['similar_topics_count'] = len(topic['similar_topics'])
                                
                                topics_summary.append(summary_topic)
                            
                            final_output_data["topics"] = topics_summary
                            
                            # Add aggregate analysis metrics
                            if topic_similarity_metrics or topic_stability:
                                analysis_metrics = {}
                                
                                if topic_similarity_metrics:
                                    analysis_metrics['topic_similarity'] = {
                                        'mean_similarity': topic_similarity_metrics['mean_similarity'],
                                        'max_similarity': topic_similarity_metrics['max_similarity'],
                                        'min_similarity': topic_similarity_metrics['min_similarity'],
                                        'interpretation': topic_similarity_metrics['interpretation'],
                                        'high_similarity_pairs_count': len(topic_similarity_metrics.get('high_similarity_pairs', []))
                                    }
                                
                                if topic_stability:
                                    analysis_metrics['topic_stability'] = {
                                        'mean_stability': topic_stability['mean_stability'],
                                        'n_runs': topic_stability['n_runs'],
                                        'sample_fraction': topic_stability['sample_fraction'],
                                        'methodology': topic_stability['methodology']
                                    }
                                
                                final_output_data['analysis_metrics'] = analysis_metrics
                                self._log(f"✅ Added aggregate analysis metrics to output")
                            
                            # Add hierarchical topics structure if available
                            if hierarchical_topics:
                                final_output_data["hierarchical_topics"] = hierarchical_topics
                                self._log(f"✅ Added hierarchical topics structure to output")
                                self._log(f"   • Leaf topics: {hierarchical_topics['metadata']['total_leaf_topics']}")
                                self._log(f"   • Parent nodes: {hierarchical_topics['metadata']['total_parent_nodes']}")
                            
                            # Save full topic data to attached file
                            if report_block_id:
                                try:
                                    import json
                                    full_topics_json = json.dumps({
                                        "topics": topics_list,
                                        "total_topics": len(topics_list),
                                        "analysis_metadata": {
                                            "num_topics_requested": num_topics,
                                            "min_topic_size": min_topic_size,
                                            "top_n_words": top_n_words
                                        }
                                    }, indent=2, ensure_ascii=False)
                                    
                                    # Attach full topics data as JSON file
                                    self.attach_detail_file(
                                        report_block_id=report_block_id,
                                        file_name="topics_complete.json",
                                        content=full_topics_json.encode('utf-8'),
                                        content_type="application/json"
                                    )
                                    self._log(f"✅ Saved complete topic data with {len(topics_list)} topics to topics_complete.json")
                                except Exception as e:
                                    self._log(f"❌ Failed to save complete topic data: {e}", level="ERROR")
                            
                            # Add before/after comparison to fine_tuning section
                            if before_topics_data:
                                # Simplify before topics data structure - just topic name and keywords (limit to reduce size)
                                topics_before_simplified = []
                                for topic_id, topic_data in list(before_topics_data.items())[:10]:  # Limit to 10 for size
                                    topics_before_simplified.append({
                                        "topic_id": int(topic_id),
                                        "name": topic_data.get('name', f'Topic {topic_id}'),
                                        "keywords": topic_data.get('keywords', [])[:5]  # Limit keywords
                                    })
                                final_output_data["fine_tuning"]["topics_before"] = topics_before_simplified
                                self._log(f"✅ Added 'before' topics data to fine-tuning section ({len(topics_before_simplified)} of {len(before_topics_data)} topics)")
                                
                                # Create before/after comparison (limit to reduce size)
                                comparison = []
                                for topic in topics_summary[:5]:  # Show first 5 topics from summary
                                    topic_id_str = str(topic["id"])
                                    before_keywords = []
                                    before_name = "N/A"
                                    
                                    if topic_id_str in before_topics_data:
                                        before_topic = before_topics_data[topic_id_str]
                                        if isinstance(before_topic, dict):
                                            before_keywords = before_topic.get('keywords', [])[:5]  # Top 5 keywords
                                            before_name = before_topic.get('name', 'N/A')
                                    
                                    comparison.append({
                                        "topic_id": topic["id"],
                                        "before_keywords": before_keywords,
                                        "before_name": before_name,
                                        "after_name": topic["name"],
                                        "enhanced": before_name != topic["name"] and not topic["name"].startswith(str(topic["id"]) + "_")
                                    })
                                
                                final_output_data["fine_tuning"]["before_after_comparison"] = comparison
                                self._log("🔄 FINE-TUNING COMPARISON (Before vs After):")
                                for comp in comparison:
                                    keywords_str = ", ".join(comp['before_keywords'][:3]) if comp['before_keywords'] else "N/A"
                                    enhancement = "✅ Enhanced" if comp['enhanced'] else "⚠️ Not Enhanced"
                                    self._log(f"   Topic {comp['topic_id']}: [{keywords_str}] → '{comp['after_name']}' ({enhancement})")
                            else:
                                self._log("⚠️  No 'before' topics data available for comparison - this may indicate the representation model didn't save before/after states")
                                
                            # --- Task-based Final Summarization ---
                            if self.task_config and topics_list:
                                self._log("🎯 STAGE 4.5: TASK-BASED FINAL SUMMARIZATION")
                                self._log("="*60)
                                self._log("Generating final summary using task context and all topic buckets...")
                                
                                try:
                                    final_summary = await self._generate_final_summary(
                                        topics_list=topics_list,
                                        task_context=self.task_config,
                                        openai_api_key=openai_api_key,
                                        final_summarization_config=self.final_summarization_config,
                                        analysis_stats={
                                            'preprocessing': final_output_data.get('preprocessing', {}),
                                            'llm_extraction': final_output_data.get('llm_extraction', {}),
                                            'bertopic_analysis': final_output_data.get('bertopic_analysis', {}),
                                            'total_topics': len(topics_list),
                                            'total_documents': sum(topic.get('count', 0) for topic in topics_list)
                                        },
                                        full_output_data=final_output_data  # NEW: Pass entire universal code structure
                                    )
                                    
                                    if final_summary:
                                        final_output_data["final_summary"] = final_summary
                                        self._log(f"✅ Generated final summary: {final_summary[:200]}...")
                                        
                                        # Save final summary as attachment
                                        if report_block_id:
                                            self.attach_detail_file(
                                                report_block_id=report_block_id,
                                                file_name="final_summary.txt",
                                                content=final_summary.encode('utf-8'),
                                                content_type="text/plain"
                                            )
                                            self._log("✅ Saved final summary to final_summary.txt")
                                    else:
                                        self._log("⚠️  Final summary generation failed or returned empty result")
                                        
                                except Exception as e:
                                    error_msg = f"Error generating final summary: {str(e)}"
                                    traceback_str = traceback.format_exc()
                                    self._log(error_msg, level="ERROR")
                                    self._log(f"Traceback:\n{traceback_str}", level="ERROR")
                                    final_output_data["errors"].append(f"{error_msg}\n{traceback_str}")
                                    
                                self._log("="*60)
                            else:
                                if not self.task_config:
                                    self._log("ℹ️  No task configuration provided - skipping final summarization")
                                else:
                                    self._log("⚠️  No topics found - skipping final summarization")

                            # This is critical information - ensure it goes to both console AND attached log
                            self._log("🎯 TOPIC DISCOVERY RESULTS")
                            self._log("-" * 40)
                            self._log(f"📈 FOUND {len(topics_list)} DISTINCT TOPICS")
                            self._log(f"📋 Complete topic data saved to topics_complete.json attachment")
                            
                            # Log top topic details for visibility
                            if topics_list:
                                sorted_topics = sorted(topics_list, key=lambda t: t.get('count', 0), reverse=True)
                                self._log("📊 TOP TOPICS SUMMARY:")
                                for i, topic in enumerate(sorted_topics[:5]):  # Top 5 topics
                                    keywords = topic.get('keywords', [])[:8]  # Top 8 keywords
                                    self._log(f"   {i+1}. Topic {topic['id']}: {topic['count']} items")
                                    self._log(f"      Name: {topic.get('name', 'Unnamed')}")
                                    self._log(f"      Keywords: {', '.join(keywords)}")
                                
                                self._log("-" * 40)
                            
                            # Add visualization info based on topic count
                            if len(topics_list) < 2:
                                final_output_data["visualization_notes"] = {
                                    "topics_visualization": "Skipped - requires 2+ topics for 2D visualization",
                                    "heatmap_visualization": "Skipped - requires 2+ topics",
                                    "available_files": "Topic information CSV and individual topic details available"
                                }
                    except Exception as e:
                        tb_str = traceback.format_exc()
                        self._log(f"Failed to extract topic information: {e}", "ERROR")
                        self._log(f"Traceback:\n{tb_str}", "ERROR")
                        final_output_data["bertopic_debug"] = {
                            "topic_model_exists": topic_model is not None,
                            "has_get_topic_info": hasattr(topic_model, 'get_topic_info') if topic_model else False,
                            "error_reason": f"Exception during topic extraction: {str(e)}"
                        }
                        self._log(f"Failed to extract topic information: {e}", "ERROR")
                        final_output_data["errors"].append(f"Error extracting topics: {str(e)}")
                else:
                    # No topic model or couldn't get topic info
                    error_reason = "No topic model returned or missing get_topic_info method. This often indicates a problem during the BERTopic model fitting process (e.g., incompatible data, memory issues)."
                    final_output_data["bertopic_debug"] = {
                        "topic_model_exists": topic_model is not None,
                        "has_get_topic_info": hasattr(topic_model, 'get_topic_info') if topic_model else False,
                        "error_reason": error_reason
                    }
                    final_output_data["errors"].append(f"BERTopic Analysis Failed: {error_reason}")
                    self._log("🎯 TOPIC DISCOVERY RESULTS")
                    self._log("-" * 40)
                    self._log("⚠️  NO TOPICS DISCOVERED (DUE TO ERROR)")
                    self._log(f"   ERROR: {error_reason}")
                    self._log("   This could be due to:")
                    self._log(f"   • Min topic size being too high (current: {min_topic_size}) for the data.")
                    self._log("   • Insufficient data diversity or sample size.")
                    self._log("   • An internal error in the BERTopic library or its dependencies.")
                    self._log("-" * 40)

                # --- 5. Attach Artifacts ---
                self._log("📎 STAGE 5: FILE ATTACHMENT")
                self._log("="*60)
                self._log(f"Scanning artifacts in: {main_temp_dir}")
                if not report_block_id:
                    self._log("❌ No report_block_id available - cannot attach files", level="ERROR")
                    final_output_data["errors"].append("Cannot attach files: report_block_id is missing.")
                else:
                    for root, _, files in os.walk(main_temp_dir):
                        for filename in files:
                            file_path = Path(root) / filename
                            file_ext = file_path.suffix.lower()

                            if file_ext in SUPPORTED_TEXT_EXTENSIONS:
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        content = f.read()
                                    
                                    # Use relative path for display name in attachedFiles
                                    relative_file_path = str(file_path.relative_to(main_temp_dir))
                                    
                                    # Dynamically determine content type for common text files
                                    content_type = "text/plain"
                                    if file_ext == ".html":
                                        content_type = "text/html"
                                    elif file_ext == ".csv":
                                        content_type = "text/csv"
                                    elif file_ext == ".json":
                                        content_type = "application/json"
                                    elif file_ext == ".md":
                                        content_type = "text/markdown"

                                    # Attach the file - returns path to S3 file
                                    s3_file_path = self.attach_detail_file(
                                        report_block_id=report_block_id,
                                        file_name=relative_file_path, # Use relative path for S3 name
                                        content=content.encode('utf-8'), # Encode string content to bytes
                                        content_type=content_type
                                    )
                                    # File is automatically tracked in ReportBlock.attachedFiles
                                except Exception as e:
                                    self._log(f"Failed to attach text file {file_path}: {e}", level="ERROR")
                                    final_output_data["errors"].append(f"Error attaching {file_path}: {e}")
                            elif file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                                try:
                                    with open(file_path, 'rb') as f:
                                        content = f.read() # Read as bytes
                                    
                                    relative_file_path = str(file_path.relative_to(main_temp_dir))
                                    content_type = "image/png" # Assuming only PNG for now
                                        
                                    # Attach the file - returns path to S3 file
                                    s3_file_path = self.attach_detail_file(
                                        report_block_id=report_block_id,
                                        file_name=relative_file_path,
                                        content=content, # Pass bytes directly
                                        content_type=content_type
                                    )
                                    # File is automatically tracked in ReportBlock.attachedFiles
                                except Exception as e:
                                    self._log(f"Failed to attach image file {file_path}: {e}", level="ERROR")
                                    final_output_data["errors"].append(f"Error attaching {file_path}: {e}")
                            else:
                                self._log(f"Skipping unsupported file type: {file_path}", level="DEBUG")
                                final_output_data["skipped_files"].append(str(file_path))
                # Generate summary based on the number of topics found (only if not task-based)
                topic_count = len(final_output_data.get("topics", []))
                if not self.task_config:  # Only set default summary if no task is provided
                    if topic_count == 0:
                        summary_msg = "Topic analysis completed, but no distinct topics were identified in the data. Consider increasing sample size or adjusting min_topic_size parameter."
                        final_output_data["summary"] = summary_msg
                        self._log(f"⚠️ Analysis Summary: {summary_msg}", "WARNING")
                    elif topic_count == 1:
                        summary_msg = f"Topic analysis completed with {topic_count} topic identified. Limited visualizations available due to single topic. Consider decreasing min_topic_size (currently {min_topic_size}) or increasing sample size."
                        final_output_data["summary"] = summary_msg
                        self._log(f"📋 Analysis Summary: {summary_msg}", "INFO") 
                    else:
                        summary_msg = f"Topic analysis completed successfully with {topic_count} topics identified."
                        final_output_data["summary"] = summary_msg
                        self._log(f"✅ Analysis Summary: {summary_msg}", "INFO")

        except Exception as e:
            error_msg = f"An error occurred during TopicAnalysis block generation: {str(e)}"
            try:
                tb_str = traceback.format_exc()
            except Exception:
                # Defensive handling in case traceback module has scoping issues
                import traceback as tb_module
                tb_str = tb_module.format_exc()
            self._log(error_msg, "ERROR")
            self._log("Traceback:", "ERROR")
            self._log(tb_str, "ERROR")
            final_output_data["errors"].append(error_msg)
            final_output_data["summary"] = "Topic analysis failed."
        finally:
            # --- 6. Clean up temporary directory ---
            try:
                shutil.rmtree(main_temp_dir)
                self._log(f"Successfully cleaned up main temporary directory: {main_temp_dir}")
            except Exception as e:
                self._log(f"Error cleaning up main temporary directory {main_temp_dir}: {e}", level="ERROR")
                final_output_data["errors"].append(f"Cleanup error for {main_temp_dir}: {str(e)}")
        
        # Ensure summary reflects final state if errors occurred
        if final_output_data["errors"] and not final_output_data["summary"].endswith("failed.") and not final_output_data["summary"].endswith("error."):
            if self.task_config:
                final_output_data["summary"] = "Task-based topic analysis completed with errors."
            else:
                final_output_data["summary"] = "Topic analysis completed with errors."

        # Add block metadata for frontend display
        final_output_data["block_title"] = self.config.get("name", self.DEFAULT_NAME)
        
        # Add task-enhanced summary if task was provided
        if self.task_config and final_output_data.get("final_summary"):
            summary_msg = f"Task-based topic analysis completed successfully with {topic_count} topics identified and final summary generated."
            final_output_data["summary"] = summary_msg
            self._log(f"✅ Task-Enhanced Analysis Summary: {summary_msg}", "INFO")
        elif self.task_config:
            # Task was provided but final summary failed
            summary_msg = f"Task-based topic analysis completed with {topic_count} topics identified, but final summary generation failed."
            final_output_data["summary"] = summary_msg
            self._log(f"⚠️ Task-Based Analysis Summary: {summary_msg}", "WARNING")

        # Debug logging to verify hit rate stats are in final output
        self._log("🔍 DEBUG: Final output data structure verification:")
        if "llm_extraction" in final_output_data:
            llm_data = final_output_data["llm_extraction"]
            self._log(f"   • LLM extraction present: True")
            self._log(f"   • Hit rate stats in final output: {'hit_rate_stats' in llm_data}")
            if 'hit_rate_stats' in llm_data:
                hit_stats = llm_data['hit_rate_stats']
                self._log(f"   • Final hit rate: {hit_stats.get('hit_rate_percentage', 'unknown')}%")
                self._log(f"   • Final total processed: {hit_stats.get('total_processed', 'unknown')}")
            else:
                self._log(f"   • LLM extraction keys: {list(llm_data.keys())}")
        else:
            self._log("   • LLM extraction missing from final output")

        # Return YAML formatted output with contextual comments
        try:
            # Custom Dumper to prevent YAML aliases/anchors
            class NoAliasDumper(yaml.SafeDumper):
                def ignore_aliases(self, data):
                    return True

            contextual_comment = """# Topic Analysis Report Output
# 
# This is the structured output from a multi-stage topic analysis pipeline that:
# 1. Preprocesses data through programmatic filtering and preparation
# 2. Extracts content using LLM-powered transformation with custom prompts  
# 3. Discovers topics using BERTopic clustering and analysis
# 4. Fine-tunes topic representations using LLM-based naming models
# 5. Optionally generates task-based final summary (if task configuration provided)
#
# The output contains configuration parameters, extracted examples, discovered topics,
# visualization metadata, task-based summaries, and file attachments from the complete analysis workflow.

"""
            yaml_output = yaml.dump(
                final_output_data, 
                Dumper=NoAliasDumper, 
                indent=2, 
                allow_unicode=True, 
                sort_keys=False
            )
            formatted_output = contextual_comment + yaml_output
        except Exception as e:
            self._log(f"Failed to create YAML formatted output: {e}", level="ERROR")
            # Fallback to basic YAML without comments
            formatted_output = yaml.dump(final_output_data, indent=2, allow_unicode=True, sort_keys=False)

        # Return the formatted YAML output (the frontend expects a YAML string)
        return formatted_output, self._get_log_string()
    
    async def _generate_final_summary(
        self, 
        topics_list: List[Dict[str, Any]], 
        task_context: str, 
        openai_api_key: Optional[str],
        final_summarization_config: Optional[Dict[str, Any]] = None,
        analysis_stats: Optional[Dict[str, Any]] = None,
        full_output_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Generate a final summary using all topic buckets and the task context.
        
        Args:
            topics_list: List of topic dictionaries with names, keywords, and examples
            task_context: The task configuration paragraph providing context
            openai_api_key: OpenAI API key for LLM calls
            final_summarization_config: Configuration for final summarization (model, prompt, etc.)
            analysis_stats: Aggregate statistics from preprocessing, extraction, and analysis
            full_output_data: Complete output data structure (universal code) to pass to LLM
            
        Returns:
            Final summary string or None if generation fails
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            
            # Check if we have an API key
            if not openai_api_key:
                self._log("No OpenAI API key available for final summary generation", level="WARNING")
                return None
            
            # NEW APPROACH: Serialize full_output_data as YAML for the LLM
            # This is much cleaner than building custom text strings
            import yaml
            
            analysis_stats = analysis_stats or {}
            full_output_data = full_output_data or {}
            
            # Build a clean data structure for the LLM prompt
            # Include only the essential data, excluding logs and errors
            prompt_data = {
                'preprocessing': full_output_data.get('preprocessing', {}),
                'llm_extraction': full_output_data.get('llm_extraction', {}),
                'bertopic_analysis': full_output_data.get('bertopic_analysis', {}),
                'topics': topics_list,  # Full topics list with all metrics
                'analysis_metrics': full_output_data.get('analysis_metrics', {}),
            }
            
            # Add fine-tuning comparison if available
            if 'fine_tuning' in full_output_data:
                prompt_data['fine_tuning'] = full_output_data['fine_tuning']
            
            # Serialize to YAML for the prompt
            analysis_results_yaml = yaml.dump(prompt_data, indent=2, allow_unicode=True, sort_keys=False)
            
            self._log(f"📄 Generated YAML representation for LLM prompt ({len(analysis_results_yaml):,} characters)")
            
            # Verify YAML contains key information
            self._log(f"🔍 YAML DATA VERIFICATION:")
            self._log(f"   • Topics in YAML: {len(topics_list)}")
            self._log(f"   • Has analysis_metrics: {'analysis_metrics' in prompt_data}")
            self._log(f"   • Has llm_extraction stats: {'llm_extraction' in prompt_data}")
            self._log(f"   • YAML size: {len(analysis_results_yaml):,} characters")
            
            # Get final summarization configuration
            config = final_summarization_config or {}
            model = config.get("model", "gpt-4o-mini")
            provider = config.get("provider", "openai")
            # Use lower temperature for more factual, data-driven responses
            temperature = config.get("temperature", 0.05)  # Lower default for factual analysis
            custom_prompt = config.get("prompt")
            
            # NEW SIMPLIFIED APPROACH: Use YAML data directly in the prompt
            # No need for complex variable substitution
            
            default_user_prompt = """Based on the topic analysis results below, provide a concise summary.

# Topic Analysis Results (YAML format)

```yaml
{{analysis_results}}
```

## Summary Requirements

1. **Data Overview**: 
   - Explain the distinction between original transcripts (in `llm_extraction.hit_rate_stats.total_processed`) and extracted documents/quotes (in `topics` array)
   - Report the extraction success rate (`llm_extraction.hit_rate_stats.hit_rate_percentage`)

2. **Top Topics**: 
   - Discuss the top 2-3 topics from the `topics` array (sorted by `count`)
   - Use the exact topic `name` and calculate or use `percentage` fields
   - Reference specific `keywords` and `examples` if helpful

3. **Quality Metrics** (if present):
   - If `analysis_metrics.topic_similarity` exists, comment on topic distinctness:
     * `mean_similarity` < 0.3 = highly distinct topics
     * `mean_similarity` > 0.6 = potential topic overlap
     * Check `high_similarity_pairs_count` for specific redundant topics
   - If `analysis_metrics.topic_stability` exists, report the mean_stability score factually without interpretation

4. **Key Insights**: 
   - Interpret patterns from the actual topic distribution
   - Use active voice, not passive

Keep the summary concise and focused on interpretation rather than recommendations.

You are writing copy for a Markdown document that already has an H1 at the top, so your top-level headers should be H2. Don't start with a header, just start with copy.
"""
            
            # Handle custom prompt - ensure it includes analysis_results placeholder
            if custom_prompt:
                if '{{analysis_results}}' not in custom_prompt:
                    self._log("⚠️  WARNING: Custom prompt does not contain {{analysis_results}} placeholder!")
                    self._log("⚠️  Prepending YAML data to custom prompt")
                    # Prepend YAML data to custom prompt
                    user_prompt = "# Topic Analysis Results (YAML format)\n\n```yaml\n{{analysis_results}}\n```\n\n" + custom_prompt
                else:
                    user_prompt = custom_prompt
                    
                self._log("📊 YAML-BASED PROMPT: Custom prompt will receive full analysis_results YAML")
            else:
                user_prompt = default_user_prompt
            
            # Create the prompt template - Use Jinja2 format for consistency with codebase
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", task_context),
                ("user", user_prompt)
            ], template_format="jinja2")
            
            # Verify the prompt template recognizes the analysis_results variable
            expected_variables = prompt_template.input_variables
            required_vars = ['analysis_results']  # Core required variable
            
            missing_required = [var for var in required_vars if var not in expected_variables]
            if missing_required:
                self._log(f"❌ ERROR: LangChain template does not recognize required variables: {missing_required}")
                self._log(f"   Expected variables: {expected_variables}")
                self._log(f"   User prompt preview: {user_prompt[:200]}...")
                raise ValueError(f"Template configuration error: required variables not recognized: {missing_required}")
            else:
                self._log(f"✅ LangChain template correctly recognizes required variables")
                self._log(f"   All template variables: {expected_variables}")
            
            # Initialize the LLM based on provider
            if provider == "openai":
                llm = ChatOpenAI(
                    model=model,
                    api_key=openai_api_key,
                    temperature=temperature
                )
            else:
                # For future extensibility - could add other providers
                self._log(f"Provider {provider} not yet supported, falling back to OpenAI", level="WARNING")
                llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=openai_api_key,
                    temperature=0.1
                )
            
            # Create the chain
            chain = prompt_template | llm
            
            # Generate the summary
            self._log(f"🎯 Generating final summary for {len(topics_list)} topics...")
            self._log(f"   • Model: {model}")
            self._log(f"   • Provider: {provider}")
            self._log(f"   • Temperature: {temperature}")
            self._log(f"   • Custom prompt: {'Yes' if custom_prompt else 'No (using default)'}")
            self._log(f"   • Total YAML data: {len(analysis_results_yaml):,} characters")
            
            # === COMPREHENSIVE LLM DATA VERIFICATION LOGGING ===
            self._log("🔍 LLM DATA VERIFICATION - START")
            self._log("=" * 50)
            
            # 1. Log raw topics_list data structure
            self._log(f"📊 Raw topics_list contains {len(topics_list)} topics:")
            for i, topic in enumerate(topics_list[:3]):
                self._log(f"   [{i}] Topic {topic['id']}: '{topic['name']}' - {topic['count']} docs")
                self._log(f"       Keywords: {topic.get('keywords', [])[:5]}")
                examples = topic.get('examples', [])
                self._log(f"       Examples available: {len(examples)}")
                if examples:
                    self._log(f"       First example: {examples[0].get('text', '')[:100]}...")
            
            # 1.5. Log topic data structure verification
            self._log(f"🔍 TOPIC DATA STRUCTURE VERIFICATION:")
            total_examples_count = sum(len(topic.get('examples', [])) for topic in topics_list)
            self._log(f"   • Total examples across all topics: {total_examples_count}")
            topics_with_examples = sum(1 for topic in topics_list if topic.get('examples'))
            self._log(f"   • Topics with examples: {topics_with_examples}/{len(topics_list)}")
            
            # Verify that all topics have proper structure
            for i, topic in enumerate(topics_list):
                has_name = bool(topic.get('name'))
                has_keywords = bool(topic.get('keywords'))
                has_examples = bool(topic.get('examples'))
                example_count = len(topic.get('examples', []))
                
                if not has_name or not has_keywords or not has_examples:
                    self._log(f"   ⚠️  Topic {topic['id']} missing data: name={has_name}, keywords={has_keywords}, examples={has_examples}")
                elif example_count < 5:
                    self._log(f"   ⚠️  Topic {topic['id']} has only {example_count} examples")
                else:
                    self._log(f"   ✅ Topic {topic['id']} complete: {example_count} examples")
            
            
            # 3. Log the exact prompt template being used
            self._log(f"📋 User prompt template:")
            self._log(f"--- BEGIN USER PROMPT ---")
            self._log(user_prompt[:1000] + "..." if len(user_prompt) > 1000 else user_prompt)
            self._log(f"--- END USER PROMPT ---")
            
            # 4. Prepare template variables with YAML data
            template_vars = {
                'analysis_results': analysis_results_yaml
            }
            
            self._log(f"📨 Template variables prepared:")
            self._log(f"   • analysis_results (YAML): {len(analysis_results_yaml):,} characters")
            
            
            # 5. Log system prompt
            self._log(f"⚙️ System prompt: {task_context[:500]}...")
            
            self._log("🔍 LLM DATA VERIFICATION - END")
            self._log("=" * 50)
            
            # === DEBUG: TEST THE ACTUAL CHAIN INVOCATION ===
            self._log("🔧 CHAIN INVOCATION DEBUG:")
            try:
                # Test what happens when we invoke the chain
                self._log(f"   • About to invoke chain with YAML data length: {len(analysis_results_yaml):,} characters")
                self._log(f"   • Chain input keys expected: {prompt_template.input_variables}")
                
                # Try to format the prompt manually to see what LangChain will actually send
                if hasattr(prompt_template, 'format_messages'):
                    try:
                        formatted_messages = prompt_template.format_messages(**template_vars)
                        self._log(f"   • Successfully formatted {len(formatted_messages)} messages")
                        for i, msg in enumerate(formatted_messages):
                            content = msg.content if hasattr(msg, 'content') else str(msg)
                            self._log(f"     Message {i}: {content[:200]}...")
                    except Exception as format_error:
                        self._log(f"   • Error formatting messages: {format_error}")
                        self._log(f"   • This suggests the template variable is not properly configured")
                
                response = await chain.ainvoke(template_vars)
                self._log(f"   • Chain invocation successful")
                
            except Exception as chain_error:
                self._log(f"   • Chain invocation failed: {chain_error}")
                self._log(f"   • This suggests a template variable mismatch")
                raise
            
            # === LOG LLM RESPONSE ===
            if hasattr(response, 'content'):
                response_text = response.content.strip()
            else:
                response_text = str(response).strip()
            
            self._log("🤖 LLM RESPONSE RECEIVED")
            self._log("=" * 50)
            self._log(f"💬 Response length: {len(response_text)} characters")
            self._log(f"--- BEGIN LLM RESPONSE ---")
            self._log(response_text[:1000] + "..." if len(response_text) > 1000 else response_text)
            self._log(f"--- END LLM RESPONSE ---")
            
            # === VALIDATE RESPONSE AGAINST ACTUAL DATA ===
            self._log("🔍 RESPONSE VALIDATION:")
            sorted_topics_for_validation = sorted(topics_list, key=lambda t: t.get('count', 0), reverse=True)
            self._log(f"Expected top 3 topics by count:")
            for i, topic in enumerate(sorted_topics_for_validation[:3]):
                self._log(f"   {i+1}. Topic {topic['id']}: '{topic['name']}' ({topic['count']} docs)")
            
            # Check if any of the top topic names appear in the response
            top_3_names = [topic['name'] for topic in sorted_topics_for_validation[:3]]
            matches_found = []
            for name in top_3_names:
                if name.lower() in response_text.lower():
                    matches_found.append(name)
            
            self._log(f"Top topic names found in response: {len(matches_found)}/{len(top_3_names)}")
            for match in matches_found:
                self._log(f"   ✓ Found: '{match}'")
            
            if not matches_found:
                self._log("⚠️  WARNING: None of the top 3 topic names appear in the LLM response!")
                self._log("⚠️  This suggests the LLM may not be analyzing the actual data provided.")
            
            self._log("=" * 50)
            
            return response_text
                
        except Exception as e:
            self._log(f"Error in final summary generation: {e}", level="ERROR")
            self._log(f"Traceback: {traceback.format_exc()}", level="ERROR")
            return None

    # Remove custom _log method - now inherited from BaseReportBlock with unified logging 