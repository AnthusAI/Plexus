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

-- History comes from caller via console_session_history, then filtered by MessageHistory
local history = {}
if type(input) == "table" then
  local provided_history = input.console_session_history
  if type(provided_history) == "table" and #provided_history > 0 then
    history = provided_history
  end
end

local tool_access_mode = "execution"
if type(input) == "table" then
  local provided_mode = input.console_tool_access_mode or input.tool_access_mode
  if type(provided_mode) == "string" and provided_mode ~= "" then
    tool_access_mode = provided_mode
  end
end

-- Extract latest and previous user prompts for reference
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

-- Apply token-budgeted history management using MessageHistory primitives
-- Target: 100K tokens for history (models have 128K+ windows; leave room for system prompt + response)
local MAX_HISTORY_TOKENS = 100000
MessageHistory.replace(history)
local filtered_history = MessageHistory.tail_tokens(MAX_HISTORY_TOKENS)

-- Format filtered history for prompt context (preserving role structure)
local history_context = ""
for i = 1, #filtered_history do
  local msg = filtered_history[i]
  local role = string.upper(tostring((msg and msg.role) or "UNKNOWN"))
  local content = tostring((msg and msg.content) or "")
  if content ~= "" then
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

local function normalized_choice_text(value)
  local text = string.lower(_trim(tostring(value or "")))
  text = text:gsub("^use%s+", "")
  text = text:gsub("^choose%s+", "")
  text = text:gsub("^select%s+", "")
  text = text:gsub("^the%s+", "")
  text = text:gsub("%s+score$", "")
  text = text:gsub("[%.,;:!?]+$", "")
  text = _trim(text)
  return text
end

local function find_pending_score_disambiguation()
  for i = #history, 1, -1 do
    local msg = history[i]
    local role = string.upper(tostring((msg and msg.role) or ""))
    local content = (msg and msg.content) or nil
    if role == "ASSISTANT"
      and type(content) == "string"
      and string.find(content, "matching scores", 1, true)
      and string.find(content, "Which one", 1, true) then
      local scorecard = string.match(content, "on%s+%*%*(.-)%*%*")
      local candidates = {}
      for candidate in string.gmatch(content, "%-%s+%*%*(.-)%*%*") do
        table.insert(candidates, _trim(candidate))
      end
      if #candidates > 0 then
        local pending_user_request = nil
        for j = i - 1, 1, -1 do
          local prior = history[j]
          local prior_role = string.upper(tostring((prior and prior.role) or ""))
          local prior_content = (prior and prior.content) or nil
          if prior_role == "USER" and type(prior_content) == "string" and prior_content ~= "" then
            pending_user_request = prior_content
            break
          end
        end
        return {
          scorecard = scorecard,
          candidates = candidates,
          pending_user_request = pending_user_request,
        }
      end
    end
  end
  return nil
end

local function resolve_pending_score_choice(pending, latest)
  if pending == nil or type(pending.candidates) ~= "table" then
    return nil, nil
  end

  local lower_latest = string.lower(latest or "")
  local ordinal = nil
  if string.find(lower_latest, "first", 1, true) or string.find(lower_latest, "1st", 1, true) then
    ordinal = 1
  elseif string.find(lower_latest, "second", 1, true) or string.find(lower_latest, "2nd", 1, true) then
    ordinal = 2
  elseif string.find(lower_latest, "third", 1, true) or string.find(lower_latest, "3rd", 1, true) then
    ordinal = 3
  end
  if ordinal ~= nil and pending.candidates[ordinal] ~= nil then
    return pending.candidates[ordinal], nil
  end

  local normalized_latest = normalized_choice_text(latest)
  local exact_matches = {}
  for _, candidate in ipairs(pending.candidates) do
    if normalized_choice_text(candidate) == normalized_latest then
      table.insert(exact_matches, candidate)
    end
  end
  if #exact_matches == 1 then
    return exact_matches[1], nil
  elseif #exact_matches > 1 then
    return nil, "I still need one exact score name from the list before I can apply the change."
  end

  if string.find(lower_latest, "without confidence", 1, true) then
    local matches = {}
    for _, candidate in ipairs(pending.candidates) do
      if not string.find(string.lower(candidate), "confidence", 1, true) then
        table.insert(matches, candidate)
      end
    end
    if #matches == 1 then
      return matches[1], nil
    end
  elseif string.find(lower_latest, "with confidence", 1, true) then
    local matches = {}
    for _, candidate in ipairs(pending.candidates) do
      if string.find(string.lower(candidate), "confidence", 1, true) then
        table.insert(matches, candidate)
      end
    end
    if #matches == 1 then
      return matches[1], nil
    end
  end

  return nil, nil
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

local disambiguation_context = ""
do
  local pending = find_pending_score_disambiguation()
  local selected_score, selection_error = resolve_pending_score_choice(pending, latest_user_prompt)
  if selection_error ~= nil then
    deterministic_response = deterministic_response or selection_error
  elseif selected_score ~= nil and pending ~= nil then
    disambiguation_context =
      "Resolved follow-up target selection:\n" ..
      "- The latest user message is a response to your prior score disambiguation question.\n" ..
      "- Continue the pending user request; do not ask the same disambiguation question again.\n" ..
      "- Use scorecard_identifier exactly: " .. tostring(pending.scorecard or "") .. "\n" ..
      "- Use score_identifier exactly: " .. tostring(selected_score) .. "\n" ..
      "- Pending user request to complete:\n" .. tostring(pending.pending_user_request or "") .. "\n\n"
  end
end

State.set("stage", "responding")

