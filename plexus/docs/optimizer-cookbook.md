=== CHANGE COOKBOOK — OPTIONS TO TRY ===

─────────────────────────────────────────────────────────────────────────────────
SCAN FIRST — MANDATORY PATTERN CHECK (do this before generating any hypotheses):
─────────────────────────────────────────────────────────────────────────────────

Before proposing any hypotheses, scan score_config.yaml for the patterns below.
When a pattern matches, you MUST include the indicated hypothesis in your candidate
set — even if you also include Category A or B hypotheses.
These structural changes are often the highest-leverage option available, and
prompt-level tweaks alone CANNOT fix an underlying input-quality problem.

▶ STALE MODEL SIGNAL → mandatory C3 model-swap hypothesis — CHECK THIS FIRST:

  Add a model-swap hypothesis (highest priority, lowest risk) if score_config.yaml
  contains model_name: gpt-4o-mini or any model that is NOT gpt-5.4-nano or newer.
  This is the cheapest, fastest structural win — 2 lines of YAML, often meaningful gains.
  If the score is already on gpt-5.4-nano, skip this signal. See C3 below.

▶ WORD-LEVEL TIMING SIGNAL → mandatory C1e.1 hypothesis (DeepgramInputSource + format: words):

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
  Word-level Deepgram format (format: words) preserves exact temporal order, making
  it unambiguous which "Yes" followed which school pitch.
  See C1e.1 below for the full YAML snippet.

▶ KEYWORD-FOCUSED SCORE SIGNAL → consider C2 hypothesis (RelevantWindowsTranscriptFilter):

  Add this as one of your hypotheses if ALL of the following are true:
  - The score's classification decision revolves around whether specific words or
    phrases appear in the transcript (e.g., a required disclosure, a specific offer,
    a key question the agent must ask)
  - The transcripts are long (many turns) and the relevant content is a small fraction
  - The RCA shows the LLM missing or misidentifying relevant content amid unrelated text

  The filter extracts only the transcript lines that contain your target keywords,
  plus a configurable window of surrounding lines for context. Removed sections are
  replaced with "..." so the LLM understands the transcript is abbreviated.

  WHY THIS HELPS: Long transcripts push relevant content deep into the LLM's context
  where attention degrades. Trimming to keyword windows keeps the decision-relevant
  text front and center, and also reduces cost and latency.

  WHEN TO USE: Most effective when the score asks "did the agent mention X?" — where
  X maps cleanly to a small vocabulary (specific product words, required phrases,
  topic keywords). Less effective when the relevant content is diffuse or doesn't
  cluster around predictable keywords.

  See C2 below for full YAML syntax and parameter reference.

