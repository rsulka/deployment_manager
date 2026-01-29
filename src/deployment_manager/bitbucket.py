"""Integracja z Bitbucket Server/Cloud: pobieranie, scalanie PR i klonowanie."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, cast

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import urllib3

from .config import Config
from .logger import info
from .models import PullRequest, parse_server_pr, parse_cloud_pr

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

__all__ = [
    "BitbucketPlatform",
    "BitbucketServerPlatform",
    "BitbucketCloudPlatform",
    "create_platform",
    "get_pull_requests",
    "PullRequest",
]


def _create_session() -> requests.Session:
    """Tworzy sesję HTTP z retry dla stabilniejszych wywołań API.

    Returns:
        Skonfigurowana sesja HTTP z mechanizmem retry.
    """
    session = requests.Session()
    retry = Retry(
        total=5,
        read=5,
        connect=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class BitbucketPlatform(ABC):
    """Abstrakcja platformy Bitbucket (wspólne API dla Server i Cloud).

    Attributes:
        repo: Nazwa repozytorium.
        token: Token autoryzacyjny API.
        project_or_workspace: Projekt (Server) lub workspace (Cloud).
    """

    def __init__(self, repo: str, token: str, project_or_workspace: str):
        """Inicjalizuje platformę Bitbucket.

        Args:
            repo: Nazwa repozytorium.
            token: Token autoryzacyjny API.
            project_or_workspace: Projekt (Server) lub workspace (Cloud).
        """
        self.repo = repo
        self.token = token
        self.project_or_workspace = project_or_workspace

    @abstractmethod
    def get_api_prs_url(self) -> str:
        """Zwraca pełny URL endpointu API listy otwartych PR.

        Returns:
            Pełny URL endpointu API.
        """

    @abstractmethod
    def get_clone_url(self) -> str:
        """Zwraca URL używany do klonowania repozytorium (SSH).

        Returns:
            URL do klonowania repozytorium przez SSH.
        """

    @abstractmethod
    def parse_pr(self, raw: dict[str, Any]) -> PullRequest:
        """Parsuje surowe dane PR z API do dataclass PullRequest.

        Args:
            raw: Surowe dane PR z odpowiedzi API.

        Returns:
            Sparsowany obiekt PullRequest.
        """

    @abstractmethod
    def merge_pull_request(self, pr: PullRequest) -> tuple[bool, str | None]:
        """Scala podany PR w Bitbucket.

        Args:
            pr: Obiekt PullRequest do scalenia.

        Returns:
            Krotka (True, None) przy powodzeniu lub (False, przyczyna) przy niepowodzeniu.
        """


class BitbucketServerPlatform(BitbucketPlatform):
    """Implementacja dla Bitbucket Server."""

    def __init__(self, repo: str, token: str, project_or_workspace: str, host: str):
        super().__init__(repo, token, project_or_workspace)
        self.host = host

    def get_api_prs_url(self) -> str:
        base_url = (
            f"https://{self.host}/rest/api/1.0/projects/"
            f"{self.project_or_workspace}/repos/{self.repo}/pull-requests"
        )
        params = "state=OPEN&at=refs/heads/master"
        return f"{base_url}?{params}"

    def get_clone_url(self) -> str:
        return (
            f"ssh://git@{self.host}:7999/{self.project_or_workspace.lower()}/"
            f"{self.repo}.git"
        )

    def parse_pr(self, raw: dict[str, Any]) -> PullRequest:
        return parse_server_pr(raw)

    def merge_pull_request(self, pr: PullRequest) -> tuple[bool, str | None]:
        pr_id = pr.id
        url = (
            f"https://{self.host}/rest/api/1.0/projects/"
            f"{self.project_or_workspace}/repos/{self.repo}/pull-requests/{pr_id}/merge"
        )
        session = _create_session()
        headers = {"Authorization": f"Bearer {self.token}"}
        params: dict[str, Any] = {}
        if pr.version is not None:
            params["version"] = pr.version
        def _do_post(p: dict[str, Any]) -> tuple[bool, str | None, requests.Response | None]:
            try:
                resp = session.post(url, headers=headers, json=p or None, verify=False, timeout=15)
            except requests.exceptions.RequestException as exc:
                return False, f"Błąd sieciowy podczas merge: {exc}", None

            if resp.status_code == 200:
                return True, None, resp

            reason_local: str | None = None
            try:
                data = cast(dict[str, Any], resp.json())
                errs = cast(list[Any] | None, data.get("errors"))
                if isinstance(errs, list) and errs:
                    messages: list[str] = []
                    for e in errs:
                        msg: str | None = None
                        if isinstance(e, dict):
                            e_dict = cast(dict[str, Any], e)
                            msg = cast(str | None, e_dict.get("message"))
                        if isinstance(msg, str) and msg:
                            messages.append(msg)
                        else:
                            messages.append(str(cast(object, e)))
                    reason_local = "; ".join(messages)
                if not reason_local:
                    m = data.get("message")
                    if isinstance(m, str):
                        reason_local = m
            except (ValueError, TypeError):
                reason_local = resp.text or f"HTTP {resp.status_code}"

            if not reason_local:
                reason_local = f"HTTP {resp.status_code}: {resp.text}"

            return False, reason_local, resp

        ok_flag, reason, resp = _do_post(params)

        if not ok_flag and resp is not None:
            reason_lc = (reason or "").lower()
            if ("out-of-date" in reason_lc
                or "out of date" in reason_lc
                or "attempting to modify a pull request based on out-of-date" in reason_lc
            ):

                pr_url = (
                    f"https://{self.host}/rest/api/1.0/projects/"
                    f"{self.project_or_workspace}/repos/{self.repo}/pull-requests/{pr_id}"
                )
                try:
                    pr_resp = session.get(pr_url, headers=headers, verify=False, timeout=10)
                    pr_resp.raise_for_status()
                    pr_data = pr_resp.json()
                    new_version = pr_data.get("version")
                    if isinstance(new_version, int):
                        params["version"] = new_version
                        ok_flag2, reason2, _ = _do_post(params)
                        if ok_flag2:
                            return True, None
                        return False, reason2 or reason
                except requests.exceptions.RequestException as exc:
                    return False, f"Błąd przy odświeżaniu PR przed retry: {exc}"

        return ok_flag, reason


class BitbucketCloudPlatform(BitbucketPlatform):
    """Implementacja dla Bitbucket Cloud."""

    def get_api_prs_url(self) -> str:
        base_url = (
            "https://api.bitbucket.org/2.0/repositories/"
            f"{self.project_or_workspace}/{self.repo}/pullrequests"
        )
        params = "state=OPEN&fields=%2Bvalues.participants"
        return f"{base_url}?{params}"

    def get_clone_url(self) -> str:
        return f"git@bitbucket.org:{self.project_or_workspace}/{self.repo}.git"

    def parse_pr(self, raw: dict[str, Any]) -> PullRequest:
        return parse_cloud_pr(raw)

    def merge_pull_request(self, pr: PullRequest) -> tuple[bool, str | None]:
        pr_id = pr.id
        url = (
            "https://api.bitbucket.org/2.0/repositories/"
            f"{self.project_or_workspace}/{self.repo}/pullrequests/{pr_id}/merge"
        )
        session = _create_session()
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = session.post(url, headers=headers, json={}, verify=False, timeout=15)
        except requests.exceptions.RequestException as exc:
            return False, f"Błąd sieciowy podczas merge: {exc}"

        if resp.status_code in (200, 201):
            return True, None

        reason = None
        try:
            data = cast(dict[str, Any], resp.json())
            err = data.get("error")
            if isinstance(err, dict):
                err_dict = cast(dict[str, Any], err)
                m = err_dict.get("message")
                if isinstance(m, str):
                    reason = m
        except (ValueError, TypeError):
            reason = resp.text or f"HTTP {resp.status_code}"

        if not reason:
            reason = f"HTTP {resp.status_code}"
        return False, reason


def create_platform(config: Config, repo: str) -> BitbucketPlatform:
    """Buduje obiekt platformy wg konfiguracji (Server lub Cloud).

    Args:
        config: Obiekt konfiguracji z ustawieniami Bitbucket.
        repo: Nazwa repozytorium.

    Returns:
        Obiekt platformy BitbucketServerPlatform lub BitbucketCloudPlatform.
    """

    is_server = config.get("is_bitbucket_server", False)
    token = config.get("bitbucket_api_token") or ""
    project_or_workspace = config.get("bitbucket_project_or_workspace") or ""

    if is_server:
        host = config.get("bitbucket_host") or ""
        info("Tryb: Bitbucket Server")
        return BitbucketServerPlatform(
            repo=repo,
            token=token,
            project_or_workspace=project_or_workspace,
            host=host,
        )

    info("Tryb: Bitbucket Cloud")
    return BitbucketCloudPlatform(
        repo=repo, token=token, project_or_workspace=project_or_workspace
    )


def get_pull_requests(platform: BitbucketPlatform, *, timeout: int = 10) -> list[PullRequest]:
    """Zwraca listę otwartych PR jako obiekty PullRequest.

    Args:
        platform: Obiekt platformy Bitbucket.
        timeout: Limit czasu żądania HTTP w sekundach.

    Returns:
        Lista obiektów PullRequest reprezentujących otwarte PR.

    Raises:
        RuntimeError: Gdy nie udało się pobrać danych z Bitbucket.
    """
    session = _create_session()
    url = platform.get_api_prs_url()
    headers = {"Authorization": f"Bearer {platform.token}"}

    raw_prs: list[dict[str, Any]] = []
    while True:
        try:
            response = session.get(url, headers=headers, verify=False, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Nie udało się pobrać danych z Bitbucket: {exc}") from exc

        values = data.get("values", [])
        if isinstance(values, list):
            values_list = cast(list[dict[str, Any]], values)
            raw_prs.extend(values_list)

        next_url = data.get("next")
        if next_url:
            url = next_url
            continue

        is_last_page = data.get("isLastPage")
        if is_last_page is False:
            next_start = data.get("nextPageStart")
            if next_start is not None:
                base = platform.get_api_prs_url()
                url = f"{base}&start={next_start}"
                continue

        break

    # Parsowanie do PullRequest
    return [platform.parse_pr(raw) for raw in raw_prs]
