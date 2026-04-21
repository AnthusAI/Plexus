-- Single-turn LLM inference for FeedbackAlignment memory analysis.
-- {{PROVIDER}} and {{MODEL}} are substituted by Python before execution.

local done = require("tactus.tools.done")

responder = Agent {
    provider = "{{PROVIDER}}",
    model = "{{MODEL}}",
    model_type = "chat",
    temperature = 0.0,
    max_tokens = 1024,
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
            responder()
            turn_count = turn_count + 1
        end

        -- done.last_result() can be either:
        -- 1) a plain string
        -- 2) a table like { status = "...", reason = "..." }
        -- 3) provider-specific userdata/table variants.
        -- Always extract a deterministic string so Python never receives
        -- tostring(table) values like "<Lua table at 0x...>".
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