local assistant_prompt = "You are the Plexus Console assistant in an ongoing engineering chat.\n" ..
                         "Use prior turns for continuity and respond concisely with concrete help.\n" ..
                         "Ask one short clarifying question only if context is insufficient.\n\n" ..
                         "Current tool access mode: " .. tool_access_mode .. "\n" ..
                         "In planning mode, inspect existing data and procedure runs, run safe analysis, and propose exact next actions. " ..
                         "Planning blocks significant mutations: score version changes, champion promotion, and starting/continuing/branching/optimizing procedures.\n\n" ..
                         "Latest user message:\n" .. latest_user_prompt .. "\n\n" ..
                         "Previous user message before latest (if any):\n" .. (previous_user_prompt or "") .. "\n\n" ..
                         "Recent conversation context (oldest to newest):\n" .. history_context .. "\n\n" ..
                         disambiguation_context ..
                         "Respond to the latest user message now."

local function extract_text(value)
  if type(value) == "string" and value ~= "" then
    return value
  end
  -- Handle both Lua tables AND Lupa-wrapped Python objects (type == "userdata")
  if type(value) == "table" or type(value) == "userdata" then
    for _, key in ipairs({"response", "content", "message", "text"}) do
      local ok, attr = pcall(function() return value[key] end)
      if ok and type(attr) == "string" and attr ~= "" then
        return attr
      end
    end
    -- Indexed first element
    local ok_first, first = pcall(function() return value[1] end)
    if ok_first and type(first) == "string" and first ~= "" then
      return first
    end
    if ok_first and (type(first) == "table" or type(first) == "userdata") then
      for _, key in ipairs({"text", "content"}) do
        local ok2, attr2 = pcall(function() return first[key] end)
        if ok2 and type(attr2) == "string" and attr2 ~= "" then
          return attr2
        end
      end
    end
  end
  return ""
end

local function looks_like_uuid(value)
  if type(value) ~= "string" then
    return false
  end
  local trimmed = _trim(value)
  if trimmed == "" then
    return false
  end
  return string.match(trimmed, "^[0-9a-fA-F]{8}%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x$") ~= nil
end

local function contains_score_link(value)
  if type(value) ~= "string" then
    return false
  end
  local lowered = string.lower(value)
  return string.find(lowered, "/scorecards/", 1, true) ~= nil
    and string.find(lowered, "/scores/", 1, true) ~= nil
end

local function extract_score_target_key(value)
  if type(value) ~= "string" then
    return nil
  end

  local lowered = string.lower(value)
  local scorecard_id, score_id = string.match(lowered, "/scorecards/([0-9a-f%-]+)/scores/([0-9a-f%-]+)")
  if scorecard_id ~= nil and score_id ~= nil and looks_like_uuid(scorecard_id) and looks_like_uuid(score_id) then
    return string.lower(scorecard_id) .. "|" .. string.lower(score_id)
  end

  local uuids = {}
  for token in string.gmatch(value, "[0-9a-fA-F%-]+") do
    if looks_like_uuid(token) then
      table.insert(uuids, string.lower(_trim(token)))
    end
  end

  if #uuids >= 2 then
    return uuids[1] .. "|" .. uuids[2]
  end

  return nil
end

local function has_explicit_score_target(value)
  return extract_score_target_key(value) ~= nil
end

local function collect_active_score_targets()
  local seen = {}
  local ordered = {}

  local function remember(value)
    local key = extract_score_target_key(value)
    if key ~= nil and seen[key] == nil then
      seen[key] = true
      table.insert(ordered, key)
    end
  end

  remember(latest_user_prompt)
  for i = #history, 1, -1 do
    local msg = history[i]
    local content = (msg and msg.content) or nil
    remember(content)
  end

  return ordered
end

if deterministic_response == nil then
  local lower_latest = string.lower(latest_user_prompt or "")
  local has_deictic_score_ref = (
    string.find(lower_latest, "this score", 1, true)
    or string.find(lower_latest, "that score", 1, true)
    or string.find(lower_latest, "this scorecard", 1, true)
    or string.find(lower_latest, "that scorecard", 1, true)
    or string.find(lower_latest, "same score", 1, true)
  ) ~= nil
  local explicit_target_key = extract_score_target_key(latest_user_prompt)
  local active_targets = collect_active_score_targets()
  local active_target_count = #active_targets

  if has_deictic_score_ref and explicit_target_key == nil then
    if active_target_count == 0 then
      deterministic_response = "I can do that, but I need the exact target first. Please share the scorecard and score (name or link), and I’ll apply the change."
    elseif active_target_count > 1 then
      deterministic_response = "I can do that, but this chat has more than one possible score target. Please share the exact scorecard and score (name or link), and I’ll apply the change."
    end
  end
end

local assistant_result = nil
if deterministic_response ~= nil and deterministic_response ~= "" then
  assistant_result = { response = deterministic_response }
else
  assistant_result = assistant({ message = assistant_prompt })
end

local final_response = ""

final_response = extract_text(assistant_result)

-- Fallback: read TactusResult.output (may be string or structured table/userdata)
if final_response == "" then
  local ok_res, res_output = pcall(function() return assistant_result.output end)
  if ok_res and res_output ~= nil then
    final_response = extract_text(res_output)
  end
end

-- Fallback: assistant.output set by Tactus after the call — filter out Python repr garbage
if final_response == "" then
  local ok_out, out_val = pcall(function() return assistant.output end)
  if ok_out and type(out_val) == "string" and out_val ~= ""
    and not string.find(out_val, "UsageStats", 1, true)
    and not string.find(out_val, "output=None", 1, true) then
    final_response = out_val
  end
end

if final_response == "" then
  for _, key in ipairs({ "response", "content", "message", "text", "output" }) do
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

if looks_like_uuid(final_response) then
  final_response = "Completed, but the assistant returned only a version identifier (" .. final_response .. "). I will include a clear human-readable summary next time."
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
