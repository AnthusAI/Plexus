=== CHANGE COOKBOOK — OPTIONS TO TRY ===

─────────────────────────────────────────────────────────────────────────────────
SCAN FIRST — MANDATORY PATTERN CHECK (do this before generating any hypotheses):
─────────────────────────────────────────────────────────────────────────────────

Before proposing any hypotheses, scan score_config.yaml for the patterns below.
When a pattern matches, you MUST include the indicated hypothesis in your candidate
set — even if you also include Category A or B hypotheses.
These structural changes are often the highest-leverage option available, and
prompt-level tweaks alone CANNOT fix an underlying input-quality problem.

▶ WORD-LEVEL TIMING SIGNAL → mandatory C1b.1 hypothesis (DeepgramInputSource + words + timestamps):

  Add this hypothesis if the score config contains ANY of the following:
  - language like "each [X] requires its own individual affirmative response"
  - language like "cannot group multiple [X] together for a single response"
  - language like "individual" + "affirmative" + "each" in proximity
  - any rubric requiring knowledge of WHICH short response ("Yes", "I agree", etc.)
    followed WHICH specific item in a list (school, product, disclosure, offer, etc.)
  - any rubric checking sequential per-item acknowledgment or per-item consent
  - any rubric involving interruptions, crosstalk, or overlap between speakers
  - any rubric that asks whether a speaker finished before another speaker started

  WHY THIS MATTERS: The default `text` transcript is produced at sentence/paragraph
  level. Short responses like "Yes" or "I agree" get repositioned by the sentence-
  grouping algorithm — they may appear adjacent to the WRONG list item in the text.
  Prompt fixes that say "be careful which Yes goes with which school" CANNOT work if
  the transcript doesn't show the correct temporal order to begin with.
  Word-level Deepgram format (format: words + include_timestamps: true) preserves
  exact temporal order, making it unambiguous which "Yes" followed which school pitch.
  See C1b.1 below for the full YAML snippet.

▶ LONG/NOISY TRANSCRIPT SIGNAL → consider C2 hypothesis (RelevantWindowsTranscriptFilter):

  Add this as one of your hypotheses if:
  - The transcripts are long (>2000 words) and the score only cares about a small section
  - The RCA shows the LLM getting confused by irrelevant parts of the call
  - The rubric is about a specific topic (repairs, disclosures, school pitches, etc.)
    that appears in only part of a long transcript

  The filter extracts only the transcript windows around keywords you specify, greatly
  reducing noise without losing the relevant content. See C2 below for YAML details.

▶ STALE MODEL SIGNAL → mandatory C3 model-swap hypothesis (gpt-5.4-nano):

  Add this hypothesis if score_config.yaml contains model_name: gpt-4o-mini or any
  model that is NOT gpt-5.4-nano or newer. Switching to gpt-5.4-nano is cheap and
  often produces meaningful accuracy gains. See C3 below.

─────────────────────────────────────────────────────────────────────────────────

DIRECTIONAL AWARENESS: The Feedback RCA above is grouped by confusion matrix segment
(e.g., 'Predicted: Yes / Actual: No' vs 'Predicted: No / Actual: Yes').
Each segment represents a distinct error direction. Fixes for one segment often
pull in the OPPOSITE direction from fixes for another. Target ONE segment per hypothesis.

