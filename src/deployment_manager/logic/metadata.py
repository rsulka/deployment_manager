"""Operacje związane z eksportem i importem metadanych SAS."""
from __future__ import annotations


import re
from invoke.exceptions import UnexpectedExit

from ..config import Config
from ..constants import (
    LOG_METADATA_EXPORT,
    LOG_METADATA_IMPORT,
    META_FILE_NAME,
    METADATA_SPK_NAME,
    METADATA_SUBPROP_NAME,
    SPKS_DIR_NAME,
    LOGS_DIR_NAME,
)
from ..logger import info, warn, error
from ..remote.ssh_executor import SSHExecutor, RemotePath, quote_shell

__all__ = ["export_metadata", "import_metadata"]

def _check_meta_logs(log_content: str) -> tuple[bool, bool]:
    """Analizuje treść logu exportu/importu w poszukiwaniu błędów i ostrzeżeń.

    Args:
        log_content: Treść logu do analizy.

    Returns:
        Krotka (czy wystąpiły błędy, czy wystąpiły ostrzeżenia).
    """
    error_lines = re.findall(r"^ERROR.*", log_content, flags=re.MULTILINE)
    warning_lines = re.findall(r"^WARN.*", log_content, flags=re.MULTILINE)
    for line in error_lines:
        error(f"{line}")
    for line in warning_lines:
        warn(f"{line}")

    return (len(error_lines) > 0, len(warning_lines) > 0)

def export_metadata(
    package_dir: RemotePath, config: Config, ssh_executor: SSHExecutor
) -> None:
    """Eksportuje metadane SAS do SPK wg definicji w meta.txt (jeśli istnieje).

    Args:
        package_dir: Ścieżka do katalogu pakietu.
        config: Obiekt konfiguracji.
        ssh_executor: Executor do wykonywania poleceń SSH.

    Raises:
        UnexpectedExit: Gdy eksport metadanych nie powiedzie się.
    """
    meta_file = package_dir / META_FILE_NAME
    if not ssh_executor.exists(meta_file):
        info(f"Plik {META_FILE_NAME} nie znaleziony. Pomijanie.")
        return

    try:
        meta_content = ssh_executor.read_file(meta_file)
    except OSError as exc:
        error(f"Nie udało się odczytać pliku {meta_file}: {exc}. Pomijanie eksportu.")
        return
    objects = [line.strip() for line in meta_content.splitlines() if line.strip()]
    if not objects:
        warn("Plik meta.txt jest pusty. Pomijanie eksportu.")
        return

    spk_dir = package_dir / SPKS_DIR_NAME
    log_dir = package_dir / LOGS_DIR_NAME
    export_tool = config.get("path_to_exportpackage")
    profile = config.get("dev_meta_profile")
    subprop_file = spk_dir / METADATA_SUBPROP_NAME
    spk_file = spk_dir / METADATA_SPK_NAME
    log_file = log_dir / LOG_METADATA_EXPORT

    command_parts = [
        quote_shell(str(export_tool)),
        "-disableX11",
        f"-profile {quote_shell(str(profile))}",
        f"-package {quote_shell(spk_file)}",
        f"-log {quote_shell(log_file)}",
        f"-subprop {quote_shell(subprop_file)}",
        "-objects",
        *[quote_shell(obj) for obj in sorted(objects)],
    ]
    command = " ".join(command_parts)

    try:
        ssh_executor.run_command(command)
        info("Zakończono eksport metadanych.")
    except UnexpectedExit:
        error(
            "Eksport metadanych nie powiódł się. "
            "Sprawdź logi na serwerze zdalnym."
        )
        raise

    log_content = ssh_executor.read_file(log_file)
    has_error, has_warn = _check_meta_logs(log_content)
    if has_error:
        error(f"Wykryto błąd podczas eksportu, sprawdź {log_file}")
    if has_warn:
        warn(f"Wykryto ostrzeżenia podczas eksportu, sprawdź {log_file}")


def import_metadata(
    package_dir: RemotePath, config: Config, ssh_executor: SSHExecutor
) -> None:
    """Importuje metadane z pakietu SPK (jeśli obecny) używając narzędzia importu.

    Args:
        package_dir: Ścieżka do katalogu pakietu.
        config: Obiekt konfiguracji.
        ssh_executor: Executor do wykonywania poleceń SSH.

    Raises:
        UnexpectedExit: Gdy import metadanych nie powiedzie się.
    """
    spk_file = package_dir / SPKS_DIR_NAME / METADATA_SPK_NAME
    if not ssh_executor.exists(spk_file):
        info("Plik SPK nie znaleziony. Pomijanie.")
        return
    import_tool = config.get("path_to_importpackage")
    profile = config.get("meta_profile")
    log_file = package_dir / LOGS_DIR_NAME / LOG_METADATA_IMPORT
    subprop_file = package_dir / SPKS_DIR_NAME / METADATA_SUBPROP_NAME
    command_parts = [
        quote_shell(str(import_tool)),
        "-disableX11",
        "-profile",
        quote_shell(str(profile)),
        "-target",
        quote_shell("/"),
        "-package",
        quote_shell(spk_file),
        "-subprop",
        quote_shell(subprop_file),
        "--includeACL",
        "-preservePaths",
        "-log",
        quote_shell(log_file),
    ]
    command = " ".join(command_parts)
    try:
        ssh_executor.run_command(command)
        info("Zakończono import metadanych.")
    except UnexpectedExit:
        error(
            "Import metadanych nie powiódł się. "
            "Sprawdź logi na serwerze zdalnym."
        )
        raise

    log_content = ssh_executor.read_file(log_file)
    has_error, has_warn = _check_meta_logs(log_content)
    if has_error:
        error(f"Wykryto błąd podczas importu, sprawdź {log_file}")
    if has_warn:
        warn(f"Wykryto ostrzeżenia podczas importu, sprawdź {log_file}")