▶ PHONETIC TRANSCRIPTION ERROR SIGNAL → mandatory Category A hypothesis (fuzzy-matching rule):

  Add this hypothesis if the score evaluates proper nouns that are likely to be
  transcribed as phonetically similar common words. This is extremely common for:
  - School names (e.g., "Fortis College" → "forty's college", "forty college")
  - Company/product names (e.g., "Plexus" → "plexis", "flexus")
  - Program names with uncommon terms (e.g., "Gerontology" → "gynecology")
  - Acronyms that expand into longer phrases ("HVAC" → "heating and cooling")
  - Any proper noun that sounds like a common word when spoken aloud

  If the RCA shows false negatives where the human says the agent DID mention a school
  or product but the LLM said it didn't, the most likely cause is a transcription
  variant the prompt doesn't recognize. The fix is a Category A rule in the system_message
  or user_message instructing the LLM to accept phonetically similar variants, with
  explicit examples of the known substitution patterns visible in the transcripts.

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
  This is ALWAYS slot 4 — every cycle gets one structural hypothesis.
  Pick the most promising option from C1–C4 below that has NOT already been tried.

  C1. Architecture — decomposing the decision into multiple LLM calls:

    The most powerful structural lever is breaking a complicated single prompt into
    multiple focused LLM calls, each responsible for one clear sub-question.

    C1a. Decompose into sequential per-element calls:
      When a score evaluates multiple independent elements (e.g., check each school,
      each required disclosure, each list item), a single LLM call that sees everything
      at once often gets confused. Instead, loop over the elements and make one LLM call
      per element, then aggregate. This mirrors what a human reviewer would do.
      Already present in TactusScore YAML as a Lua `for` loop calling `Agent{...}`.

    C1b. Add an N/A gate as a separate first call:
      When the score has a "Not Applicable" or "N/A" class in addition to Yes/No, a
      single combined prompt must simultaneously reason about applicability AND the
      actual decision, which confuses the model. The fix is a two-pass approach:
        Pass 1 — Applicability gate: "Is this call in scope for this check at all?"
                  If Not Applicable → return N/A immediately (cheap, fast).
        Pass 2 — The real decision: only runs if pass 1 says "yes, this is applicable."
      This is especially valuable when N/A cases are common and easy to detect early.
      Example structure:
        local gate_agent = Agent { provider = "openai", model = "gpt-5.4-nano",
          system_prompt = "Is this call subject to [X] at all? Answer APPLICABLE or NOT_APPLICABLE." }
        local gate = gate_agent({ message = input.text })
        if gate.output:find("NOT_APPLICABLE") then
          return { value = "N/A", explanation = "Out of scope: " .. gate.output }
        end
        -- ... then run the real decision agent ...

    C1c. Add a chain-of-thought extraction step before the final classifier:
      If the decision requires finding specific evidence in a long transcript before
      judging it, split into:
        Step 1 — Extraction: "List every instance of X in this transcript."
        Step 2 — Classification: "Given these instances, was the requirement met?"
      This lets each step focus on one thing and produces more reliable evidence extraction.

    C1d. Split into parallel per-criterion calls (for multi-criteria scores):
      If a score checks 3–5 independent criteria (e.g., branding = school name +
      program + modality + location + affirmative), consider one LLM call per criterion
      rather than asking a single prompt to check all criteria simultaneously.
      Any single criterion failure → overall No. All pass → Yes.
      Tradeoff: more API calls but each is faster, cheaper per call, and more accurate.

  C1e. Input source — control WHAT text the score receives:
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

  C1e.1 — When the rubric involves PRECISE WORD TIMING — upgrade to word-level format:

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

    SOLUTION: Use DeepgramInputSource with format: words.
    This preserves each word's exact sequential position and speaker label, giving the
    LLM the information it needs to reason about who said what and in what order.

    DO NOT add include_timestamps: true by default. Timestamps add tokens that are
    noise to the LLM unless the rubric specifically requires knowing actual clock times
    (e.g., "did this happen within the first 60 seconds of the call?"). For sequential-
    ordering questions — who responded to what — the word sequence itself is sufficient.
    Extra tokens = extra cost + extra distraction with no benefit.

    ⚠ STRUCTURE WARNING — common mistake that will be caught by YAML validation:
    DeepgramInputSource goes in a TOP-LEVEL `item:` section. It does NOT go under
    `data:`, under `tactus_code:`, or anywhere else. The `data:` section is for the
    dataset source only (e.g. CallCriteriaDBCache or FeedbackItems).

    WRONG (will fail validation with PROCESSOR_UNDER_DATA error):
      data:
        class: CallCriteriaDBCache
        ...
        input_source:            # ← WRONG: not a valid key under data:
          class: DeepgramInputSource
          ...

    CORRECT — add a new top-level `item:` section alongside `data:`:
      data:
        class: CallCriteriaDBCache
        searches:
          ...

      item:                      # ← NEW top-level section (same indent level as data:)
        class: DeepgramInputSource
        options:
          pattern: ".*deepgram.*\\.json$"
        processors:
          - class: DeepgramFormatProcessor
            parameters:
              format: words
              speaker_labels: true
              # include_timestamps: true  ← only add if rubric requires clock-time judgements

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

    WHEN TO TRY THIS:
    The keyword-window approach (RelevantWindowsTranscriptFilter) is a solid Category C
    hypothesis when:
      - The score is explicitly about whether a specific topic was discussed (a required
        question, a product offer, a disclosure, a safety check, etc.)
      - The topic maps to a clear keyword vocabulary (synonyms, related terms)
      - Transcripts are long and the relevant content occupies only a small portion

    EXAMPLE: A score that checks whether the agent offered warranty protection.
    Most of the call is unrelated; the warranty topic clusters around words like
    "warranty", "coverage", "protect", "plan", "extend". Filtering to windows around
    those words dramatically reduces noise while keeping the relevant exchange intact.

    The filter replaces omitted sections with "..." so the LLM understands the
    transcript has been abbreviated. The LLM sees context before and after each
    matching window (controlled by prev_count and next_count).

    RULES (enforced by YAML validation — submit will be rejected if violated):
      1. Each entry MUST have a `class` key naming a known processor.
      2. DO NOT invent processor class names — use ONLY the classes listed below.
      3. Processors go under `item:`, NOT at the top level or under `data:`.
      4. RelevantWindowsTranscriptFilter REQUIRES a `keywords` parameter (a YAML list).
      5. If submit_score_version rejects with a processor error, fix the YAML — do not
         try to work around it by inventing code or alternative classes.

    ── GROUP A: Text filtering (most useful for optimization) ──

    RelevantWindowsTranscriptFilter
      Extracts only the transcript lines containing target keywords, plus surrounding
      context lines. Omitted sections are replaced with "..." markers.
      Parameters:
        keywords       (REQUIRED, list of strings) — terms to search for in each line
        fuzzy_match    (optional, bool, default false) — enable fuzzy string matching
        fuzzy_threshold (optional, int 0-100, default 80) — minimum similarity score
        case_sensitive (optional, bool, default false) — case-sensitive keyword matching
        prev_count     (optional, int, default 1) — lines to include BEFORE each match
        next_count     (optional, int, default 1) — lines to include AFTER each match
        window_unit    (optional, string, default 'sentences') — unit for context window:
                         'sentences' — include N surrounding lines (default, most useful)
                         'words'     — include N surrounding words
                         'characters' — include N surrounding characters

      When to use fuzzy_match: Enable it when keywords may be phonetically transcribed
      (e.g., a brand name mangled in speech-to-text). Use a threshold of 75-85 to
      catch variants without too many false matches.

      Complete working example — warranty offer check:
        item:
          processors:
            - class: RelevantWindowsTranscriptFilter
              parameters:
                keywords: ["warranty", "coverage", "protection plan", "extend", "protect"]
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

    ── GROUP D: Deepgram processors (require DeepgramInputSource — see C1e above) ──
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
                        Adds '[X.XXs]' timestamp to each unit.
                        ⚠ DO NOT enable this unless the rubric requires actual clock-time
                        judgements (e.g., "did X happen within the first 60 seconds?").
                        For sequential-ordering questions (which response followed which
                        item), the word order alone is sufficient — timestamps add tokens
                        that cost money and distract the LLM with irrelevant numbers.
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

  C4. Full rewrite — nuclear option (only when iterations have plateaued):
    ⚠ DO NOT use this in the first 2–3 cycles. It is a last resort.

    WHEN TO USE: You have run 3 or more cycles, tried structural and prompt changes,
    and accuracy/feedback metrics are stuck — improvements in one area keep regressing
    another, or every hypothesis produces near-zero net change. When the score feels
    like it has accumulated too many band-aids and is fighting itself, the right move
    is to discard everything from `tactus_code:` onward and write it fresh.

    WHAT "full rewrite" means:
      - Keep ONLY the header metadata (name, key, id, description, class, model settings,
        valid_classes, max_tokens, output: section, and data: section)
      - DELETE everything in `tactus_code:` and write it from scratch
      - Base the new implementation entirely on the classification guidelines and the
        confusion matrix evidence — not on what was there before
      - Choose the cleanest architecture for the problem (single call, multi-call,
        N/A gate, etc.) without trying to preserve any prior structure

    WHY: Scores that were implemented long ago or that have been iteratively patched
    can accumulate contradictions, dead code, and structural assumptions that no longer
    fit the rubric. Incremental editing cannot fix a fundamentally wrong architecture —
    it just adds more complexity on top of the same broken foundation. Starting from
    scratch with a clean implementation based on current guidelines is often the
    highest-leverage move after a plateau.

    HOW: Write the new `tactus_code:` in one edit using `str_replace_editor` to
    replace the entire block. Do not carry forward any of the old code. Build it as
    if you are implementing the score for the first time, using only the guidelines
    and the confusion matrix to guide the design.

