-- Rubric-memory SME question gate.
-- {{PROVIDER}} and {{MODEL}} are substituted by Python before execution.

gate_agent = Agent {
    provider = "{{PROVIDER}}",
    model = "{{MODEL}}",
    model_type = "responses",
    temperature = 1.0,
    max_tokens = {{MAX_TOKENS}},
    system_prompt = [[
You gate proposed SME agenda questions using rubric-memory evidence.

Rules:
- The official score version rubric is canonical policy authority.
- Corpus evidence can explain historical intent, client conversations, scripts, exceptions, disputes, stale areas, and gaps.
- Do not ask SMEs questions already answered by the official rubric.
- If corpus evidence answers a question but the rubric is unclear or missing that detail, transform the item into a rubric codification/update decision.
- Keep questions only when they represent a true open question, conflicting evidence, stale-rubric issue, or unresolved policy ambiguity.
- Every policy-memory claim must cite exact citation IDs from citation_index.
- Use action "suppress" only when no SME decision remains.
- Use action "transform" when the original question should become a clearer codification/update/confirmation decision.
- Use action "keep" when the question is still genuinely unresolved.
- Return concise final_agenda_markdown suitable for humans.
- Return only valid JSON. Do not return Markdown outside JSON.
]],
    output = {
        text = field.string{required = true},
    },
}

Procedure {
    input = {
        gate_input_json = field.string{required = true},
    },
    output = {
        text = field.string{required = true},
    },
    function(input)
        local gate_message = input.gate_input_json .. [[

Return a JSON object with:
{
  "items": [
    {
      "id": "...",
      "original_text": "...",
      "final_text": "...",
      "action": "suppress|transform|keep",
      "answer_status": "answered_by_rubric|answered_by_corpus|partially_answered|conflicting_evidence|true_open_question",
      "rationale": "...",
      "citation_ids": ["..."]
    }
  ],
  "final_agenda_markdown": "..."
}

If every item is suppressed, final_agenda_markdown must be "(No SME decisions needed this cycle)".
]]

        local function get_field(value, key)
            if value == nil then
                return nil
            end
            local ok, field_value = pcall(function()
                return value[key]
            end)
            if ok then
                return field_value
            end
            return nil
        end

        local result = gate_agent({ message = gate_message })
        local output = get_field(result, "output") or result
        local text = get_field(output, "text") or get_field(output, "response") or output

        if type(text) ~= "string" then
            local ok_json, encoded = pcall(function()
                return Json.encode(text)
            end)
            if ok_json and type(encoded) == "string" then
                text = encoded
            else
                text = tostring(text or "")
            end
        end
        return { text = text }
    end
}
