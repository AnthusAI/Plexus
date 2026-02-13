"""
Core LoRA fine-tuning logic shared by local and SageMaker trainers.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def train_lora_adapter(*,
                       base_model_hf_id: str,
                       training_file: str,
                       validation_file: Optional[str],
                       output_dir: str,
                       lora_config: Dict[str, Any],
                       training_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Train a LoRA adapter using chat-style JSONL data.

    Args:
        base_model_hf_id: HuggingFace model ID
        training_file: Path to training.jsonl
        validation_file: Optional path to validation.jsonl
        output_dir: Directory to write adapter artifacts
        lora_config: LoRA hyperparameters
        training_config: Training hyperparameters

    Returns:
        Training metrics dict
    """
    import torch
    from peft import LoraConfig, get_peft_model, TaskType
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        TrainingArguments,
        Trainer as HFTrainer,
        DataCollatorForSeq2Seq,
    )
    from datasets import load_dataset

    os.makedirs(output_dir, exist_ok=True)

    hf_token = os.environ.get('HF_TOKEN')
    tokenizer = AutoTokenizer.from_pretrained(base_model_hf_id, token=hf_token)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    quantization = training_config.get("quantization")
    if quantization == "4bit":
        from transformers import BitsAndBytesConfig
        compute_dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
        )
        model = AutoModelForCausalLM.from_pretrained(
            base_model_hf_id,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            token=hf_token
        )
    elif quantization == "8bit":
        from transformers import BitsAndBytesConfig
        bnb_config = BitsAndBytesConfig(load_in_8bit=True)
        model = AutoModelForCausalLM.from_pretrained(
            base_model_hf_id,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            token=hf_token
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            base_model_hf_id,
            torch_dtype=torch_dtype,
            trust_remote_code=True,
            token=hf_token
        )

    # Optional memory-saving settings
    if training_config.get('gradient_checkpointing'):
        try:
            model.gradient_checkpointing_enable()
            model.config.use_cache = False
        except Exception:
            pass

    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_config.get('r', 64),
        lora_alpha=lora_config.get('lora_alpha', 16),
        lora_dropout=lora_config.get('lora_dropout', 0.1),
        target_modules=lora_config.get(
            'target_modules',
            [
                "q_proj", "v_proj", "k_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"
            ]
        ),
        bias="none",
        inference_mode=False,
    )
    model = get_peft_model(model, lora_cfg)

    data_files = {"train": training_file}
    if validation_file:
        data_files["validation"] = validation_file

    dataset = load_dataset("json", data_files=data_files)

    max_seq_length = training_config.get('max_seq_length', 2048)

    def _apply_chat(messages, add_generation_prompt: bool) -> list:
        if hasattr(tokenizer, "apply_chat_template"):
            try:
                return tokenizer.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=add_generation_prompt
                )
            except Exception:
                pass
        text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        return tokenizer(text, add_special_tokens=False).input_ids

    def _format_example(example: Dict[str, Any]) -> Dict[str, Any]:
        messages = example.get('messages', [])
        if not messages or messages[-1].get('role') != 'assistant':
            return {"input_ids": [], "labels": [], "attention_mask": []}

        prompt_messages = messages[:-1]
        prompt_ids = _apply_chat(prompt_messages, add_generation_prompt=True)
        full_ids = _apply_chat(messages, add_generation_prompt=False)

        labels = list(full_ids)
        for i in range(min(len(prompt_ids), len(labels))):
            labels[i] = -100

        if len(full_ids) > max_seq_length:
            overflow = len(full_ids) - max_seq_length
            full_ids = full_ids[overflow:]
            labels = labels[overflow:]

        attention_mask = [1] * len(full_ids)
        return {
            "input_ids": full_ids,
            "labels": labels,
            "attention_mask": attention_mask,
        }

    tokenized = dataset.map(_format_example, remove_columns=dataset["train"].column_names)
    tokenized = tokenized.filter(lambda x: len(x["input_ids"]) > 0)

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        label_pad_token_id=-100,
    )

    epochs = training_config.get('epochs', 3)
    batch_size = training_config.get('batch_size', 1)
    learning_rate = training_config.get('learning_rate', 2e-4)
    grad_accum = training_config.get('gradient_accumulation_steps', 4)

    use_fp16 = torch.cuda.is_available()
    training_args_kwargs = dict(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=learning_rate,
        logging_steps=training_config.get('logging_steps', 10),
        save_steps=training_config.get('save_steps', 200),
        save_total_limit=training_config.get('save_total_limit', 2),
        fp16=use_fp16,
        bf16=False,
        report_to=[],
    )

    has_validation = "validation" in tokenized
    if "evaluation_strategy" in TrainingArguments.__init__.__code__.co_varnames:
        training_args_kwargs["evaluation_strategy"] = "steps" if has_validation else "no"
        training_args_kwargs["eval_steps"] = training_config.get('eval_steps', 200)
    elif "eval_strategy" in TrainingArguments.__init__.__code__.co_varnames:
        training_args_kwargs["eval_strategy"] = "steps" if has_validation else "no"
        training_args_kwargs["eval_steps"] = training_config.get('eval_steps', 200)

    training_args = TrainingArguments(**training_args_kwargs)

    trainer = HFTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized.get("validation"),
        data_collator=data_collator,
    )

    train_result = trainer.train()
    metrics = train_result.metrics or {}

    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    info_path = os.path.join(output_dir, "training_info.json")
    with open(info_path, "w") as f:
        json.dump({
            "base_model": base_model_hf_id,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "metrics": metrics,
        }, f, indent=2)

    logger.info(f"LoRA adapter saved to {output_dir}")
    return metrics
