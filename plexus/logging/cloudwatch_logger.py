"""
CloudWatch Logs integration for Plexus components.

Each component invocation opens two log streams:
  {component_name}/run/{invocation_id}         - lifecycle events, tool calls, cost events
  {component_name}/llm-context/{invocation_id} - full JSON per LLM call (prompt_context)

Log group: /plexus/{log_category}/{account_key}

All methods degrade gracefully when AWS is not configured; they never raise.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _safe_account_key(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "-", raw)[:64] or "unknown"


def _epoch_ms() -> int:
    return int(time.time() * 1000)


def _get_data_protection_policy() -> str:
    """
    Get CloudWatch Logs data protection policy for PII/PHI masking.

    Uses AWS managed data identifiers to automatically detect and mask:
    - PII (emails, phone numbers, SSNs, addresses)
    - PHI (medical records, health plan IDs)
    - Financial data (credit cards, bank accounts)
    - Credentials (API keys, AWS secrets)

    Returns:
        JSON string of data protection policy
    """
    policy = {
        "Name": "data-protection-policy",
        "Description": "",
        "Version": "2021-06-01",
        "Statement": [
            {
            "Sid": "audit-policy",
            "DataIdentifier": [
                "arn:aws:dataprotection::aws:data-identifier/Address",
                "arn:aws:dataprotection::aws:data-identifier/AwsSecretKey",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-DE",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-FR",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-IT",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/CepCode-BR",
                "arn:aws:dataprotection::aws:data-identifier/Cnpj-BR",
                "arn:aws:dataprotection::aws:data-identifier/CpfCode-BR",
                "arn:aws:dataprotection::aws:data-identifier/CreditCardExpiration",
                "arn:aws:dataprotection::aws:data-identifier/CreditCardMagneticStripe",
                "arn:aws:dataprotection::aws:data-identifier/CreditCardNumber",
                "arn:aws:dataprotection::aws:data-identifier/CreditCardSecurityCode",
                "arn:aws:dataprotection::aws:data-identifier/DateOfBirth",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-AT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-AU",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-BE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-BG",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-CA",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-CY",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-CZ",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-DE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-DK",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-EE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-ES",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-FI",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-FR",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-GB",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-GR",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-HR",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-HU",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-IE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-IT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-LT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-LU",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-LV",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-MT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-NL",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-PL",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-PT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-RO",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-SE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-SI",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-SK",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-US",
                "arn:aws:dataprotection::aws:data-identifier/DrugEnforcementAgencyNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/ElectoralRollNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/EmailAddress",
                "arn:aws:dataprotection::aws:data-identifier/HealthInsuranceCardNumber-EU",
                "arn:aws:dataprotection::aws:data-identifier/HealthInsuranceClaimNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/HealthInsuranceNumber-FR",
                "arn:aws:dataprotection::aws:data-identifier/HealthcareProcedureCode-US",
                "arn:aws:dataprotection::aws:data-identifier/IndividualTaxIdentificationNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/InseeCode-FR",
                "arn:aws:dataprotection::aws:data-identifier/IpAddress",
                "arn:aws:dataprotection::aws:data-identifier/LatLong",
                "arn:aws:dataprotection::aws:data-identifier/MedicareBeneficiaryNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/Name",
                "arn:aws:dataprotection::aws:data-identifier/NationalDrugCode-US",
                "arn:aws:dataprotection::aws:data-identifier/NationalIdentificationNumber-DE",
                "arn:aws:dataprotection::aws:data-identifier/NationalIdentificationNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/NationalIdentificationNumber-IT",
                "arn:aws:dataprotection::aws:data-identifier/NationalInsuranceNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/NationalProviderId-US",
                "arn:aws:dataprotection::aws:data-identifier/NhsNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/NieNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/NifNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/OpenSshPrivateKey",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-CA",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-DE",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-FR",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-IT",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/PermanentResidenceNumber-CA",
                "arn:aws:dataprotection::aws:data-identifier/PersonalHealthNumber-CA",
                "arn:aws:dataprotection::aws:data-identifier/PgpPrivateKey",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-BR",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-DE",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-FR",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-IT",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/PkcsPrivateKey",
                "arn:aws:dataprotection::aws:data-identifier/PostalCode-CA",
                "arn:aws:dataprotection::aws:data-identifier/PuttyPrivateKey",
                "arn:aws:dataprotection::aws:data-identifier/RgNumber-BR",
                "arn:aws:dataprotection::aws:data-identifier/SocialInsuranceNumber-CA",
                "arn:aws:dataprotection::aws:data-identifier/Ssn-ES",
                "arn:aws:dataprotection::aws:data-identifier/Ssn-US",
                "arn:aws:dataprotection::aws:data-identifier/TaxId-DE",
                "arn:aws:dataprotection::aws:data-identifier/TaxId-ES",
                "arn:aws:dataprotection::aws:data-identifier/TaxId-FR",
                "arn:aws:dataprotection::aws:data-identifier/TaxId-GB",
                "arn:aws:dataprotection::aws:data-identifier/VehicleIdentificationNumber",
                "arn:aws:dataprotection::aws:data-identifier/ZipCode-US"
            ],
            "Operation": {
                "Audit": {
                "FindingsDestination": {}
                }
            }
            },
            {
            "Sid": "redact-policy",
            "DataIdentifier": [
                "arn:aws:dataprotection::aws:data-identifier/Address",
                "arn:aws:dataprotection::aws:data-identifier/AwsSecretKey",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-DE",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-FR",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-IT",
                "arn:aws:dataprotection::aws:data-identifier/BankAccountNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/CepCode-BR",
                "arn:aws:dataprotection::aws:data-identifier/Cnpj-BR",
                "arn:aws:dataprotection::aws:data-identifier/CpfCode-BR",
                "arn:aws:dataprotection::aws:data-identifier/CreditCardExpiration",
                "arn:aws:dataprotection::aws:data-identifier/CreditCardMagneticStripe",
                "arn:aws:dataprotection::aws:data-identifier/CreditCardNumber",
                "arn:aws:dataprotection::aws:data-identifier/CreditCardSecurityCode",
                "arn:aws:dataprotection::aws:data-identifier/DateOfBirth",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-AT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-AU",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-BE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-BG",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-CA",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-CY",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-CZ",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-DE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-DK",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-EE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-ES",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-FI",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-FR",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-GB",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-GR",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-HR",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-HU",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-IE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-IT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-LT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-LU",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-LV",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-MT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-NL",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-PL",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-PT",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-RO",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-SE",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-SI",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-SK",
                "arn:aws:dataprotection::aws:data-identifier/DriversLicense-US",
                "arn:aws:dataprotection::aws:data-identifier/DrugEnforcementAgencyNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/ElectoralRollNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/EmailAddress",
                "arn:aws:dataprotection::aws:data-identifier/HealthInsuranceCardNumber-EU",
                "arn:aws:dataprotection::aws:data-identifier/HealthInsuranceClaimNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/HealthInsuranceNumber-FR",
                "arn:aws:dataprotection::aws:data-identifier/HealthcareProcedureCode-US",
                "arn:aws:dataprotection::aws:data-identifier/IndividualTaxIdentificationNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/InseeCode-FR",
                "arn:aws:dataprotection::aws:data-identifier/IpAddress",
                "arn:aws:dataprotection::aws:data-identifier/LatLong",
                "arn:aws:dataprotection::aws:data-identifier/MedicareBeneficiaryNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/Name",
                "arn:aws:dataprotection::aws:data-identifier/NationalDrugCode-US",
                "arn:aws:dataprotection::aws:data-identifier/NationalIdentificationNumber-DE",
                "arn:aws:dataprotection::aws:data-identifier/NationalIdentificationNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/NationalIdentificationNumber-IT",
                "arn:aws:dataprotection::aws:data-identifier/NationalInsuranceNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/NationalProviderId-US",
                "arn:aws:dataprotection::aws:data-identifier/NhsNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/NieNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/NifNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/OpenSshPrivateKey",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-CA",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-DE",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-FR",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-IT",
                "arn:aws:dataprotection::aws:data-identifier/PassportNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/PermanentResidenceNumber-CA",
                "arn:aws:dataprotection::aws:data-identifier/PersonalHealthNumber-CA",
                "arn:aws:dataprotection::aws:data-identifier/PgpPrivateKey",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-BR",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-DE",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-ES",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-FR",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-GB",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-IT",
                "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-US",
                "arn:aws:dataprotection::aws:data-identifier/PkcsPrivateKey",
                "arn:aws:dataprotection::aws:data-identifier/PostalCode-CA",
                "arn:aws:dataprotection::aws:data-identifier/PuttyPrivateKey",
                "arn:aws:dataprotection::aws:data-identifier/RgNumber-BR",
                "arn:aws:dataprotection::aws:data-identifier/SocialInsuranceNumber-CA",
                "arn:aws:dataprotection::aws:data-identifier/Ssn-ES",
                "arn:aws:dataprotection::aws:data-identifier/Ssn-US",
                "arn:aws:dataprotection::aws:data-identifier/TaxId-DE",
                "arn:aws:dataprotection::aws:data-identifier/TaxId-ES",
                "arn:aws:dataprotection::aws:data-identifier/TaxId-FR",
                "arn:aws:dataprotection::aws:data-identifier/TaxId-GB",
                "arn:aws:dataprotection::aws:data-identifier/VehicleIdentificationNumber",
                "arn:aws:dataprotection::aws:data-identifier/ZipCode-US"
            ],
            "Operation": {
                "Deidentify": {
                "MaskConfig": {}
                }
            }
            }
        ]
        }
    return json.dumps(policy)


class PlexusCloudWatchLogger:
    """Streams Plexus component execution events to two CloudWatch log streams."""

    def __init__(
        self,
        account_key: str,
        component_name: str,
        invocation_id: str,
        log_category: str = "procedures",
    ) -> None:
        """
        Initialize CloudWatch logger.

        Args:
            account_key: Account identifier for log group segmentation
            component_name: Component identifier (e.g., procedure ID, "console/chat")
            invocation_id: Unique invocation identifier (e.g., run ID, message ID)
            log_category: Category for log group (default: "procedures")
        """
        self._component_name = component_name
        self._invocation_id = invocation_id
        self.log_group = f"/plexus/{log_category}/{_safe_account_key(account_key)}"
        self._run_stream = f"{component_name}/run/{invocation_id}"
        self._llm_stream = f"{component_name}/llm-context/{invocation_id}"
        self._logs_client: Any = None
        self._closed = False
        self._init_client()

    def _init_client(self) -> None:
        aws_region = (
            os.getenv("AWS_REGION")
            or os.getenv("AWS_REGION_NAME")
            or os.getenv("AWS_DEFAULT_REGION")
        )
        if not aws_region:
            logger.debug("AWS region not set; CloudWatch logging disabled")
            return
        try:
            import boto3
            is_lambda = os.getenv("AWS_EXECUTION_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            if is_lambda or not (aws_access_key and aws_secret_key):
                self._logs_client = boto3.client("logs", region_name=aws_region)
            else:
                self._logs_client = boto3.client(
                    "logs",
                    region_name=aws_region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                )
        except Exception as exc:
            logger.debug("Could not initialize CloudWatch Logs client: %s", exc)

    def open(self) -> None:
        if not self._logs_client:
            return
        try:
            # Create log group
            try:
                self._logs_client.create_log_group(logGroupName=self.log_group)
            except self._logs_client.exceptions.ResourceAlreadyExistsException:
                # Log group creation is idempotent; existing group is expected on retries.
                pass

            # Apply data protection policy for PII/PHI masking
            # Note: Always try to apply, even if log group already existed
            try:
                response = self._logs_client.put_data_protection_policy(
                    logGroupIdentifier=self.log_group,
                    policyDocument=_get_data_protection_policy()
                )
                logger.info("Applied data protection policy to %s: %s", self.log_group, response)
            except Exception as exc:
                # Non-fatal: log group is still usable, just without PII protection
                logger.error("Could not apply data protection policy to %s: %s", self.log_group, exc, exc_info=True)

            # Create log streams
            for stream in (self._run_stream, self._llm_stream):
                try:
                    self._logs_client.create_log_stream(
                        logGroupName=self.log_group, logStreamName=stream
                    )
                except self._logs_client.exceptions.ResourceAlreadyExistsException:
                    # Stream creation is idempotent; existing streams are non-fatal.
                    pass

            # Log initial event
            self._put(self._run_stream, json.dumps({
                "event": "component_started",
                "component_name": self._component_name,
                "invocation_id": self._invocation_id,
                "log_group": self.log_group,
                "run_stream": self._run_stream,
                "llm_context_stream": self._llm_stream,
            }))
        except Exception as exc:
            logger.debug("CloudWatch open failed: %s", exc)

    def _put(self, stream_name: str, message: str) -> None:
        try:
            self._logs_client.put_log_events(
                logGroupName=self.log_group,
                logStreamName=stream_name,
                logEvents=[{"timestamp": _epoch_ms(), "message": message}],
            )
        except Exception as exc:
            logger.debug("put_log_events(%s) failed: %s", stream_name, exc)

    def log_run_event_from_tactus(self, event: Any) -> None:
        if not self._logs_client or self._closed:
            return
        try:
            self._put(self._run_stream, _format_tactus_event(event))
        except Exception as exc:
            logger.debug("log_run_event_from_tactus failed: %s", exc)

    def log_llm_context(self, payload: Dict[str, Any]) -> None:
        if not self._logs_client or self._closed:
            return
        try:
            self._put(self._llm_stream, json.dumps(payload, ensure_ascii=False, default=str))
        except Exception as exc:
            logger.debug("log_llm_context failed: %s", exc)

    def close(self, success: bool = True) -> None:
        if self._closed or not self._logs_client:
            return
        self._closed = True
        event_name = "component_completed" if success else "component_failed"
        self._put(self._run_stream, json.dumps({
            "event": event_name,
            "component_name": self._component_name,
            "invocation_id": self._invocation_id,
        }))


def _format_tactus_event(event: Any) -> str:
    try:
        from tactus.protocols.models import CostEvent
        if isinstance(event, CostEvent):
            return json.dumps({
                "event": "cost",
                "agent": getattr(event, "agent_name", None),
                "model": getattr(event, "model", None),
                "cost_usd": getattr(event, "total_cost", None) or getattr(event, "cost", None),
                "total_tokens": getattr(event, "total_tokens", None),
                "cache_hit": getattr(event, "cache_hit", False),
            }, default=str)
    except Exception as exc:
        logger.debug(
            "Falling back to generic tactus event formatting: %s",
            exc,
            exc_info=True,
        )

    event_type = getattr(event, "event_type", None) or type(event).__name__
    content = getattr(event, "content", None) or getattr(event, "message", None)
    role = getattr(event, "role", None)
    parts: Dict[str, Any] = {"event": str(event_type)}
    if role:
        parts["role"] = str(role)
    if content:
        text = str(content)
        parts["content"] = text[:500] + "…" if len(text) > 500 else text
    return json.dumps(parts, default=str) if len(parts) > 1 else str(event_type)
