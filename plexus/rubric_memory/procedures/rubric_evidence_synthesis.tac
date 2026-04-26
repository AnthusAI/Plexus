-- Rubric evidence pack synthesis.
-- {{PROVIDER}} and {{MODEL}} are substituted by Python before execution.

local done = require("tactus.tools.done")

synthesizer = Agent {
    provider = "{{PROVIDER}}",
    model = "{{MODEL}}",
    model_type = "chat",
    temperature = 0.0,
    max_tokens = 4096,
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
- Return only valid JSON matching response_schema. Do not return Markdown or commentary.
]],
    initial_message = "{synthesis_input_json}\n\nCall the done tool with only the RubricEvidencePack JSON as the reason.",
    tools = {done},
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

        local max_turns = 3
        local turn_count = 0
        while not done.called() and turn_count < max_turns do
            synthesizer()
            turn_count = turn_count + 1
        end

        local last = done.last_result()
        local text = extract_text(last)
        if text == "" and last ~= nil and type(last) ~= "table" then
            text = tostring(last)
        end

        if type(text) ~= "string" then
            text = tostring(text or "")
        end
        if string.find(string.lower(text), "<lua table at ", 1, true) then
            text = ""
        end
        return { text = text }
    end
}
