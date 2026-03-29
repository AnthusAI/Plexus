-- Single-turn LLM inference for FeedbackAnalysis memory analysis.
-- {{PROVIDER}} and {{MODEL}} are substituted by Python before execution.

local done = require("tactus.tools.done")

responder = Agent {
    provider = "{{PROVIDER}}",
    model = "{{MODEL}}",
    system_prompt = "{system_prompt}",
    initial_message = "{user_message}\n\nIMPORTANT: Call the done tool with your answer as the 'reason' parameter.",
    tools = {done},
}

Procedure {
    input = {
        user_message = field.string{required = true},
        system_prompt = field.string{default = ""},
    },
    output = {
        text = field.string{required = true},
    },
    function(input)
        local max_turns = 3
        local turn_count = 0
        while not done.called() and turn_count < max_turns do
            responder()
            turn_count = turn_count + 1
        end
        return { text = done.last_result() or "" }
    end
}
