"""Operacje SSH z wykorzystaniem biblioteki Fabric."""
from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
import shlex
import shutil
import textwrap


from fabric import Connection
from invoke.exceptions import UnexpectedExit
from invoke.runners import Result

from ..logger import error, info

RemotePath = PurePosixPath

LOG_PREFIKS_LENGTH = 29

def quote_shell(value: RemotePath | str) -> str:
    """Zwraca bezpiecznie zacytowaną (shell) reprezentację ścieżki/napisu.

    Args:
        value: Wartość do zacytowania.

    Returns:
        Bezpiecznie zacytowany string.
    """
    return shlex.quote(str(value))


def _wrap_command(command: str, *, prefix: str) -> str:
    """Zawija komendę do szerokości terminala bez łamania słów.

    Args:
        command: Komenda do zawijania.
        prefix: Prefiks dodawany przed komendą.

    Returns:
        Zawinięta komenda z prefiksem.
    """
    term_width = shutil.get_terminal_size(fallback=(120, 40)).columns
    content_width = max(10, term_width - len(prefix) - LOG_PREFIKS_LENGTH)
    return textwrap.fill(
        command,
        width=content_width,
        initial_indent=prefix,
        subsequent_indent=" " * LOG_PREFIKS_LENGTH,
        break_long_words=False,
        break_on_hyphens=False,
    )


class SSHExecutor:
    """Wykonywanie poleceń i operacji na plikach na zdalnym hoście przez SSH.

    Attributes:
        conn: Obiekt połączenia Fabric.
    """

    def __init__(self, host: str, user: str, *, connect_timeout: float | None = None):
        """Inicjalizuje obiekt połączenia SSH.

        Args:
            host: Nazwa hosta lub adres IP.
            user: Nazwa użytkownika SSH.
            connect_timeout: Limit czasu połączenia w sekundach.
        """
        self.conn = Connection(host=host, user=user, connect_timeout=connect_timeout)

    def run_command(
        self,
        command: str,
        cwd: RemotePath | None = None,
        suppress_error_print: bool = False,
        timeout: float | None = None,
    ) -> Result:
        """Uruchamia polecenie na zdalnym hoście.

        Args:
            command: Polecenie do wykonania.
            cwd: Katalog roboczy dla polecenia.
            suppress_error_print: Czy pomińąć wyświetlanie błędów.
            timeout: Limit czasu wykonania w sekundach.

        Returns:
            Obiekt Result z wynikiem polecenia.

        Raises:
            UnexpectedExit: Gdy polecenie zakończy się błędem.
        """
        prompt = f"[{self.conn.user}@{self.conn.host}]$ "
        info(_wrap_command(command, prefix=prompt))
        try:
            with self.conn.cd(str(cwd) if cwd else "."):
                result = self.conn.run(command, hide=True, warn=True, pty=False, timeout=timeout)

            if not result.ok:
                raise UnexpectedExit(result)

            return result
        except UnexpectedExit as exc:
            if not suppress_error_print:
                error(
                    "Polecenie zdalne zakończone niepowodzeniem "
                    f"kod wyjścia: {exc.result.return_code}.\n"
                    f"STDOUT:\n{exc.result.stdout}\n"
                    f"STDERR:\n{exc.result.stderr}"
                )
            raise

    def exists(self, remote_path: RemotePath) -> bool:
        """Sprawdza, czy plik lub katalog istnieje na zdalnym hoście.

        Args:
            remote_path: Ścieżka do sprawdzenia.

        Returns:
            True jeśli ścieżka istnieje, False w przeciwnym przypadku.
        """
        cmd = f"test -e {quote_shell(remote_path)}"
        return self.conn.run(cmd, hide=True, warn=True, pty=False).ok

    def mkdir(self, remote_path: RemotePath) -> None:
        """Tworzy katalog (rekurencyjnie) na zdalnym hoście (odpowiednik mkdir -p).

        Args:
            remote_path: Ścieżka do katalogu do utworzenia.
        """
        self.run_command(f"mkdir -p {quote_shell(remote_path)}")

    def rmdir(self, remote_path: RemotePath) -> None:
        """Usuwa rekursywnie plik lub katalog na zdalnym hoście.

        Args:
            remote_path: Ścieżka do usunięcia.
        """
        self.run_command(f"rm -rf {quote_shell(remote_path)}")

    def write_file(self, remote_path: RemotePath, content: str, *, encoding: str = "utf-8") -> None:
        """Zapisuje zawartość tekstową do pliku na zdalnym hoście.

        Używa kodowania UTF-8 i przesyła bajty (BytesIO) kompatybilne z SFTP.

        Args:
            remote_path: Ścieżka do pliku docelowego.
            content: Treść do zapisania.
            encoding: Kodowanie tekstu (domyślnie UTF-8).
        """
        prompt = f"[{self.conn.user}@{self.conn.host}]$ "
        info(_wrap_command(f"write > {remote_path}", prefix=prompt))
        data = content.encode(encoding)
        bytes_io = BytesIO(data)
        self.conn.put(bytes_io, remote=str(remote_path))

    def read_file(self, remote_path: RemotePath, *, encoding: str = "utf-8") -> str:
        """Odczytuje zawartość pliku ze zdalnego hosta jako tekst.

        Pobiera plik do bufora bajtowego (BytesIO), a następnie dekoduje do `str`.

        Args:
            remote_path: Ścieżka do pliku źródłowego.
            encoding: Kodowanie tekstu (domyślnie UTF-8).

        Returns:
            Zawartość pliku jako string.
        """
        prompt = f"[{self.conn.user}@{self.conn.host}]$ "
        info(_wrap_command(f"read < {remote_path}", prefix=prompt))
        buffer = BytesIO()
        self.conn.get(str(remote_path), local=buffer)
        return buffer.getvalue().decode(encoding)
