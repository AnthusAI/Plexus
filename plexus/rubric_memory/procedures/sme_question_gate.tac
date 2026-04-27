-- Rubric-memory SME question gate.
-- {{PROVIDER}} and {{MODEL}} are substituted by Python before execution.

finish = Tool {
    name = "finish",
    description = "Return the final SME question gate JSON.",
    input = {
        result_json = field.string{
            required = true,
            description = "The complete SME question gate result JSON string."
        },
    },
    function(args)
        return { result_json = args.result_json }
    end
}

gate_agent = Agent {
    provider = "{{PROVIDER}}",
    model = "{{MODEL}}",
    model_type = "chat",
    temperature = 0.0,
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
    tools = {finish},
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

You must call the finish tool exactly once.
The finish tool has a required argument named result_json.
Set result_json to a JSON object with:
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

        gate_agent({ message = gate_message })
        local text = tostring(finish.last_call() or "")

        if type(text) ~= "string" then
            text = tostring(text or "")
        end
        return { text = text }
    end
}
