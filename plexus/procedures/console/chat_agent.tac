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
if type(input) == "table" then
  local provided_history = input.console_session_history
  if type(provided_history) == "table" and #provided_history > 0 then
    history = provided_history
  end
end

if #history == 0 and MessageHistory ~= nil and MessageHistory.get ~= nil then
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

local previous_user_prompt = nil
if #history > 0 then
  local found_latest = false
  for i = #history, 1, -1 do
    local msg = history[i]
    local role = string.upper(tostring((msg and msg.role) or ""))
    local content = (msg and msg.content) or nil
    if role == "USER" and type(content) == "string" and content ~= "" then
      if not found_latest then
        found_latest = true
        if not injected_user_prompt then
          latest_user_prompt = content
        end
      else
        previous_user_prompt = content
        break
      end
    end
  end
end

local history_context = ""
local history_start = 1
if #history > 24 then
  history_start = #history - 23
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

local function _trim(value)
  if type(value) ~= "string" then
    return ""
  end
  return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

local number_words = {
  zero = 0,
  one = 1,
  two = 2,
  three = 3,
  four = 4,
  five = 5,
  six = 6,
  seven = 7,
  eight = 8,
  nine = 9,
  ten = 10,
  eleven = 11,
  twelve = 12,
  thirteen = 13,
  fourteen = 14,
  fifteen = 15,
  sixteen = 16,
  seventeen = 17,
  eighteen = 18,
  nineteen = 19,
  twenty = 20,
}

local function parse_number_token(raw_token)
  if raw_token == nil then
    return nil
  end
  local token = string.lower(_trim(tostring(raw_token)))
  if token == "" then
    return nil
  end
  local numeric = tonumber(token)
  if numeric ~= nil then
    return numeric
  end
  token = token:gsub("[^%a%-]", "")
  return number_words[token]
end

local function format_number(value)
  if type(value) ~= "number" then
    return tostring(value)
  end
  if math.floor(value) == value then
    return tostring(math.floor(value))
  end
  return tostring(value)
end

local function find_last_numeric_reference()
  for i = #history, 1, -1 do
    local msg = history[i]
    local content = (msg and msg.content) or nil
    if type(content) == "string" and content ~= "" then
      local last_match = nil
      for numeric_token in string.gmatch(content, "[-+]?%d+%.?%d*") do
        local parsed = tonumber(numeric_token)
        if parsed ~= nil then
          last_match = parsed
        end
      end
      if last_match ~= nil then
        return last_match
      end
    end
  end
  return nil
end

local deterministic_response = nil
do
  local lower_latest = string.lower(latest_user_prompt or "")
  local multiplier_token = (
    string.match(lower_latest, "multiply%s+.-%s+by%s+([%w%.-]+)")
    or string.match(lower_latest, "times%s+([%w%.-]+)")
  )
  local multiplier = parse_number_token(multiplier_token)
  local explicit_left_token = string.match(lower_latest, "multiply%s+([%w%.-]+)%s+by%s+[%w%.-]+")
  local explicit_left = parse_number_token(explicit_left_token)
  local has_reference = (
    string.find(lower_latest, " that ", 1, true)
    or string.find(lower_latest, "that?", 1, true)
    or string.find(lower_latest, "that.", 1, true)
    or string.find(lower_latest, " it ", 1, true)
    or string.find(lower_latest, "it?", 1, true)
    or string.find(lower_latest, "it.", 1, true)
  ) ~= nil

  if multiplier ~= nil then
    if explicit_left ~= nil then
      local computed = explicit_left * multiplier
      deterministic_response = (
        format_number(explicit_left)
        .. " multiplied by "
        .. format_number(multiplier)
        .. " is "
        .. format_number(computed)
        .. "."
      )
    elseif has_reference then
      local base_number = find_last_numeric_reference()
      if base_number ~= nil then
        local computed = base_number * multiplier
        deterministic_response = (
          format_number(base_number)
          .. " multiplied by "
          .. format_number(multiplier)
          .. " is "
          .. format_number(computed)
          .. "."
        )
      end
    end
  end
end

State.set("stage", "responding")

local assistant_prompt = "You are the Plexus Console assistant in an ongoing chat.\n\n" ..
                         "Rules:\n" ..
                         "- Treat the latest user message as part of the same ongoing conversation.\n" ..
                         "- Use prior turns when the user refers to earlier context (pronouns, 'it', 'that', follow-ups).\n" ..
                         "- Do not ask the user to repeat something already present in context.\n" ..
                         "- Ask one concise clarifying question only when context is genuinely insufficient.\n" ..
                         "- Keep responses concise and practical.\n\n" ..
                         "Latest user message:\n" .. latest_user_prompt .. "\n\n" ..
                         "Previous user message before latest (if any):\n" .. (previous_user_prompt or "") .. "\n\n" ..
                         "Recent conversation context (oldest to newest):\n" .. history_context .. "\n\n" ..
                         "Respond to the latest user message now."

local assistant_result = nil
if deterministic_response ~= nil and deterministic_response ~= "" then
  assistant_result = { response = deterministic_response }
else
  assistant_result = assistant({ message = assistant_prompt })
end

local final_response = ""

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

final_response = extract_text(assistant_result)

if final_response == "" and type(assistant_result) == "table" then
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
  final_response = "I can help with that. Could you clarify what you want me to do next?"
end

State.set("stage", "complete")

return {
  success = final_response ~= "",
  response = final_response,
  prompt_used = latest_user_prompt,
  iterations = Iterations.current()
}