THINGS YOU CANNOT CHANGE (do NOT propose hypotheses targeting these):
  - Parser/output normalization logic (parse_final_value, label parsing, case normalization)
    These are in Python framework code, NOT in score_config.yaml. You cannot edit them.
  - The classification guidelines — they are for reference only, not editable.
  - Infrastructure code outside the YAML config file.
  If the RCA mentions output parsing issues, address them by adjusting the LLM prompt to
  produce cleaner output, NOT by trying to modify the parser.

IMPORTANT: The classification guidelines above are for reference only — they help you understand policy but are not editable.
You will edit score_config.yaml (shown between the === markers above).
Do NOT rewrite the entire user_message as a Category A or B hypothesis — full prompt rewrites
consistently regress. The only time a full rewrite is appropriate is as a Category C / C4
structural hypothesis after multiple cycles have plateaued (see C4 above).

GUIDELINES → PROMPT ALIGNMENT: If classification guidelines exist above, they are the authoritative
source of policy for this score. Cross-reference them against the system_message and user_message
in score_config.yaml. If the guidelines describe policies, decision criteria, edge cases, or
examples that are NOT already reflected in the prompt messages, that is a high-value hypothesis:
add the missing policy information to the prompts. The LLM can only follow rules it can see.
This is often the single highest-impact change you can make — before trying prompt rewording or
model swaps, check whether the prompts actually contain all the decision rules from the guidelines.
