from typing import List, Set
import re

class TaskTargetPattern:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self._validate_pattern()
        self._compile_pattern()

    def _validate_pattern(self) -> None:
        if not self.pattern:
            raise ValueError("Pattern cannot be empty")

        if self.pattern == "*":
            return

        parts = self.pattern.split("/")
        if len(parts) != 2:
            raise ValueError(
                "Pattern must be in format 'domain/subdomain' or '*'"
            )

        domain, subdomain = parts
        if domain.startswith("[") and domain.endswith("]"):
            domains = [d.strip() for d in domain[1:-1].split(",")]
            if not all(domains):
                raise ValueError("Domain list cannot contain empty values")
        elif domain != "*" and not domain.isidentifier():
            raise ValueError(
                f"Domain must be a valid identifier, '*', or a list: {domain}"
            )

        if subdomain != "*" and not subdomain.isidentifier():
            raise ValueError(
                f"Subdomain must be a valid identifier or '*': {subdomain}"
            )

    def _compile_pattern(self) -> None:
        if self.pattern == "*":
            self._domain_patterns = {"*"}
            self._subdomain_pattern = "*"
            return

        domain, subdomain = self.pattern.split("/")
        
        if domain.startswith("[") and domain.endswith("]"):
            self._domain_patterns = {
                d.strip() for d in domain[1:-1].split(",")
            }
        else:
            self._domain_patterns = {domain}
            
        self._subdomain_pattern = subdomain

    def matches(self, target: str) -> bool:
        if not target or "/" not in target:
            return False

        if self.pattern == "*":
            return True

        target_domain, target_subdomain = target.split("/")

        domain_match = (
            "*" in self._domain_patterns or 
            target_domain in self._domain_patterns
        )
        
        subdomain_match = (
            self._subdomain_pattern == "*" or
            self._subdomain_pattern == target_subdomain
        )

        return domain_match and subdomain_match

class TaskTargetMatcher:
    def __init__(self, patterns: List[str]):
        self.patterns = [TaskTargetPattern(p) for p in patterns]

    def matches(self, target: str) -> bool:
        return any(pattern.matches(target) for pattern in self.patterns)

    @staticmethod
    def validate_target(target: str) -> bool:
        if not target or "/" not in target:
            return False

        domain, subdomain = target.split("/")
        return (
            domain.isidentifier() and 
            subdomain.isidentifier()
        ) 