CATEGORY A — Incremental prompt fix (low risk, targets the #1 RCA issue):
  Target the LARGEST category of misclassification from the RCA.
  PREFERRED (try these first):
  * Identify a MISSING POLICY: Does the rubric fail to cover a pattern the RCA reveals?
    Add a rule that defines the correct behavior for that pattern.
  * Clarify an AMBIGUOUS CRITERION: Is an existing rule unclear about what 'counts'?
    Sharpen the language so the model applies it consistently.
  * Tighten language on an existing condition to reduce mis-application.
  LAST RESORT (few-shot examples):
  * Only add examples for SPEECH-TO-TEXT ERROR patterns — where a specific name or
    phrase is consistently mangled phonetically in transcripts. Maximum 2 examples.
  * DO NOT add examples for general classification edge cases — a policy rule
    generalizes; an example only helps items that closely resemble it and risks
    overfitting that hurts the regression (accuracy) dataset.
  DO NOT add examples for patterns already explicitly handled in the current YAML.

CATEGORY B — Bold prompt overhaul (medium risk, high upside):
  Take a bigger step: attempt changes that could address MULTIPLE top-priority RCA issues at once.
  * Reorganize the prompt structure to be clearer
  * Add a decision framework that covers several edge cases
  * Rewrite a section of the system_message or user_message to eliminate ambiguity
  Be willing to take more risks here — this is your swing-for-the-fences hypothesis.

CATEGORY C — Structural / non-prompt change (higher risk, highest upside):
  Changes to control flow, data preprocessing, or the model itself.

  C1. Architecture changes:
    * Split a single Classifier into multiple graph nodes (extraction + matching)
    * Add a chain-of-thought step that reasons about ambiguous cases before classifying
    * New graph nodes use class: Classifier with their own system_message and user_message

  C1b. Input source — control WHAT text the score receives:
    The `item:` section of the YAML controls where the score gets its input text from.
    By default, scores use the item's `text` field directly. But you can switch the input
    source to `DeepgramInputSource`, which loads the original Deepgram JSON from the item's
    attached files and makes it available for Deepgram processors to format.

    DeepgramInputSource — load raw Deepgram transcript data:
      Extracts the Deepgram JSON attachment from an item's attached files and provides
      both the raw transcript and the full structured Deepgram metadata (words, sentences,
      paragraphs, speaker info, timestamps) for downstream processors.
      Parameters:
        pattern  (REQUIRED, string) — regex to match the Deepgram JSON filename
      YAML structure (note: class and options are at the item level, NOT under processors):
        item:
          class: DeepgramInputSource
          options:
            pattern: ".*deepgram.*\\.json$"
          processors:
            - class: DeepgramFormatProcessor
              parameters:
                format: sentences
                speaker_labels: true

    WHY use DeepgramInputSource?
    The default item.text is a pre-formatted transcript with fixed formatting choices.
    With DeepgramInputSource + processors, you control:
      * Text granularity: paragraphs vs. sentences vs. individual words
      * Speaker filtering: all speakers, agent only (channel 0), or customer only (channel 1)
      * Time slicing: first N seconds, last N seconds, or a specific time range
      * Speaker labels: include or strip 'Speaker 0:'/'Speaker 1:' prefixes
      * Timestamps: include '[X.XXs]' markers for temporal context
    This is especially valuable when the default transcript is noisy or too long for the LLM.

  C1b.1 — When the rubric involves PRECISE WORD TIMING — upgrade to word-level format:

    If the score must decide based on WHEN words were spoken relative to each other —
    for example:
      * Interruption detection: did Speaker A start speaking before Speaker B finished?
      * Sequential acknowledgment: did the agent confirm each item in a list, one by one?
      * Overlap/crosstalk: were two people speaking simultaneously?
      * Any judgment that requires seeing exact temporal ordering of words across speakers

    → The default "sentences" (or "paragraphs") DeepGram format WILL NOT WORK.

    WHY: Deepgram's sentence/paragraph grouping intentionally re-segments words into
    natural-sounding sentence boundaries WITHOUT preserving exact overlap/interruption timing.
    Two speakers whose words overlapped in time may appear sequential in the transcript.
    An interruption can become invisible. List items acknowledged out-of-order may look
    sequential. The "sentences" format is designed for readability — it sacrifices timing
    fidelity to produce clean sentence boundaries.

    SOLUTION: Use DeepgramInputSource with format: words + include_timestamps: true.
    This preserves each word's exact start/end time and speaker label, giving the LLM
    the information it needs to reason about timing:

      item:
        class: DeepgramInputSource
        options:
          pattern: ".*deepgram.*\\.json$"
        processors:
          - class: DeepgramFormatProcessor
            parameters:
              format: words
              speaker_labels: true
              include_timestamps: true

    WHEN TO TRY THIS: If the score's rubric or classification guidelines mention any of the
    following concepts, this is a high-value hypothesis — try it early:
      - "interrupted", "cut off", "talked over", "interjected"
      - "acknowledged each", "confirmed each item", "went through the list", "covered all items"
      - "each [item] requires its own [response/confirmation]" — individual per-item affirmation
      - Scores that check whether a RESPONSE was for a SPECIFIC item vs. grouped items
        (e.g., "each school requires its own individual affirmative response" — the LLM needs
         to know which "Yes" came after which pitch, and sentence-level grouping obscures this
         by repositioning short responses away from the pitches they actually followed)
      - "before [speaker] finished", "while [speaker] was still talking"
      - "overlapping speech", "simultaneous", "both speaking at once"
      - Any temporal relationship between speaker turns that depends on knowing WHEN words occurred

  C2. Text preprocessing with the processors pipeline:
    Scores can preprocess the input text BEFORE it reaches the LLM using the `item.processors` list.
    This is powerful for long transcripts — trim the text to only the relevant parts.
    Processors run in order; each transforms the text before the next one sees it.

    RULES (enforced by YAML validation — submit will be rejected if violated):
      1. Each entry MUST have a `class` key naming a known processor.
      2. DO NOT invent processor class names — use ONLY the classes listed below.
      3. Processors go under `item:`, NOT at the top level or under `data:`.
      4. RelevantWindowsTranscriptFilter REQUIRES a `keywords` parameter (a YAML list).
      5. If submit_score_version rejects with a processor error, fix the YAML — do not
         try to work around it by inventing code or alternative classes.

    ── GROUP A: Text filtering (most useful for optimization) ──

    RelevantWindowsTranscriptFilter
      Extracts only the parts of a long transcript that mention relevant keywords.
      Dramatically reduces noise so the LLM focuses on what matters.
      Parameters:
        keywords     (REQUIRED, list of strings) — terms to search for in each sentence
        fuzzy_match  (optional, bool, default false) — enable fuzzy string matching
        fuzzy_threshold (optional, int 0-100, default 80) — minimum similarity score
        prev_count   (optional, int, default 1) — sentences to include BEFORE a match
        next_count   (optional, int, default 1) — sentences to include AFTER a match
      Complete working example:
        item:
          processors:
            - class: RelevantWindowsTranscriptFilter
              parameters:
                keywords: ["repair", "fix", "replace", "broken"]   # REQUIRED
                fuzzy_match: true
                fuzzy_threshold: 80
                prev_count: 2
                next_count: 2

    FilterCustomerOnlyProcessor
      Keeps only customer/caller speech turns; removes agent/representative lines.
      No parameters required. Useful when only the customer's words matter for the score.

    RemoveSpeakerIdentifiersTranscriptFilter
      Strips speaker labels like 'Agent:', 'Customer:', 'Speaker 1:' from each line.
      No parameters required. Often combined with FilterCustomerOnlyProcessor.

    Example — keep only customer speech with labels removed:
        item:
          processors:
            - class: FilterCustomerOnlyProcessor
            - class: RemoveSpeakerIdentifiersTranscriptFilter

    ── GROUP B: Text normalization ──

    ExpandContractionsProcessor
      Expands contractions: "don't" → "do not", "I'm" → "I am", etc.
      No parameters. Low risk — useful if the LLM is tripping on contractions.

    RemoveStopWordsTranscriptFilter
      Removes common English filler words (the, is, at, etc.).
      No parameters. Can be aggressive — only use when noise words are hurting classification.

    ── GROUP C: Speaker label manipulation ──

    AddUnknownSpeakerIdentifiersTranscriptFilter
      Replaces all speaker labels with 'Unknown Speaker:'. No parameters.

    AddEnumeratedSpeakerIdentifiersTranscriptFilter
      Maps speaker labels to 'Speaker A:', 'Speaker B:', etc. by order of appearance.
      No parameters. Useful when the original labels are inconsistent or confusing.

    ── GROUP D: Deepgram processors (require DeepgramInputSource — see C1b above) ──
    These processors operate on the structured Deepgram JSON in metadata.deepgram.
    They ONLY work when the score uses `item.class: DeepgramInputSource`.
    If the score uses plain text (no item.class), these processors will silently pass through.

    DeepgramFormatProcessor
      Converts structured Deepgram data into formatted text for the LLM.
      This is the primary way to control how the transcript looks when it reaches the prompt.
      Parameters:
        format         (optional, string, default 'paragraphs')
                        'paragraphs' — groups sentences into speaker paragraphs, separated by blank lines.
                                        Most human-readable. Best for full-context analysis.
                        'sentences'  — one sentence per line, chronological order.
                                        Better for sentence-level analysis and keyword matching.
                        'words'      — space-separated words, minimal structure.
                                        Compact but loses sentence boundaries.
        speaker_labels  (optional, bool, default false)
                        Adds 'Speaker 0:' / 'Speaker 1:' prefix to each unit.
                        In stereo recordings: Speaker 0 = agent, Speaker 1 = customer.
        include_timestamps (optional, bool, default false)
                        Adds '[X.XXs]' timestamp to each unit. Useful for temporal analysis.
        channel         (optional, int, default null — include all channels)
                        0 = agent channel only, 1 = customer channel only.
                        null/omitted = merge all channels chronologically.
      Example — sentences with speaker labels, customer only:
        item:
          class: DeepgramInputSource
          options:
            pattern: ".*deepgram.*\\.json$"
          processors:
            - class: DeepgramFormatProcessor
              parameters:
                format: sentences
                speaker_labels: true
                channel: 1

    DeepgramTimeSliceProcessor
      Filters the Deepgram data to a specific time window BEFORE formatting.
      Must be placed BEFORE DeepgramFormatProcessor in the pipeline.
      Parameters:
        start  (optional, float, default 0.0) — start time in seconds
        end    (optional, float) — end time in seconds (exclusive)
        last   (optional, float) — last N seconds of the call (overrides start/end)
      Example — last 60 seconds of the call, formatted as paragraphs:
        item:
          class: DeepgramInputSource
          options:
            pattern: ".*deepgram.*\\.json$"
          processors:
            - class: DeepgramTimeSliceProcessor
              parameters:
                last: 60
            - class: DeepgramFormatProcessor
              parameters:
                format: paragraphs
                speaker_labels: true

    PIPELINE ORDER for Deepgram: DeepgramTimeSliceProcessor → DeepgramFormatProcessor → other processors
    (TimeSlice operates on structured JSON, so it must come before Format converts to text.)

  C2b. Transcription error / redaction resilience (prompt-level):
    If the RCA shows misclassifications caused by garbled speech-to-text output or redacted PII,
    add instructions to the system_message or user_message warning the model that the transcript
    may contain STT errors or redacted text (e.g., [REDACTED], ***). Instruct the model to infer
    the likely intended phrase before classifying. This is a low-risk prompt addition.
    Example addition to system_message:
      'Note: Transcripts may contain speech-to-text errors (e.g., homophones, truncated words)
       or redacted personally identifiable information. When you encounter garbled or redacted
       text, infer the most likely intended meaning from surrounding context before classifying.'

  C3. Model swap (use sparingly — only when prompt/structure changes have stagnated):
    First check score_config.yaml above for the current model_name. Then swap to a DIFFERENT model.
    PREFERRED MODEL: gpt-5.4-nano is the preferred default model. If the score is not already using
    gpt-5.4-nano, switching to it should be your FIRST model swap hypothesis.
    Available models (only propose one that is NOT already in use):
    * gpt-5.4-nano (preferred, fast, cheapest): model_provider: ChatOpenAI, model_name: gpt-5.4-nano, max_tokens: 2000
    * gpt-5-mini (good value): model_provider: ChatOpenAI, model_name: gpt-5-mini, max_tokens: 2000
    * gpt-4o-mini: model_provider: ChatOpenAI, model_name: gpt-4o-mini-2024-07-18
    * gpt-5.4-mini (stronger, more expensive — only if nano + prompt changes are exhausted):
      model_provider: ChatOpenAI, model_name: gpt-5.4-mini, max_tokens: 2000
    * gpt-oss-120b via Bedrock: model_provider: BedrockChat, model_name: openai.gpt-oss-120b-1:0
      (For Bedrock models: remove the temperature field — it is not supported)
    AVOID unless nothing else works (expensive):
    * Claude 3.5 Haiku: model_provider: BedrockChat, model_name: us.anthropic.claude-3-5-haiku-20241022-v1:0

THINGS YOU CANNOT CHANGE (do NOT propose hypotheses targeting these):
  - Parser/output normalization logic (parse_final_value, label parsing, case normalization)
    These are in Python framework code, NOT in score_config.yaml. You cannot edit them.
  - The classification guidelines — they are for reference only, not editable.
  - Infrastructure code outside the YAML config file.
  If the RCA mentions output parsing issues, address them by adjusting the LLM prompt to
  produce cleaner output, NOT by trying to modify the parser.

IMPORTANT: The classification guidelines above are for reference only — they help you understand policy but are not editable.
You will edit score_config.yaml (shown between the === markers above).
Do NOT rewrite the entire user_message — full rewrites consistently regress.

GUIDELINES → PROMPT ALIGNMENT: If classification guidelines exist above, they are the authoritative
source of policy for this score. Cross-reference them against the system_message and user_message
in score_config.yaml. If the guidelines describe policies, decision criteria, edge cases, or
examples that are NOT already reflected in the prompt messages, that is a high-value hypothesis:
add the missing policy information to the prompts. The LLM can only follow rules it can see.
This is often the single highest-impact change you can make — before trying prompt rewording or
model swaps, check whether the prompts actually contain all the decision rules from the guidelines.
