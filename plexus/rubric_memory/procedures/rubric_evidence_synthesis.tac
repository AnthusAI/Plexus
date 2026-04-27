-- Rubric evidence pack synthesis.
-- {{PROVIDER}} and {{MODEL}} are substituted by Python before execution.

finish = Tool {
    name = "finish",
    description = "Return the final RubricEvidencePack JSON.",
    input = {
        pack_json = field.string{
            required = true,
            description = "The complete RubricEvidencePack JSON string."
        },
    },
    function(args)
        return { pack_json = args.pack_json }
    end
}

synthesizer = Agent {
    provider = "{{PROVIDER}}",
    model = "{{MODEL}}",
    model_type = "chat",
    temperature = 1.0,
    max_tokens = {{MAX_TOKENS}},
    system_prompt = [[
You synthesize RubricEvidencePack JSON for Plexus.

Rules:
- The request.score_version_id and request.rubric_text are the official, versioned rubric authority.
- Corpus evidence can explain interpretation, rationale, history, exceptions, disputes, stale areas, and gaps.
- Corpus evidence cannot override the official rubric by itself.
- Use "rubric_supported" when the official rubric directly supports the feedback classification.
- Use "rubric_conflicting" when evidence conflicts with the official rubric or the disputed classification.
- Use "rubric_gap" when the official rubric lacks enough policy detail.
- Use "historical_context" when evidence explains rationale or interpretation without conflict.
- Use "possible_stale_rubric" when corpus evidence suggests the official rubric may need updating.
- Preserve source_uri, scope_level, source_type, authority_level, source_timestamp, author, retrieval_score, and policy_concepts when returning evidence.
- Sparse evidence must produce low confidence and open questions instead of a confident policy claim.
- Use output_template as the exact JSON shape.
- Fill empty text fields with concise analysis.
- Leave supporting_evidence and conflicting_evidence empty. Python attaches evidence provenance after synthesis.
- Return only valid JSON matching output_contract. Do not return Markdown or commentary.
]],
    tools = {finish},
}

Procedure {
    input = {
        synthesis_input_json = field.string{required = true},
    },
    output = {
        text = field.string{required = true},
    },
    function(input)
        local function extract_text(value, depth)
            depth = depth or 0
            if value == nil or depth > 6 then
                return ""
            end

            local value_type = type(value)
            if value_type == "string" then
                return value
            end
            if value_type == "number" or value_type == "boolean" then
                return tostring(value)
            end
            if value_type ~= "table" then
                return ""
            end

            local preferred_keys = { "reason", "text", "output", "content", "message", "result" }
            for _, key in ipairs(preferred_keys) do
                local extracted = extract_text(value[key], depth + 1)
                if extracted ~= "" then
                    return extracted
                end
            end

            for _, nested in pairs(value) do
                local extracted = extract_text(nested, depth + 1)
                if extracted ~= "" then
                    return extracted
                end
            end

            return ""
        end

        local synthesis_message = input.synthesis_input_json .. [[

You must call the finish tool exactly once.
The finish tool has a required argument named pack_json.
Set pack_json to the complete RubricEvidencePack JSON string.
Start from output_template and fill in the empty fields.
Do not copy raw evidence objects into supporting_evidence or conflicting_evidence.
]]

        synthesizer({ message = synthesis_message })
        local text = tostring(finish.last_call() or "")

        if type(text) ~= "string" then
            text = tostring(text or "")
        end
        return { text = text }
    end
}
