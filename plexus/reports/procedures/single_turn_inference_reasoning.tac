-- Single-turn LLM inference for reasoning models (gpt-5, o3 series).
-- These models use the Responses API and do not need tool-call signaling.
-- {{PROVIDER}} and {{MODEL}} are substituted by Python before execution.

responder = Agent {
    provider = "{{PROVIDER}}",
    model = "{{MODEL}}",
    model_type = "responses",
    temperature = 1.0,
    max_tokens = 16000,
    system_prompt = "{system_prompt}",
    initial_message = "{user_message}",
}

Procedure {
    input = {
        user_message = field.string{required = true},
        system_prompt = field.string{default = ""},
    },
    function(input)
        local result = responder()
        local text = ""
        if type(result) == "table" then
            text = result.output or result.response or ""
        elseif result ~= nil then
            -- Python object (lupa userdata) — try .output attribute access
            local ok, output = pcall(function() return result.output end)
            if ok and output ~= nil then
                text = tostring(output)
            else
                text = tostring(result)
            end
        end
        return { text = text }
    end
}
