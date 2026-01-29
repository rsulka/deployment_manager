"""Narzędzia pomocnicze dla pracy z sesją SAS."""
from __future__ import annotations

import platform
import re
from contextlib import contextmanager
from typing import Final, Iterator
from pathlib import Path

import saspy

from ..logger import info, warn, error
from .ssh_executor import SSHExecutor, RemotePath

__all__ = ["resolve_sas_cfg", "open_sas_session", "submit_sas_code"]

_WINDOWS_PREFIX: Final[str] = "ssh_win_batch_"
_UNIX_PREFIX: Final[str] = "ssh_batch_"


def resolve_sas_cfg(env: str) -> str:
    """Zwraca nazwę konfiguracji saspy dla danego *env*.

    Zależna od systemu operacyjnego (Windows, UNIX) oraz wartości
    parametru środowiskowego. Zwracana nazwa jest przekazywana do saspy
    jako *cfgname*.

    Args:
        env: Nazwa środowiska (np. 'dev', 'prod').

    Returns:
        Nazwa konfiguracji saspy dla podanego środowiska.
    """
    prefix = _WINDOWS_PREFIX if platform.system() == "Windows" else _UNIX_PREFIX
    return f"{prefix}{env.lower()}"


@contextmanager
def open_sas_session(env: str) -> Iterator[saspy.SASsession]:
    """Tworzy i zwraca nową sesję SAS dla podanego środowiska *env*.

    Używa funkcji :func:`resolve_sas_cfg` do wyznaczenia nazwy konfiguracji.

    Args:
        env: Nazwa środowiska (np. 'dev', 'prod').

    Yields:
        Utworzona sesja SAS.

    Raises:
        Exception: Gdy nawiązanie połączenia się nie powiedzie.
    """
    sas_session = None
    try:
        cfgname = resolve_sas_cfg(env)
        cfgfile = Path(__file__).resolve().parents[3] / "configs" / "sascfg_personal.py"
        info(f"Nawiązywanie połączenia SAS z konfiguracją: {cfgname}")
        sas_session = saspy.SASsession(
            cfgname=cfgname, cfgfile=str(cfgfile), verbose=False, results="TEXT"
        )
        info("Połączenie SAS nawiązane pomyślnie.")
        yield sas_session
    finally:
        if sas_session:
            info("Zamykanie połączenia SAS.")
            sas_session.endsas()


def submit_sas_code(
    sas_session: saspy.SASsession,
    ssh_executor: SSHExecutor,
    sas_code: str,
    log_file: RemotePath | str,
) -> str:
    """Wysyła kod SAS do wykonania, zapisuje log i zwraca jego treść.

    Args:
        sas_session: Aktywna sesja SAS.
        ssh_executor: Executor do wykonywania poleceń SSH.
        sas_code: Kod SAS do wykonania.
        log_file: Ścieżka do pliku logu na serwerze zdalnym.

    Returns:
        Treść logu SAS.

    Raises:
        RuntimeError: Gdy wykonanie kodu SAS zakończy się błędem.
    """
    result = sas_session.submit(sas_code, results="TEXT")
    log_content = result.get("LOG", "Nie udało się pobrać logu SAS.")

    log_path = RemotePath(log_file) if isinstance(log_file, str) else log_file
    info(f"Zapisywanie logu SAS do: {log_path}")
    ssh_executor.write_file(log_path, log_content)

    has_errors, _ = _check_sas_log(log_content)
    if has_errors:
        error("Błąd wykonania kodu SAS.")
        raise RuntimeError("Błąd wykonania kodu SAS.")

    return log_content


def _check_sas_log(log_content: str, *, report_warnings: bool = True) -> tuple[bool, bool]:
    """Analizuje treść logu SAS w poszukiwaniu błędów i (opcjonalnie) ostrzeżeń.

    Args:
        log_content: Treść logu SAS do analizy.
        report_warnings: Czy raportować ostrzeżenia (domyślnie True).

    Returns:
        Krotka (czy wystąpiły błędy, czy wystąpiły ostrzeżenia).
    """
    error_lines = re.findall(r"^ERROR.*", log_content, flags=re.MULTILINE)
    warning_lines: list[str] = []
    if report_warnings:
        warning_lines = re.findall(r"^WARNING.*", log_content, flags=re.MULTILINE)

    for line in error_lines:
        error(f"{line}")
    if report_warnings:
        for line in warning_lines:
            warn(f"{line}")

    return (bool(error_lines), bool(warning_lines))
