"""
Chat Recording for Procedure Runs.

This module provides functionality to record AI conversations during procedure runs,
including tool calls and responses, for later analysis and display in the UI.
"""

import logging
import os
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.client import LONG_RUNNING_WRITE_RETRY_POLICY_NAME

logger = logging.getLogger(__name__)


def truncate_for_log(content: str, max_length: int = 200) -> str:
    """Truncate content for logging purposes."""
    if not content:
        return content
    if len(content) <= max_length:
        return content
    return content[:max_length] + f"... [truncated, total: {len(content)} chars]"


_SLIM_MAX_STR = 200    # enough for UUIDs (36 chars), URLs, short labels
_SLIM_MAX_BYTES = 512  # keep small dicts/lists; drop large analysis blobs


def _slim_tool_response_for_storage(value: Any) -> Any:
    """Return a compact representation of a tool response for storage.

    Parses JSON strings, keeps scalar values <= _SLIM_MAX_STR chars, and keeps
    nested structures only when their serialised size is <= _SLIM_MAX_BYTES.
    Large blobs (confusionMatrix, misclassification_analysis, etc.) are dropped --
    they already live in the referenced Evaluation record.
    """
    if isinstance(value, str):
        try:
            return _slim_tool_response_for_storage(json.loads(value))
        except (json.JSONDecodeError, ValueError):
            return value[:_SLIM_MAX_STR] if len(value) > _SLIM_MAX_STR else value
    if isinstance(value, dict):
        slimmed = {}
        for k, v in value.items():
            sv = _slim_tool_response_for_storage(v)
            if isinstance(sv, (dict, list)) and len(json.dumps(sv).encode()) > _SLIM_MAX_BYTES:
                continue  # drop large nested structure
            slimmed[k] = sv
        return slimmed
    if isinstance(value, list):
        return [_slim_tool_response_for_storage(item) for item in value]
    return value  # int, float, bool, None


