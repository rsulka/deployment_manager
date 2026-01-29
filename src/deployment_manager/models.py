"""Modele danych dla Deployment Manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PullRequest:
    """Reprezentacja Pull Requesta z Bitbucket.
    
    Ujednolicona struktura dla Server i Cloud.
    
    Attributes:
        id: Identyfikator PR.
        title: Tytuł PR.
        source_branch: Nazwa gałęzi źródłowej.
        approval_count: Liczba akceptacji.
        version: Wersja PR (tylko Bitbucket Server).
        raw_data: Surowe dane z API.
    """
    
    id: int
    title: str
    source_branch: str
    approval_count: int
    version: int | None = None
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)
    
    def __lt__(self, other: object) -> bool:
        """Umożliwia sortowanie PR po id.

        Args:
            other: Obiekt do porównania.

        Returns:
            True jeśli self.id < other.id, NotImplemented dla niekompatybilnych typów.
        """
        if not isinstance(other, PullRequest):
            return NotImplemented
        return self.id < other.id
    
    def __str__(self) -> str:
        """Zwraca czytelny opis PR.

        Returns:
            Sformatowany string z id, tytułem i gałęzią.
        """
        return f"PR #{self.id}: {self.title} ({self.source_branch})"


def parse_server_pr(raw: dict[str, Any]) -> PullRequest:
    """Parsuje odpowiedź Bitbucket Server do PullRequest.

    Args:
        raw: Surowe dane PR z API Bitbucket Server.

    Returns:
        Obiekt PullRequest z wyparsowanymi danymi.
    """
    reviewers = raw.get("reviewers", [])
    approval_count = sum(1 for r in reviewers if r.get("approved"))
    
    from_ref = raw.get("fromRef", {})
    source_branch = from_ref.get("displayId", "")
    
    return PullRequest(
        id=int(raw.get("id", 0)),
        title=raw.get("title", ""),
        source_branch=source_branch,
        approval_count=approval_count,
        version=raw.get("version"),
        raw_data=raw,
    )


def parse_cloud_pr(raw: dict[str, Any]) -> PullRequest:
    """Parsuje odpowiedź Bitbucket Cloud do PullRequest.

    Args:
        raw: Surowe dane PR z API Bitbucket Cloud.

    Returns:
        Obiekt PullRequest z wyparsowanymi danymi.
    """
    participants = raw.get("participants", [])
    approval_count = sum(1 for p in participants if p.get("approved"))
    
    source = raw.get("source", {})
    branch = source.get("branch", {})
    source_branch = branch.get("name", "")
    
    return PullRequest(
        id=int(raw.get("id", 0)),
        title=raw.get("title", ""),
        source_branch=source_branch,
        approval_count=approval_count,
        version=None,
        raw_data=raw,
    )
