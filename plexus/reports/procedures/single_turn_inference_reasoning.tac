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
        local function extract_text(value, depth)
            depth = depth or 0
            if value == nil or depth > 8 then
                return ""
            end

            local value_type = type(value)
            if value_type == "string" then
                return value
            end
            if value_type == "number" or value_type == "boolean" then
                return tostring(value)
            end
            if value_type == "table" then
                if type(value["overall_summary"]) == "string" then
                    local escaped_summary = value["overall_summary"]
                        :gsub("\\", "\\\\")
                        :gsub('"', '\\"')
                        :gsub("\n", "\\n")
                        :gsub("\r", "\\r")
                        :gsub("\t", "\\t")
                    return '{"overall_summary":"' .. escaped_summary .. '"}'
                end

                local preferred_keys = { "reason", "text", "output", "content", "message", "response", "result" }
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

            local object_keys = { "output", "text", "content", "response" }
            for _, key in ipairs(object_keys) do
                local ok, nested = pcall(function() return value[key] end)
                if ok and nested ~= nil then
                    local extracted = extract_text(nested, depth + 1)
                    if extracted ~= "" then
                        return extracted
                    end
                end
            end

            return ""
        end

        local result = responder()
        local text = extract_text(result)
        if text == "" and result ~= nil and type(result) ~= "table" then
            text = tostring(result)
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
