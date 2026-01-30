"""Tryb mockowy dla testowania bez SAS, Bitbucket i SSH."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from .bitbucket import BitbucketPlatform
from .models import PullRequest
from .logger import info

__all__ = [
    "MockSSHExecutor",
    "MockBitbucketPlatform",
    "mock_sas_session",
    "get_mock_pull_requests",
]

RemotePath = PurePosixPath


@dataclass
class MockResult:
    """Symulowany wynik komendy.

    Attributes:
        stdout: Standardowe wyjście komendy.
        stderr: Błędne wyjście komendy.
        return_code: Kod wyjścia.
        ok: Czy komenda zakończyła się sukcesem.
    """

    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    ok: bool = True


class MockSSHExecutor:
    """Symuluje SSHExecutor operując na lokalnym systemie plików.

    Attributes:
        base_dir: Bazowy katalog lokalny dla symulowanych operacji.
        user: Nazwa użytkownika (mockowa).
        host: Nazwa hosta (mockowa).
    """

    def __init__(self, local_base_dir: Path | str):
        """Inicjalizuje mockowy executor SSH.

        Args:
            local_base_dir: Bazowy katalog lokalny do symulacji.
        """
        self.base_dir = Path(local_base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.user = "mock_user"
        self.host = "mock_host"
        info(f"[MOCK] SSHExecutor: base_dir={self.base_dir}")

    def _to_local(self, remote_path: RemotePath | str) -> Path:
        """Konwertuje ścieżkę zdalną na lokalną.

        Args:
            remote_path: Ścieżka zdalna do konwersji.

        Returns:
            Odpowiadająca ścieżka lokalna.
        """
        rp = PurePosixPath(remote_path)
        # Usuń leading / żeby uzyskać relative path
        relative = str(rp).lstrip("/")
        return self.base_dir / relative

    def run_command(
        self,
        command: str,
        cwd: RemotePath | None = None,
        suppress_error_print: bool = False,
        timeout: float | None = None,
    ) -> MockResult:
        """Symuluje wykonanie komendy.

        Args:
            command: Komenda do wykonania.
            cwd: Katalog roboczy.
            suppress_error_print: Czy pomijać wyświetlanie błędów.
            timeout: Limit czasu (ignorowany w mock).

        Returns:
            Symulowany wynik komendy.
        """
        prompt = f"[MOCK {self.user}@{self.host}]$ "
        info(f"{prompt}{command}")

        # Specjalne obsłużenie niektórych komend
        if "git " in command or command.startswith("git"):
            return self._handle_git_command(command, cwd)
        if command.startswith("mkdir "):
            path_str = command.replace("mkdir -p ", "").strip().strip("'\"")
            local_path = self._to_local(path_str)
            local_path.mkdir(parents=True, exist_ok=True)
            return MockResult()
        if command.startswith("test -e "):
            path_str = command.replace("test -e ", "").strip().strip("'\"")
            local_path = self._to_local(path_str)
            ok = local_path.exists()
            return MockResult(ok=ok, return_code=0 if ok else 1)
        if command.startswith("ls "):
            return self._handle_ls_command(command)

        # Domyślnie - sukces
        return MockResult()

    def _handle_git_command(
        self, command: str, cwd: RemotePath | None
    ) -> MockResult:
        """Obsługuje komendy git.

        Args:
            command: Komenda git do obsłużenia.
            cwd: Katalog roboczy.

        Returns:
            Symulowany wynik komendy git.
        """
        local_cwd = self._to_local(cwd) if cwd else self.base_dir

        if "clone" in command:
            # Symuluj klonowanie - utwórz katalog repo
            parts = command.split()
            repo_dir_name = parts[-1].strip("'\"") if parts else "repo"
            repo_path = local_cwd / repo_dir_name
            repo_path.mkdir(parents=True, exist_ok=True)
            info(f"[MOCK] git clone -> utworzono {repo_path}")
            return MockResult()

        if "diff" in command:
            # Zwróć pustą listę zmian
            return MockResult(stdout="")

        if "merge-base" in command:
            return MockResult(stdout="abc123def456")

        if "fetch" in command or "merge" in command:
            return MockResult()

        return MockResult()

    def _handle_ls_command(self, command: str) -> MockResult:
        """Obsługuje komendę ls.

        Args:
            command: Komenda ls do obsłużenia.

        Returns:
            Symulowany wynik komendy ls.
        """
        # Wyciągnij ścieżkę z komendy
        parts = command.split()
        path_str = parts[-1].strip("'\"") if len(parts) > 1 else "."
        local_path = self._to_local(path_str)

        if local_path.exists() and local_path.is_dir():
            files = [f.name for f in local_path.iterdir()]
            return MockResult(stdout="\n".join(files))
        return MockResult(stdout="")

    def exists(self, remote_path: RemotePath) -> bool:
        """Sprawdza, czy plik lub katalog istnieje.

        Args:
            remote_path: Ścieżka do sprawdzenia.

        Returns:
            True jeśli istnieje, False w przeciwnym przypadku.
        """
        local_path = self._to_local(remote_path)
        exists = local_path.exists()
        info(f"[MOCK] exists({remote_path}) -> {exists}")
        return exists

    def mkdir(self, remote_path: RemotePath) -> None:
        """Tworzy katalog.

        Args:
            remote_path: Ścieżka do katalogu do utworzenia.
        """
        local_path = self._to_local(remote_path)
        local_path.mkdir(parents=True, exist_ok=True)
        info(f"[MOCK] mkdir({remote_path})")

    def rmdir(self, remote_path: RemotePath) -> None:
        """Usuwa katalog.

        Args:
            remote_path: Ścieżka do katalogu do usunięcia.
        """
        local_path = self._to_local(remote_path)
        if local_path.exists():
            import shutil

            shutil.rmtree(local_path)
        info(f"[MOCK] rmdir({remote_path})")

    def write_file(
        self, remote_path: RemotePath, content: str, *, encoding: str = "utf-8"
    ) -> None:
        """Zapisuje plik.

        Args:
            remote_path: Ścieżka do pliku.
            content: Treść do zapisania.
            encoding: Kodowanie tekstu.
        """
        local_path = self._to_local(remote_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(content, encoding=encoding)
        info(f"[MOCK] write_file({remote_path})")

    def read_file(
        self, remote_path: RemotePath, *, encoding: str = "utf-8"
    ) -> str:
        """Odczytuje plik.

        Args:
            remote_path: Ścieżka do pliku.
            encoding: Kodowanie tekstu.

        Returns:
            Zawartość pliku jako string.
        """
        local_path = self._to_local(remote_path)
        info(f"[MOCK] read_file({remote_path})")
        if local_path.exists():
            return local_path.read_text(encoding=encoding)
        return ""


class MockBitbucketPlatform(BitbucketPlatform):
    """Symuluje platformę Bitbucket z przykładowymi danymi PR.

    Attributes:
        repo: Nazwa repozytorium (mockowa).
        token: Token autoryzacyjny (mockowy).
        project_or_workspace: Projekt/workspace (mockowy).
    """

    def __init__(self, repo: str):
        """Inicjalizuje mockową platformę Bitbucket.

        Args:
            repo: Nazwa repozytorium.
        """
        super().__init__(repo, token="mock_token", project_or_workspace="MOCK")
        info(f"[MOCK] BitbucketPlatform: repo={repo}")

    def get_api_prs_url(self) -> str:
        return f"mock://bitbucket/{self.project_or_workspace}/{self.repo}/prs"

    def get_clone_url(self) -> str:
        return f"mock://git/{self.project_or_workspace}/{self.repo}.git"

    def parse_pr(self, raw: dict[str, Any]) -> PullRequest:
        """Parsuje surowe dane PR (mockowe).

        Args:
            raw: Surowe dane PR.

        Returns:
            Sparsowany obiekt PullRequest.
        """
        from .models import parse_server_pr
        return parse_server_pr(raw)

    def merge_pull_request(self, pr: PullRequest) -> tuple[bool, str | None]:
        info(f"[MOCK] Merge PR #{pr.id}")
        return True, None


# Mockowe dane PR
_MOCK_RAW_PRS: list[dict[str, Any]] = [
    {
        "id": 101,
        "title": "[MOCK] Feature implementation",
        "state": "OPEN",
        "fromRef": {"displayId": "feature/mock-feature"},
        "reviewers": [{"approved": True}, {"approved": True}],
    },
    {
        "id": 102,
        "title": "[MOCK] Bugfix for issue",
        "state": "OPEN",
        "fromRef": {"displayId": "bugfix/mock-bugfix"},
        "reviewers": [{"approved": True}],
    },
]


def get_mock_pull_requests() -> list[PullRequest]:
    """Zwraca listę mockowych PR jako dataclass.

    Returns:
        Lista mockowych obiektów PullRequest.
    """
    info("[MOCK] Pobieranie listy PR")
    platform = MockBitbucketPlatform("MOCK_REPO")
    return [platform.parse_pr(raw) for raw in _MOCK_RAW_PRS]


@dataclass
class MockSASSession:
    """Symulowana sesja SAS."""

    env: str = "DEV"

    def submit(self, code: str, results: str = "TEXT") -> dict[str, str]:
        """Symuluje wykonanie kodu SAS.

        Args:
            code: Kod SAS do wykonania.
            results: Format wyników.

        Returns:
            Słownik z logiem wykonania.
        """
        info(f"[MOCK] SAS submit: {len(code)} znaków kodu")
        return {"LOG": f"[MOCK] SAS Log for code execution\nNOTE: No errors."}

    def endsas(self) -> None:
        """Symuluje zamknięcie sesji."""
        info("[MOCK] SAS session ended")


@contextmanager
def mock_sas_session(env: str) -> Iterator[MockSASSession]:
    """Context manager dla mockowej sesji SAS.

    Args:
        env: Nazwa środowiska.

    Yields:
        Mockowa sesja SAS.
    """
    info(f"[MOCK] Otwieranie sesji SAS dla środowiska: {env}")
    session = MockSASSession(env=env)
    try:
        yield session
    finally:
        session.endsas()