class ProcedureChatRecorder:
    """Records chat messages during procedure runs."""

    def __init__(self, client: PlexusDashboardClient, procedure_id: str, node_id: Optional[str] = None):
        self.client = client
        self.procedure_id = procedure_id
        self.node_id = node_id
        self.session_id = None
        self.account_id = None
        self.sequence_number = 0
        self._sequence_lock = None  # Will be initialized when needed
        self._state_data: Optional[Dict[str, Any]] = None  # Conversation state machine data

    @staticmethod
    def _graphql_field(result: Any, field_name: str) -> Any:
        """Extract a field from wrapped or unwrapped GraphQL responses."""
        if not isinstance(result, dict):
            return None
        data = result.get('data')
        if isinstance(data, dict) and field_name in data:
            return data.get(field_name)
        return result.get(field_name)

    def _get_resume_session_id(self) -> Optional[str]:
        """Return existing session id when procedure is waiting for human input."""
        try:
            query = """
            query GetProcedureWaitingMessage($id: ID!) {
                getProcedure(id: $id) {
                    status
                    waitingOnMessageId
                }
            }
            """
            result = self.client.execute(query, {'id': self.procedure_id})
            procedure = self._graphql_field(result, 'getProcedure')
            if not isinstance(procedure, dict):
                return None

            if procedure.get('status') != 'WAITING_FOR_HUMAN':
                return None

            waiting_message_id = procedure.get('waitingOnMessageId')
            if not waiting_message_id:
                return None

            message_query = """
            query GetWaitingMessageSession($id: ID!) {
                getChatMessage(id: $id) {
                    id
                    sessionId
                }
            }
            """
            message_result = self.client.execute(message_query, {'id': waiting_message_id})
            message = self._graphql_field(message_result, 'getChatMessage')
            if not isinstance(message, dict):
                return None

            session_id = message.get('sessionId')
            return str(session_id) if session_id else None
        except Exception as e:
            logger.debug(f"Could not resolve resume session for procedure {self.procedure_id}: {e}")
            return None

    def _get_latest_console_chat_metadata(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Return the most recent console_chat metadata for this procedure, if present."""
        try:
            dispatch_task_id = (os.getenv('PLEXUS_DISPATCH_TASK_ID') or '').strip()
            if dispatch_task_id:
                query = """
                query GetTaskForConsoleChat($id: ID!) {
                    getTask(id: $id) {
                        id
                        accountId
                        target
                        metadata
                    }
                }
                """
                result = self.client.execute(query, {'id': dispatch_task_id})
                task = self._graphql_field(result, 'getTask')
                if isinstance(task, dict):
                    task_target = str(task.get('target') or '')
                    if task_target in {
                        f'procedure/{self.procedure_id}',
                        f'procedure/run/{self.procedure_id}',
                    }:
                        metadata = task.get('metadata')
                        if isinstance(metadata, str):
                            try:
                                metadata = json.loads(metadata)
                            except Exception:
                                metadata = None
                        if isinstance(metadata, dict):
                            console_chat = metadata.get('console_chat')
                            if isinstance(console_chat, dict):
                                task_account_id = str(task.get('accountId') or '')
                                if task_account_id and str(account_id) and task_account_id != str(account_id):
                                    logger.info(
                                        "Using dispatch task console_chat metadata despite account mismatch "
                                        "(task=%s context=%s) for procedure %s",
                                        task_account_id,
                                        account_id,
                                        self.procedure_id,
                                    )
                                return console_chat

            query = """
            query ListTaskByAccountIdAndUpdatedAt($accountId: String!, $updatedAt: ModelStringKeyConditionInput, $limit: Int, $nextToken: String) {
                listTaskByAccountIdAndUpdatedAt(
                    accountId: $accountId
                    updatedAt: $updatedAt
                    limit: $limit
                    nextToken: $nextToken
                ) {
                    items {
                        id
                        target
                        status
                        metadata
                        updatedAt
                    }
                    nextToken
                }
            }
            """

            items: List[dict] = []
            next_token: Optional[str] = None
            while True:
                result = self.client.execute(
                    query,
                    {
                        'accountId': account_id,
                        'updatedAt': {'ge': '2000-01-01T00:00:00.000Z'},
                        'limit': 200,
                        'nextToken': next_token,
                    }
                )
                task_page = self._graphql_field(result, 'listTaskByAccountIdAndUpdatedAt')
                if not isinstance(task_page, dict):
                    break

                page_items = task_page.get('items', [])
                if isinstance(page_items, list):
                    items.extend(item for item in page_items if isinstance(item, dict))

                next_token = task_page.get('nextToken')
                if not next_token:
                    break

            sorted_items = sorted(
                items,
                key=lambda item: str(item.get('updatedAt') or ''),
                reverse=True,
            )

            for item in sorted_items:
                if not isinstance(item, dict):
                    continue
                target = str(item.get('target') or '')
                if target not in {f'procedure/{self.procedure_id}', f'procedure/run/{self.procedure_id}'}:
                    continue

                metadata = item.get('metadata')
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:
                        metadata = None
                if not isinstance(metadata, dict):
                    return None

                console_chat = metadata.get('console_chat')
                if not isinstance(console_chat, dict):
                    return None

                return console_chat

            return None
        except Exception as e:
            logger.debug(f"Could not resolve console session from task metadata for procedure {self.procedure_id}: {e}")
            return None

    def _get_console_session_id_from_task_metadata(self, account_id: str) -> Optional[str]:
        """Return session id from most recent procedure task metadata when present."""
        console_chat = self._get_latest_console_chat_metadata(account_id)
        if not isinstance(console_chat, dict):
            return None

        session_id = console_chat.get('session_id')
        if isinstance(session_id, str) and session_id.strip():
            return session_id.strip()
        return None

    @staticmethod
    def _normalize_console_history_snapshot(
        raw_snapshot: Any,
        *,
        limit: int = 40,
        max_content_chars: int = 800,
    ) -> List[Dict[str, str]]:
        """Normalize client-provided history snapshots into USER/ASSISTANT message turns."""
        if not isinstance(raw_snapshot, list):
            return []

        normalized: List[Dict[str, str]] = []
        for entry in raw_snapshot:
            if not isinstance(entry, dict):
                continue

            role = str(entry.get("role") or "").upper()
            if role not in {"USER", "ASSISTANT"}:
                continue

            content = entry.get("content")
            if not isinstance(content, str):
                continue
            content = content.strip()
            if not content:
                continue

            if role == "ASSISTANT" and content == "Assistant turn completed.":
                continue

            if max_content_chars > 0 and len(content) > max_content_chars:
                content = content[:max_content_chars] + "..."

            normalized.append({"role": role, "content": content})

        if limit > 0 and len(normalized) > limit:
            return normalized[-limit:]
        return normalized

    @staticmethod
    def _history_has_trailing_user_prompt(
        history: List[Dict[str, str]],
        latest_trigger_message: Optional[str],
    ) -> bool:
        if not latest_trigger_message:
            return True
        if not history:
            return False
        last = history[-1]
        return (
            isinstance(last, dict)
            and last.get("role") == "USER"
            and str(last.get("content") or "").strip() == latest_trigger_message
        )

    @staticmethod
    def _history_quality(history: List[Dict[str, str]]) -> tuple[int, int]:
        assistant_count = 0
        numeric_token_count = 0
        total_chars = 0

        for item in history:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = str(item.get("content") or "")
            if role == "ASSISTANT":
                assistant_count += 1
            numeric_token_count += len(re.findall(r"[-+]?\d+\.?\d*", content))
            total_chars += len(content)

        return assistant_count, numeric_token_count, total_chars, len(history)

    @staticmethod
    def _merge_aligned_histories(
        snapshot_history: List[Dict[str, str]],
        db_history: List[Dict[str, str]],
    ) -> Optional[List[Dict[str, str]]]:
        if len(snapshot_history) != len(db_history):
            return None
        if not snapshot_history:
            return []

        merged: List[Dict[str, str]] = []
        for snapshot_entry, db_entry in zip(snapshot_history, db_history):
            if not isinstance(snapshot_entry, dict) or not isinstance(db_entry, dict):
                return None
            snapshot_role = str(snapshot_entry.get("role") or "").upper()
            db_role = str(db_entry.get("role") or "").upper()
            if snapshot_role != db_role:
                return None

            snapshot_content = str(snapshot_entry.get("content") or "").strip()
            db_content = str(db_entry.get("content") or "").strip()

            chosen_content = snapshot_content
            if db_content and (
                len(db_content) > len(snapshot_content)
                or snapshot_content.startswith(db_content)
                or db_content.startswith(snapshot_content)
            ):
                chosen_content = db_content
            elif not snapshot_content:
                chosen_content = db_content

            merged.append({
                "role": snapshot_role,
                "content": chosen_content,
            })

        return merged

    def get_latest_console_chat_metadata(self, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Public accessor for the latest console_chat task metadata."""
        try:
            resolved_account_id = account_id or self.account_id or self._resolve_account_id_for_session({})
            if not resolved_account_id:
                return None
            metadata = self._get_latest_console_chat_metadata(str(resolved_account_id))
            return metadata if isinstance(metadata, dict) else None
        except Exception as e:
            logger.debug(
                "Could not fetch latest console chat metadata for procedure %s: %s",
                self.procedure_id,
                e,
            )
            return None

    def get_latest_console_trigger_message(self, account_id: Optional[str] = None) -> Optional[str]:
        """Return latest console trigger message content from task metadata, if present."""
        try:
            resolved_account_id = account_id or self.account_id or self._resolve_account_id_for_session({})
            if not resolved_account_id:
                return None

            console_chat = self._get_latest_console_chat_metadata(resolved_account_id)
            if not isinstance(console_chat, dict):
                return None

            direct_message_text = console_chat.get('trigger_message_content')
            if isinstance(direct_message_text, str) and direct_message_text.strip():
                return direct_message_text.strip()

            instrumentation = console_chat.get('instrumentation')
            if isinstance(instrumentation, dict):
                for key in ('client_user_message_text', 'trigger_message_content', 'message_text'):
                    candidate = instrumentation.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()

            trigger_message_id = console_chat.get('trigger_message_id')
            if not isinstance(trigger_message_id, str) or not trigger_message_id.strip():
                return None

            query = """
            query GetChatMessageContent($id: ID!) {
                getChatMessage(id: $id) {
                    id
                    role
                    content
                }
            }
            """
            result = self.client.execute(query, {'id': trigger_message_id.strip()})
            message = self._graphql_field(result, 'getChatMessage')
            if not isinstance(message, dict):
                return None

            content = message.get('content')
            if isinstance(content, str) and content.strip():
                return content.strip()
            return None
        except Exception as e:
            logger.debug(
                "Could not resolve latest console trigger message for procedure %s: %s",
                self.procedure_id,
                e,
            )
            return None

    def _list_session_messages(
        self,
        session_id: str,
        *,
        page_limit: int = 200,
        max_messages: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Fetch chat messages for a session in ascending created order."""
        if not session_id:
            return []

        query = """
        query ListChatMessagesBySession($sessionId: String!, $limit: Int, $nextToken: String) {
            listChatMessageBySessionIdAndCreatedAt(
                sessionId: $sessionId
                sortDirection: ASC
                limit: $limit
                nextToken: $nextToken
            ) {
                items {
                    id
                    role
                    content
                    messageType
                    humanInteraction
                    sequenceNumber
                    createdAt
                }
                nextToken
            }
        }
        """

        items: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        while True:
            result = self.client.execute(
                query,
                {
                    'sessionId': session_id,
                    'limit': page_limit,
                    'nextToken': next_token,
                },
            )
            payload = self._graphql_field(result, 'listChatMessageBySessionIdAndCreatedAt')
            if not isinstance(payload, dict):
                break

            page_items = payload.get('items', [])
            if isinstance(page_items, list):
                for item in page_items:
                    if isinstance(item, dict):
                        items.append(item)
                        if len(items) >= max_messages:
                            return items

            next_token = payload.get('nextToken')
            if not next_token:
                break

        return items

    def get_console_session_history(
        self,
        account_id: Optional[str] = None,
        limit: int = 40,
    ) -> List[Dict[str, str]]:
        """
        Return normalized USER/ASSISTANT chat history for the active console session.

        This is used to seed runtime context across detached procedure runs so
        follow-up turns preserve conversational references.
        """
        try:
            resolved_account_id = account_id or self.account_id or self._resolve_account_id_for_session({})
            if not resolved_account_id:
                return []

            session_id: Optional[str] = None
            snapshot_history: List[Dict[str, str]] = []
            console_chat = self._get_latest_console_chat_metadata(str(resolved_account_id))
            if isinstance(console_chat, dict):
                raw_session_id = console_chat.get('session_id')
                if isinstance(raw_session_id, str) and raw_session_id.strip():
                    session_id = raw_session_id.strip()
                instrumentation = console_chat.get("instrumentation")
                if isinstance(instrumentation, dict):
                    snapshot_history = self._normalize_console_history_snapshot(
                        instrumentation.get("client_history_snapshot"),
                        limit=limit,
                    )

            if not session_id and isinstance(self.session_id, str) and self.session_id.strip():
                session_id = self.session_id.strip()

            if not session_id:
                return snapshot_history

            raw_messages = self._list_session_messages(session_id)
            normalized: List[Dict[str, str]] = []
            for message in raw_messages:
                role = str(message.get('role') or '').upper()
                if role not in {'USER', 'ASSISTANT'}:
                    continue

                message_type = str(message.get('messageType') or 'MESSAGE').upper()
                if message_type != 'MESSAGE':
                    continue

                human_interaction = str(message.get('humanInteraction') or '').upper()
                # Internal assistant logs (e.g. setup/placeholder trace chatter)
                # should not be fed back into user-facing console continuity.
                if role == 'ASSISTANT' and human_interaction == 'INTERNAL':
                    continue

                content = message.get('content')
                if not isinstance(content, str):
                    continue
                content = content.strip()
                if not content:
                    continue

                # Avoid polluting context with synthetic fallback-only assistant text.
                if role == 'ASSISTANT' and content == 'Assistant turn completed.':
                    continue

                normalized.append({'role': role, 'content': content})

            latest_trigger_message = self.get_latest_console_trigger_message(str(resolved_account_id))
            if isinstance(latest_trigger_message, str) and latest_trigger_message.strip():
                latest_trigger_message = latest_trigger_message.strip()
                last_user_content: Optional[str] = None
                for entry in reversed(normalized):
                    if entry.get('role') == 'USER':
                        last_user_content = entry.get('content')
                        break
                if last_user_content != latest_trigger_message:
                    normalized.append({'role': 'USER', 'content': latest_trigger_message})

            if limit > 0 and len(normalized) > limit:
                normalized = normalized[-limit:]

            if snapshot_history:
                # Start from client snapshot when present; attempt aligned merge,
                # then prefer persisted DB history when both are available.
                effective_snapshot = list(snapshot_history)
                if isinstance(latest_trigger_message, str) and latest_trigger_message.strip():
                    latest_trigger_message = latest_trigger_message.strip()
                    last_snapshot_user: Optional[str] = None
                    for entry in reversed(effective_snapshot):
                        if entry.get('role') == 'USER':
                            last_snapshot_user = entry.get('content')
                            break
                    if last_snapshot_user != latest_trigger_message:
                        effective_snapshot.append({'role': 'USER', 'content': latest_trigger_message})

                if limit > 0 and len(effective_snapshot) > limit:
                    effective_snapshot = effective_snapshot[-limit:]

                merged_history = self._merge_aligned_histories(effective_snapshot, normalized)
                if merged_history is not None:
                    logger.info(
                        "Resolved console history for session %s (snapshot=%s, db=%s, source=merged)",
                        session_id,
                        len(effective_snapshot),
                        len(normalized),
                    )
                    return merged_history

                snapshot_has_trigger = self._history_has_trailing_user_prompt(
                    effective_snapshot,
                    latest_trigger_message if isinstance(latest_trigger_message, str) else None,
                )
                db_has_trigger = self._history_has_trailing_user_prompt(
                    normalized,
                    latest_trigger_message if isinstance(latest_trigger_message, str) else None,
                )

                snapshot_assistant_count = sum(
                    1 for item in effective_snapshot
                    if isinstance(item, dict) and item.get("role") == "ASSISTANT"
                )
                db_assistant_count = sum(
                    1 for item in normalized
                    if isinstance(item, dict) and item.get("role") == "ASSISTANT"
                )

                # Prefer persisted history, but allow snapshot backfill when DB
                # is clearly stale (missing assistant context or trigger tail).
                use_snapshot = False
                if not normalized:
                    use_snapshot = True
                elif snapshot_has_trigger and not db_has_trigger:
                    use_snapshot = True
                elif (
                    snapshot_assistant_count > db_assistant_count
                    and len(effective_snapshot) > len(normalized)
                ):
                    use_snapshot = True

                logger.info(
                    "Resolved console history for session %s (snapshot=%s, db=%s, source=%s)",
                    session_id,
                    len(effective_snapshot),
                    len(normalized),
                    "snapshot" if use_snapshot else "db",
                )
                return effective_snapshot if use_snapshot else normalized

            return normalized
        except Exception as e:
            logger.debug(
                "Could not resolve console session history for procedure %s: %s",
                self.procedure_id,
                e,
            )
            return []

    def _get_latest_sequence_number_for_session(self, session_id: str) -> int:
        """Load the latest persisted message sequence for a session.

        USER messages created by the frontend often do not carry a sequence number.
        Query a small descending window and pick the first numeric sequence so
        assistant/tool writes continue incrementing instead of restarting at 1.
        """
        try:
            query = """
            query GetLatestSessionMessages($sessionId: String!, $limit: Int) {
                listChatMessageBySessionIdAndCreatedAt(
                    sessionId: $sessionId
                    sortDirection: DESC
                    limit: $limit
                ) {
                    items {
                        id
                        sequenceNumber
                        createdAt
                    }
                }
            }
            """
            result = self.client.execute(query, {'sessionId': session_id, 'limit': 50})
            payload = self._graphql_field(result, 'listChatMessageBySessionIdAndCreatedAt')
            items = payload.get('items', []) if isinstance(payload, dict) else []
            if not items:
                return 0

            for item in items:
                if not isinstance(item, dict):
                    continue
                sequence_number = item.get('sequenceNumber')
                try:
                    return int(sequence_number)
                except (TypeError, ValueError):
                    continue
            return 0
        except Exception as e:
            logger.debug(f"Could not resolve latest sequence number for session {session_id}: {e}")
            return 0

    def _resolve_account_id_for_session(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Resolve account ID for chat writes without relying solely on env defaults."""
        context = context or {}

        # 1) Prefer explicit runtime context if available
        account_id = context.get('account_id') or context.get('accountId')
        if account_id:
            return str(account_id)

        # 2) Resolve from the procedure record itself
        try:
            query = """
            query GetProcedureAccount($id: ID!) {
                getProcedure(id: $id) {
                    accountId
                }
            }
            """
            result = self.client.execute(query, {'id': self.procedure_id})
            if isinstance(result, dict):
                procedure = result.get('data', {}).get('getProcedure') if 'data' in result else result.get('getProcedure')
                procedure_account_id = procedure.get('accountId') if isinstance(procedure, dict) else None
                if procedure_account_id:
                    return str(procedure_account_id)
        except Exception as e:
            logger.debug(f"Could not resolve accountId from procedure {self.procedure_id}: {e}")

        # 3) Final fallback to existing env-based resolver
        try:
            return self.client._resolve_account_id()
        except Exception:
            return None
        
    async def start_session(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Start a new chat session for the procedure run."""
        try:
            # Resolve account first so resumed writes stay account-scoped.
            account_id = self._resolve_account_id_for_session(context)
            if not account_id:
                raise ValueError("Could not resolve account ID. Is PLEXUS_ACCOUNT_KEY set?")

            explicit_session_id = None
            if isinstance(context, dict):
                explicit_session_id = (
                    context.get('chat_session_id')
                    or context.get('session_id')
                    or context.get('sessionId')
                )
            if isinstance(explicit_session_id, str) and explicit_session_id.strip():
                self.session_id = explicit_session_id.strip()
                self.account_id = account_id
                self.sequence_number = self._get_latest_sequence_number_for_session(self.session_id)
                logger.info(
                    f"Reusing explicit chat session: {self.session_id} for account: {account_id} "
                    f"(last sequence: {self.sequence_number})"
                )
                return self.session_id

            resume_session_id = self._get_resume_session_id()
            if resume_session_id:
                self.session_id = resume_session_id
                self.account_id = account_id
                self.sequence_number = self._get_latest_sequence_number_for_session(resume_session_id)
                logger.info(
                    f"Reusing active chat session: {self.session_id} for account: {account_id} "
                    f"(last sequence: {self.sequence_number})"
                )
                return self.session_id

            console_chat_metadata = self._get_latest_console_chat_metadata(account_id)
            console_session_id = None
            if isinstance(console_chat_metadata, dict):
                session_id = console_chat_metadata.get('session_id')
                if isinstance(session_id, str) and session_id.strip():
                    console_session_id = session_id.strip()

            if console_session_id:
                self.session_id = console_session_id
                self.account_id = account_id
                self.sequence_number = self._get_latest_sequence_number_for_session(console_session_id)
                logger.info(
                    f"Reusing console chat session from task metadata: {self.session_id} for account: {account_id} "
                    f"(last sequence: {self.sequence_number})"
                )
                return self.session_id

            # Create ChatSession record
            # Get the actual IDs that are being passed
            scorecard_id = context.get('scorecard_id') if context else None
            score_id = context.get('score_id') if context else None
            
            session_category = 'Console' if isinstance(console_chat_metadata, dict) else 'Hypothesize'
            if isinstance(console_chat_metadata, dict) and not console_session_id:
                logger.info(
                    "Console-triggered task metadata found without reusable session_id for procedure %s; "
                    "creating new Console chat session.",
                    self.procedure_id,
                )

            session_data = {
                'accountId': account_id,
                'procedureId': self.procedure_id,
                'category': session_category,
                'status': 'ACTIVE'
            }
            
            # Add scorecard/score IDs if they are present
            if scorecard_id and str(scorecard_id).strip():
                session_data['scorecardId'] = scorecard_id
                
            if score_id and str(score_id).strip():
                session_data['scoreId'] = score_id
            
            # Execute GraphQL mutation to create session
            mutation = """
            mutation CreateChatSession($input: CreateChatSessionInput!) {
                createChatSession(input: $input) {
                    id
                    status
                    createdAt
                }
            }
            """
            
            result = self.client.execute(
                mutation,
                {'input': session_data},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
            
            # Check for GraphQL errors first
            if 'errors' in result:
                logger.error(f"GraphQL error creating session: {result['errors']}")
                return None
                
            # Handle both wrapped and unwrapped GraphQL responses
            chat_session_result = None
            if result and 'data' in result and 'createChatSession' in result['data']:
                chat_session_result = result['data']['createChatSession']
            elif result and 'createChatSession' in result:
                chat_session_result = result['createChatSession']
            
            if chat_session_result and 'id' in chat_session_result:
                self.session_id = chat_session_result['id']
                self.account_id = account_id  # Store account_id for use in message recording
                logger.info(f"Chat session created: {self.session_id} for account: {account_id}")
                return self.session_id
            else:
                logger.error(f"Failed to create session - unexpected result: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error starting session: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    async def record_message(
        self,
        role: str,
        content: str,
        message_type: str = 'MESSAGE',
        tool_name: Optional[str] = None,
        tool_parameters: Optional[Dict[str, Any]] = None,
        tool_response: Optional[Dict[str, Any]] = None,
        parent_message_id: Optional[str] = None,
        human_interaction: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Record a chat message."""
        if not self.session_id:
            logger.warning("No active session - cannot record message")
            return None

        try:
            self.sequence_number += 1

            # Truncate content if it exceeds DynamoDB limits (400KB total item size)
            # Allow approximately 300KB for content to leave room for other fields
            MAX_CONTENT_SIZE = 300 * 1024  # 300KB in bytes
            original_content = content

            if len(content.encode('utf-8')) > MAX_CONTENT_SIZE:
                # Truncate content while preserving UTF-8 encoding
                truncated_bytes = content.encode('utf-8')[:MAX_CONTENT_SIZE]
                # Decode and handle potential broken UTF-8 at the end
                try:
                    content = truncated_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # Try truncating a bit more to avoid broken UTF-8
                    content = truncated_bytes[:-10].decode('utf-8', errors='ignore')

                # Add truncation indicator
                content += "\n\n... [Content truncated due to size limits]"
                logger.warning(f"Truncated message content from {len(original_content)} to {len(content)} characters")

            # Set intelligent default for humanInteraction if not provided
            if human_interaction is None:
                if role == 'USER':
                    human_interaction = 'CHAT'
                elif role == 'ASSISTANT':
                    human_interaction = 'CHAT_ASSISTANT'
                elif message_type == 'TOOL_CALL' or message_type == 'TOOL_RESPONSE':
                    human_interaction = 'INTERNAL'
                else:
                    # SYSTEM and other messages default to INTERNAL
                    human_interaction = 'INTERNAL'

            message_data = {
                'sessionId': self.session_id,
                'procedureId': self.procedure_id,
                'role': role,
                'content': content,
                'messageType': message_type,
                'sequenceNumber': self.sequence_number,
                'humanInteraction': human_interaction
            }

            # Add accountId if available
            if self.account_id:
                message_data['accountId'] = self.account_id

            # Add tool-specific fields if provided
            if tool_name:
                message_data['toolName'] = tool_name
            if tool_parameters:
                message_data['toolParameters'] = json.dumps(tool_parameters)
            if tool_response:
                message_data['toolResponse'] = json.dumps(_slim_tool_response_for_storage(tool_response))
            if parent_message_id:
                message_data['parentMessageId'] = parent_message_id

            # Add metadata if provided (for rich message formatting)
            if metadata:
                message_data['metadata'] = json.dumps(metadata)
            
            # Log message recording (reduced noise - just sequence and type)
            tool_info = f" | Tool: {tool_name}" if tool_name else ""
            logger.debug(f"📝 Recording message [{self.sequence_number}] {role}/{message_type}{tool_info}")

            # NOTE: We record the FULL content in the database, only the log is truncated

            # Execute GraphQL mutation to create message
            mutation = """
            mutation CreateChatMessage($input: CreateChatMessageInput!) {
                createChatMessage(input: $input) {
                    id
                    sequenceNumber
                    createdAt
                }
            }
            """

            result = self.client.execute(
                mutation,
                {'input': message_data},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
            
            # Check for GraphQL errors first
            if 'errors' in result:
                logger.error(f"GraphQL error creating message: {result['errors']}")
                return None
                
            # Handle both wrapped and unwrapped GraphQL responses
            chat_message_result = None
            if result and 'data' in result and 'createChatMessage' in result['data']:
                chat_message_result = result['data']['createChatMessage']
            elif result and 'createChatMessage' in result:
                chat_message_result = result['createChatMessage']
            
            if chat_message_result and 'id' in chat_message_result:
                message_id = chat_message_result['id']
                logger.info(f"✅ Created message {message_id} (seq {self.sequence_number})")
                return message_id
            else:
                logger.error(f"Failed to create message - unexpected result: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error recording message: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None

    async def update_message(
        self,
        message_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        human_interaction: Optional[str] = None,
        tool_response: Optional[Any] = None,
    ) -> bool:
        """Update an existing chat message."""
        if not message_id:
            logger.warning("Cannot update chat message without message_id")
            return False

        update_input: Dict[str, Any] = {"id": message_id}

        if content is not None:
            # Keep update payload safely below DynamoDB item limits.
            max_content_size = 300 * 1024  # 300KB in bytes
            normalized_content = content
            if len(normalized_content.encode("utf-8")) > max_content_size:
                truncated_bytes = normalized_content.encode("utf-8")[:max_content_size]
                try:
                    normalized_content = truncated_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    normalized_content = truncated_bytes[:-10].decode("utf-8", errors="ignore")
                normalized_content += "\n\n... [Content truncated due to size limits]"
                logger.warning(
                    "Truncated update_message content for %s from %s to %s chars",
                    message_id,
                    len(content),
                    len(normalized_content),
                )
            update_input["content"] = normalized_content

        if metadata is not None:
            update_input["metadata"] = json.dumps(metadata)

        if human_interaction is not None:
            update_input["humanInteraction"] = human_interaction

        if tool_response is not None:
            update_input["toolResponse"] = json.dumps(_slim_tool_response_for_storage(tool_response))

        if len(update_input) == 1:
            logger.debug("No update fields provided for message %s", message_id)
            return True

        mutation = """
        mutation UpdateChatMessage($input: UpdateChatMessageInput!) {
            updateChatMessage(input: $input) {
                id
                content
                humanInteraction
                metadata
            }
        }
        """

        try:
            result = self.client.execute(
                mutation,
                {"input": update_input},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
            if isinstance(result, dict) and result.get("errors"):
                logger.error("GraphQL error updating message %s: %s", message_id, result["errors"])
                return False

            updated = None
            if isinstance(result, dict):
                data = result.get("data")
                if isinstance(data, dict):
                    updated = data.get("updateChatMessage")
                if updated is None:
                    updated = result.get("updateChatMessage")

            if isinstance(updated, dict) and updated.get("id"):
                logger.debug("Updated chat message %s", message_id)
                return True

            logger.error("Unexpected updateChatMessage result for %s: %s", message_id, result)
            return False
        except Exception as e:
            logger.error(f"Error updating chat message {message_id}: {e}", exc_info=True)
            return False
    
    def _get_next_sequence_number(self) -> int:
        """Thread-safe sequence number generation."""
        import threading
        
        # Initialize lock if not already done
        if self._sequence_lock is None:
            self._sequence_lock = threading.Lock()
        
        with self._sequence_lock:
            self.sequence_number += 1
            return self.sequence_number
    
    def record_message_sync(
        self, 
        role: str, 
        content: str, 
        message_type: str = 'MESSAGE',
        tool_name: Optional[str] = None,
        parent_message_id: Optional[str] = None
    ) -> str:
        """Synchronous wrapper for recording messages from callbacks."""
        import asyncio
        import threading
        
        message_id = None
        error = None
        
        def run_async():
            nonlocal message_id, error
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Override sequence number generation in async call for thread safety
                original_seq = self.sequence_number
                self.sequence_number = original_seq  # Don't increment here
                
                message_id = loop.run_until_complete(
                    self.record_message_with_sequence(
                        role, content, message_type, tool_name, None, None, parent_message_id,
                        sequence_number=self._get_next_sequence_number()
                    )
                )
                loop.close()
            except Exception as e:
                error = e
        
        thread = threading.Thread(target=run_async)
        thread.start()
        thread.join(timeout=30)  # 30 second timeout
        
        if error:
            logger.error(f"Error in sync message recording: {error}")
            return None
            
        return message_id
    
    async def record_message_with_sequence(
        self,
        role: str,
        content: str,
        message_type: str = 'MESSAGE',
        tool_name: Optional[str] = None,
        tool_parameters: Optional[Dict[str, Any]] = None,
        tool_response: Optional[Dict[str, Any]] = None,
        parent_message_id: Optional[str] = None,
        sequence_number: Optional[int] = None,
        human_interaction: Optional[str] = None
    ) -> str:
        """Record a chat message with explicit sequence number."""
        if not self.session_id:
            logger.warning("No active session - cannot record message")
            return None

        try:
            # Use provided sequence number or generate new one
            if sequence_number is None:
                sequence_number = self._get_next_sequence_number()

            # Set intelligent default for humanInteraction if not provided
            if human_interaction is None:
                if role == 'USER':
                    human_interaction = 'CHAT'
                elif role == 'ASSISTANT':
                    human_interaction = 'CHAT_ASSISTANT'
                elif message_type == 'TOOL_CALL' or message_type == 'TOOL_RESPONSE':
                    human_interaction = 'INTERNAL'
                else:
                    # SYSTEM and other messages default to INTERNAL
                    human_interaction = 'INTERNAL'

            message_data = {
                'sessionId': self.session_id,
                'procedureId': self.procedure_id,
                'role': role,
                'content': content,
                'messageType': message_type,
                'sequenceNumber': sequence_number,
                'humanInteraction': human_interaction
                # Note: Omitting metadata field due to GraphQL validation issues
            }

            # Add accountId if available
            if self.account_id:
                message_data['accountId'] = self.account_id

            # Add tool-specific fields if provided
            if tool_name:
                message_data['toolName'] = tool_name
            # Note: Omitting tool parameters and response for now due to GraphQL validation
            # These can be stored in the content field as formatted text instead
            if parent_message_id:
                message_data['parentMessageId'] = parent_message_id
            
            # Log message recording (reduced noise)
            tool_info = f" | Tool: {tool_name}" if tool_name else ""
            logger.debug(f"📝 Recording message [{sequence_number}] {role}/{message_type}{tool_info}")
                
            # Execute GraphQL mutation to create message
            mutation = """
            mutation CreateChatMessage($input: CreateChatMessageInput!) {
                createChatMessage(input: $input) {
                    id
                    sequenceNumber
                    createdAt
                }
            }
            """
            
            result = self.client.execute(
                mutation,
                {'input': message_data},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
            
            # Check for GraphQL errors first
            if 'errors' in result:
                logger.error(f"GraphQL error creating message: {result['errors']}")
                return None
                
            # Handle both wrapped and unwrapped GraphQL responses
            chat_message_result = None
            if result and 'data' in result and 'createChatMessage' in result['data']:
                chat_message_result = result['data']['createChatMessage']
            elif result and 'createChatMessage' in result:
                chat_message_result = result['createChatMessage']
            
            if chat_message_result and 'id' in chat_message_result:
                message_id = chat_message_result['id']
                logger.info(f"✅ Created message {message_id} (seq {sequence_number})")
                return message_id
            else:
                logger.error(f"Failed to create message - unexpected result: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error recording message: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    async def record_system_message(self, content: str) -> str:
        """Record a system message (like initial prompts)."""
        return await self.record_message('SYSTEM', content)
    
    async def record_user_message(self, content: str) -> str:
        """Record a user message."""
        return await self.record_message('USER', content)
    
    async def record_assistant_message(self, content: str) -> str:
        """Record an assistant message."""
        return await self.record_message('ASSISTANT', content)
    
    async def record_tool_call(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any], 
        description: Optional[str] = None
    ) -> str:
        """Record a tool call message."""
        # Include parameters in the content since GraphQL validation is strict
        param_str = json.dumps(parameters, indent=2) if parameters else "{}"
        content = f"{description or f'Calling tool: {tool_name}'}\n\nParameters:\n{param_str}"
        return await self.record_message(
            role='ASSISTANT',
            content=content,
            message_type='TOOL_CALL',
            tool_name=tool_name
        )
    
    async def record_tool_response(
        self, 
        tool_name: str, 
        response: Any, 
        parent_message_id: str,
        description: Optional[str] = None
    ) -> str:
        """Record a tool response message."""
        # Include response in the content since GraphQL validation is strict
        response_str = json.dumps(response, indent=2) if isinstance(response, dict) else str(response)
        content = f"{description or f'Response from tool: {tool_name}'}\n\nResponse:\n{response_str}"
        return await self.record_message(
            role='TOOL',
            content=content,
            message_type='TOOL_RESPONSE',
            tool_name=tool_name,
            parent_message_id=parent_message_id
        )
    
    async def update_session_name(self, name: str) -> bool:
        """Update the name of the current chat session."""
        if not self.session_id:
            logger.warning("No active session to update")
            return False
            
        try:
            mutation = """
            mutation UpdateChatSession($input: UpdateChatSessionInput!) {
                updateChatSession(input: $input) {
                    id
                    name
                    updatedAt
                }
            }
            """
            
            session_data = {
                'id': self.session_id,
                'name': name
            }
            
            result = self.client.execute(
                mutation,
                {'input': session_data},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
            
            if 'errors' in result:
                logger.error(f"GraphQL error updating session name: {result['errors']}")
                return False
                
            logger.info(f"📝 Session {self.session_id} name updated to: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating session name: {e}")
            return False

    async def end_session(self, *args, status: str = 'COMPLETED', name: Optional[str] = None) -> bool:
        """End the chat session with optional name update.

        Supports both call styles:
        - end_session(status="COMPLETED", name="...")
        - end_session(session_id, status="COMPLETED")
        """
        known_statuses = {'FAILED', 'FAILURE', 'ERROR', 'ACTIVE', 'COMPLETED'}
        target_session_id = self.session_id

        if args:
            first_arg = args[0]
            if isinstance(first_arg, str):
                normalized_first = first_arg.strip().upper()
                # Backward-compatible positional status call: end_session("COMPLETED")
                if normalized_first in known_statuses and len(args) == 1 and status == 'COMPLETED':
                    status = first_arg
                else:
                    target_session_id = first_arg
                    if len(args) >= 2 and isinstance(args[1], str):
                        status = args[1]
                    if len(args) >= 3 and name is None and isinstance(args[2], str):
                        name = args[2]
            elif first_arg is not None:
                target_session_id = str(first_arg)

        if not target_session_id:
            logger.debug("No active session to end")
            return True
            
        try:
            name_info = f" with name '{name}'" if name else ""
            logger.info(f"Ending session {target_session_id} with status {status}{name_info}")
            
            # Normalize to GraphQL ChatSessionStatus enum
            status_map = {
                'FAILED': 'ERROR',
                'FAILURE': 'ERROR',
                'ERROR': 'ERROR',
                'ACTIVE': 'ACTIVE',
                'COMPLETED': 'COMPLETED',
            }
            normalized_status = status_map.get(str(status or '').upper(), 'ERROR')

            # Update session status and optionally name
            mutation = """
            mutation UpdateChatSession($input: UpdateChatSessionInput!) {
                updateChatSession(input: $input) {
                    id
                    status
                    name
                    updatedAt
                }
            }
            """
            
            update_data = {
                'id': target_session_id,
                'status': normalized_status
                # Note: Omitting metadata field due to GraphQL validation issues
            }
            
            if name:
                update_data['name'] = name
            
            result = self.client.execute(
                mutation,
                {'input': update_data},
                retry_policy=LONG_RUNNING_WRITE_RETRY_POLICY_NAME,
            )
            if (
                (result and isinstance(result, dict) and result.get('updateChatSession'))
                or (result and isinstance(result, dict) and result.get('data', {}).get('updateChatSession'))
            ):
                logger.info(f"Session ended: {target_session_id}")
                return True
            else:
                logger.error(f"Failed to end session: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False


class LangChainChatRecorderHook:
    """Hook into LangChain agent execution to record tool calls and responses."""
    
    def __init__(self, recorder: ProcedureChatRecorder):
        self.recorder = recorder
        self.tool_call_messages = {}  # Map tool calls to their message IDs
    
    async def record_agent_step(self, step_info: Dict[str, Any]):
        """Record a step in the agent execution."""
        try:
            action = step_info.get('action')
            if not action:
                return
                
            # Record tool call
            tool_name = action.get('tool')
            tool_input = action.get('tool_input', {})
            
            if tool_name:
                # Record the tool call
                tool_call_id = await self.recorder.record_tool_call(
                    tool_name=tool_name,
                    parameters=tool_input,
                    description=f"Agent is calling tool: {tool_name}"
                )
                
                # Store for linking response
                self.tool_call_messages[tool_name] = tool_call_id
                
                # Record tool response if available
                observation = step_info.get('observation')
                if observation and tool_call_id:
                    await self.recorder.record_tool_response(
                        tool_name=tool_name,
                        response=observation,
                        parent_message_id=tool_call_id,
                        description=f"Tool {tool_name} responded"
                    )
                    
        except Exception as e:
            logger.error(f"Error recording agent step: {e}")
