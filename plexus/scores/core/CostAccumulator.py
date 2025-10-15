from decimal import Decimal
from typing import Dict, Any, List, Optional


class CostAccumulator:
    """
    Generic cost accumulator that any score type can use to record measurable costs.

    Tracks both aggregate totals and a list of component line items for debugging/auditing.
    """

    def __init__(self) -> None:
        self.total_usd: Decimal = Decimal('0.0')
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.cached_tokens: int = 0
        self.api_calls: int = 0
        self.duration_ms: int = 0
        self.components: List[Dict[str, Any]] = []

    def add_api_call(
        self,
        provider: str,
        model: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
        usd: Optional[Decimal] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.api_calls += 1
        self.prompt_tokens += int(prompt_tokens or 0)
        self.completion_tokens += int(completion_tokens or 0)
        self.cached_tokens += int(cached_tokens or 0)
        if usd is not None:
            self.total_usd += Decimal(str(usd))
        if duration_ms is not None:
            self.duration_ms += int(duration_ms)
        self.components.append({
            'type': 'api_call',
            'provider': provider,
            'model': model,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'cached_tokens': cached_tokens,
            'usd': float(usd) if usd is not None else 0.0,
            'duration_ms': duration_ms or 0,
            'metadata': metadata or {}
        })

    def add_http_call(self, service: str, usd: Optional[Decimal] = None, duration_ms: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        if usd is not None:
            self.total_usd += Decimal(str(usd))
        if duration_ms is not None:
            self.duration_ms += int(duration_ms)
        self.components.append({
            'type': 'http_call',
            'service': service,
            'usd': float(usd) if usd is not None else 0.0,
            'duration_ms': duration_ms or 0,
            'metadata': metadata or {}
        })

    def add_db_io(self, engine: str, operation: str, usd: Optional[Decimal] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        if usd is not None:
            self.total_usd += Decimal(str(usd))
        self.components.append({
            'type': 'db_io',
            'engine': engine,
            'operation': operation,
            'usd': float(usd) if usd is not None else 0.0,
            'metadata': metadata or {}
        })

    def add_compute(self, seconds: float, usd_per_second: Optional[Decimal] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        if usd_per_second is not None:
            self.total_usd += Decimal(str(usd_per_second)) * Decimal(str(seconds))
        self.duration_ms += int(seconds * 1000)
        self.components.append({
            'type': 'compute',
            'seconds': seconds,
            'usd_per_second': float(usd_per_second) if usd_per_second is not None else 0.0,
            'usd': float(Decimal(str(usd_per_second)) * Decimal(str(seconds))) if usd_per_second is not None else 0.0,
            'metadata': metadata or {}
        })

    def add_custom(self, label: str, usd: Optional[Decimal] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        if usd is not None:
            self.total_usd += Decimal(str(usd))
        self.components.append({
            'type': 'custom',
            'label': label,
            'usd': float(usd) if usd is not None else 0.0,
            'metadata': metadata or {}
        })

    def to_dict(self) -> Dict[str, Any]:
        total_usd_float = float(self.total_usd)
        return {
            'total_usd': total_usd_float,
            # Backward compatibility for existing code expecting total_cost
            'total_cost': total_usd_float,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'cached_tokens': self.cached_tokens,
            'api_calls': self.api_calls,
            'duration_ms': self.duration_ms,
            'components': self.components,
        }



