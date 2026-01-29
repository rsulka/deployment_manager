"""Aktualizacja słowników MDS na środowiskach innych niż DEV."""
from __future__ import annotations

import re
from typing import Final

from invoke.exceptions import UnexpectedExit

from ..remote.ssh_executor import RemotePath, SSHExecutor, quote_shell
from ..remote.sas_session import open_sas_session, submit_sas_code
from ..constants import (
    CODES_DIR_NAME,
    EXTRA_FILES_DIR_NAME,
    LOGS_DIR_NAME,
    LOG_UPDATE_DICTIONARIES,
)
from ..logger import info, warn, error, list_block

__all__ = ["update_dictionaries"]

_MDS_FILE_PATTERN: Final[re.Pattern[str]] = re.compile(r"(CRISPR-\d+)_mds\.txt")


def _get_mds_files(
    ssh_executor: SSHExecutor, extra_files_dir: RemotePath
) -> list[str] | None:
    """Zwraca listę plików _mds.txt w podanym katalogu.

    Args:
        ssh_executor: Executor do wykonywania poleceń SSH.
        extra_files_dir: Ścieżka do katalogu z plikami dodatkowymi.

    Returns:
        Lista nazw plików _mds.txt lub None gdy katalog nie istnieje.
    """
    if not ssh_executor.exists(extra_files_dir):
        info(
            f"Katalog {extra_files_dir} nie istnieje. "
            "Pomijanie aktualizacji słowników MDS."
        )
        return None
    try:
        ls_output = ssh_executor.run_command(
            f"ls -1 {quote_shell(str(extra_files_dir))}"
        )
        all_files = ls_output.stdout.strip().split("\n")
        return [f for f in all_files if _MDS_FILE_PATTERN.match(f)]
    except UnexpectedExit:
        warn(f"Nie udało się wylistować plików w {extra_files_dir}. Pomijanie.")
        return None


def _generate_sas_calls(
    ssh_executor: SSHExecutor,
    mds_files: list[str],
    extra_files_dir: RemotePath,
    env: str,
) -> list[str]:
    """Generuje wywołania makr SAS na podstawie plików _mds.txt.

    Args:
        ssh_executor: Executor do wykonywania poleceń SSH.
        mds_files: Lista nazw plików _mds.txt.
        extra_files_dir: Ścieżka do katalogu z plikami.
        env: Nazwa środowiska docelowego.

    Returns:
        Lista wywołań makr SAS.
    """
    sas_calls: list[str] = []

    for filename in mds_files:
        match = _MDS_FILE_PATTERN.match(filename)
        if not match:
            continue
        task_id = match.group(1)
        file_path = extra_files_dir / filename
        info(f"Przetwarzanie pliku: {filename}")
        try:
            content = ssh_executor.read_file(file_path)
        except OSError as exc:
            error(f"Nie udało się odczytać pliku {file_path}: {exc}. Pomijanie.")
            continue
        dictionaries = [line.strip() for line in content.split("\n") if line.strip()]
        if not dictionaries:
            info("  - Plik pusty, pomijanie.")
            continue
        for dictionary in dictionaries:
            call = (
                f"%usr_zaktualizuj_slownik(slownik={dictionary}, id_zadania={task_id}, "
                f"srodowisko_docelowe={env});"
            )
            sas_calls.append(call)
    list_block("Wywołania makr SAS do wykonania:", sas_calls)
    return sas_calls


def update_dictionaries(
    package_dir: RemotePath, env: str, ssh_executor: SSHExecutor
) -> None:
    """Aktualizuje słowniki MDS według plików CRISPR-*_mds.txt (poza DEV).

    Args:
        package_dir: Ścieżka do katalogu pakietu.
        env: Nazwa środowiska (np. 'dev', 'prod').
        ssh_executor: Executor do wykonywania poleceń SSH.

    Raises:
        RuntimeError: Gdy wystąpi błąd podczas aktualizacji słowników.
        OSError: Gdy wystąpi błąd operacji plikowej.
    """
    if env == "DEV":
        info("Środowisko MDS DEV. Pomijanie.")
        return

    extra_files_dir = package_dir / CODES_DIR_NAME / EXTRA_FILES_DIR_NAME
    mds_files = _get_mds_files(ssh_executor, extra_files_dir)

    if not mds_files:
        info("Brak plików _mds.txt do przetworzenia.")
        return

    sas_calls = _generate_sas_calls(ssh_executor, mds_files, extra_files_dir, env)

    if not sas_calls:
        info("Nie wygenerowano wywołania makra.")
        return

    full_sas_code = "\n".join(sas_calls)
    log_file = package_dir / LOGS_DIR_NAME / LOG_UPDATE_DICTIONARIES
    try:
        with open_sas_session(env) as sas_session:
            info("Wykonywanie skryptu aktualizacji słowników MDS")
            submit_sas_code(
                sas_session=sas_session,
                ssh_executor=ssh_executor,
                sas_code=full_sas_code,
                log_file=log_file,
            )
    except (RuntimeError, OSError) as e:
        error(f"Wystąpił błąd podczas aktualizacji słowników MDS: {e}")
        raise
