State.set("stage", "preparing")

local fallback_prompt = "Hello. How can I help you today?"
local latest_user_prompt = fallback_prompt
local injected_user_prompt = nil
if type(input) == "table" then
  local candidate = input.console_user_message or input.user_message or input.prompt
  if type(candidate) == "string" and candidate ~= "" then
    injected_user_prompt = candidate
    latest_user_prompt = candidate
  end
end

local history = {}
if MessageHistory ~= nil and MessageHistory.get ~= nil then
  local history_raw = MessageHistory.get()
  if type(history_raw) == "table" then
    history = history_raw
  else
    local ok_encoded, encoded = pcall(function()
      return Json.encode(history_raw)
    end)
    if ok_encoded and type(encoded) == "string" then
      local ok_decoded, decoded = pcall(function()
        return Json.decode(encoded)
      end)
      if ok_decoded and type(decoded) == "table" then
        history = decoded
      end
    end
  end
end

if (not injected_user_prompt) and #history > 0 then
  for i = #history, 1, -1 do
    local msg = history[i]
    local role = string.upper(tostring((msg and msg.role) or ""))
    local content = (msg and msg.content) or nil
    if role == "USER" and type(content) == "string" and content ~= "" then
      latest_user_prompt = content
      break
    end
  end
end

local history_context = ""
local history_start = 1
if #history > 8 then
  history_start = #history - 7
end
for i = history_start, #history do
  local msg = history[i]
  local role = string.upper(tostring((msg and msg.role) or "UNKNOWN"))
  local content = (msg and msg.content) or ""
  if type(content) == "string" and content ~= "" then
    if #content > 800 then
      content = string.sub(content, 1, 800) .. "..."
    end
    history_context = history_context .. role .. ": " .. content .. "\n"
  end
end

State.set("stage", "responding")

local assistant_prompt = "Respond to the user.\n\n" ..
                         "Latest user message:\n" .. latest_user_prompt .. "\n\n" ..
                         "Recent conversation context:\n" .. history_context .. "\n\n" ..
                         "Give a concise, practical response."

local assistant_result = assistant({ message = assistant_prompt })

local final_response = ""

local normalized_assistant_result = assistant_result

if final_response == "" then
  if type(normalized_assistant_result) == "string" and normalized_assistant_result ~= "" then
    final_response = normalized_assistant_result
  elseif type(normalized_assistant_result) == "table" then
    if type(normalized_assistant_result.response) == "string" and normalized_assistant_result.response ~= "" then
      final_response = normalized_assistant_result.response
    elseif type(normalized_assistant_result.content) == "string" and normalized_assistant_result.content ~= "" then
      final_response = normalized_assistant_result.content
    elseif type(normalized_assistant_result.content) == "table" then
      local first_part = normalized_assistant_result.content[1]
      if type(first_part) == "string" and first_part ~= "" then
        final_response = first_part
      elseif type(first_part) == "table" then
        if type(first_part.text) == "string" and first_part.text ~= "" then
          final_response = first_part.text
        elseif type(first_part.content) == "string" and first_part.content ~= "" then
          final_response = first_part.content
        end
      end
    elseif type(normalized_assistant_result.message) == "string" and normalized_assistant_result.message ~= "" then
      final_response = normalized_assistant_result.message
    end
  end
end

if final_response == "" then
  local function extract_text(value)
    if type(value) == "string" and value ~= "" then
      return value
    end
    if type(value) == "table" then
      if type(value.response) == "string" and value.response ~= "" then
        return value.response
      end
      if type(value.content) == "string" and value.content ~= "" then
        return value.content
      end
      if type(value.message) == "string" and value.message ~= "" then
        return value.message
      end
      if type(value.text) == "string" and value.text ~= "" then
        return value.text
      end
      local part = value[1]
      if type(part) == "string" and part ~= "" then
        return part
      end
      if type(part) == "table" then
        if type(part.text) == "string" and part.text ~= "" then
          return part.text
        end
        if type(part.content) == "string" and part.content ~= "" then
          return part.content
        end
      end
    end
    return ""
  end

  local attr_keys = { "response", "content", "message", "text", "output", "result" }
  for _, key in ipairs(attr_keys) do
    local ok_attr, attr_value = pcall(function()
      return assistant_result[key]
    end)
    if ok_attr then
      local attr_text = extract_text(attr_value)
      if attr_text ~= "" then
        final_response = attr_text
        break
      end
    end
  end
end
if final_response == "" then
  final_response = "I received your message: \"" .. latest_user_prompt .. "\". Ask me to inspect scorecards, evaluations, procedures, or reports and I can help."
end

State.set("stage", "complete")

return {
  success = final_response ~= "",
  response = final_response,
  prompt_used = latest_user_prompt,
  iterations = Iterations.current()
}
