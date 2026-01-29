"""Wdrażanie (redeploy) jobów."""
from __future__ import annotations

import re

from invoke.exceptions import UnexpectedExit

from ..config import Config
from ..remote.ssh_executor import RemotePath, SSHExecutor, quote_shell
from ..constants import (
    JOBS_TO_REDEPLOY_FILENAME,
    LOGS_DIR_NAME,
    LOG_REDEPLOY_JOBS,
    META_FILE_NAME,
)
from ..logger import info, warn, error, list_block

__all__ = ["redeploy_jobs", "report_deployed_flows"]


def _get_job_names_from_meta_file(
    ssh_executor: SSHExecutor, meta_file: RemotePath
) -> set[str]:
    """Odczytuje i parsuje nazwy jobów z pliku meta.txt.

    Args:
        ssh_executor: Executor do wykonywania poleceń SSH.
        meta_file: Ścieżka do pliku meta.txt.

    Returns:
        Zbiór nazw jobów znalezionych w pliku.
    """
    if not ssh_executor.exists(meta_file):
        info(f"Plik {META_FILE_NAME} nie znaleziony. Pomijanie.")
        return set()
    try:
        content = ssh_executor.read_file(meta_file)
    except OSError:
        error(f"Nie udało się odczytać pliku {meta_file}. Pomijanie redeployu jobów.")
        return set()

    job_line_pattern = re.compile(r"^(.+?)\s*\(\s*Job\s*\)\s*$")
    job_names: set[str] = set()
    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        m = job_line_pattern.match(line)
        if m:
            job = m.group(1).strip()
            job_names.add(job)

    if job_names:
        list_block("Znalezione joby do redeployu", sorted(job_names))

    return job_names


def _write_jobs_to_redeploy_file(
    ssh_executor: SSHExecutor, jobs_file: RemotePath, job_names: set[str]
) -> None:
    """Zapisuje nazwy jobów do pliku na serwerze zdalnym.

    Args:
        ssh_executor: Executor do wykonywania poleceń SSH.
        jobs_file: Ścieżka do pliku wyjściowego.
        job_names: Zbiór nazw jobów do zapisania.
    """
    jobs_content = "\n".join(sorted(job_names)) + "\n"
    ssh_executor.write_file(jobs_file, jobs_content)
    info(f"Zapisano listę jobów ({len(job_names)}) do: {jobs_file}")


def _get_redeploy_config(config: Config) -> dict[str, str] | None:
    """Pobiera i weryfikuje konfigurację potrzebną do wdrożenia.

    Args:
        config: Obiekt konfiguracji.

    Returns:
        Słownik z konfiguracją redeployu lub None gdy brakuje wymaganych kluczy.
    """
    config_keys = [
        "path_to_deployjobs",
        "meta_profile",
        "meta_repo",
        "appserver",
        "server_machine",
        "server_port",
        "deployed_jobs_dir",
        "batch_server",
        "display",
    ]

    missing: list[str] = []
    redeploy_config: dict[str, str] = {}

    for key in config_keys:
        val = config.get(key)
        if not val:
            missing.append(key)
        else:
            str_val = str(val)
            redeploy_config[key] = str_val.strip('\'"') if key == "batch_server" else str_val

    if missing:
        warn(
            f"Brak wymaganych zmiennych konfiguracyjnych: {', '.join(missing)}. "
            "Pomijam redeploy jobów."
        )
        return None

    return redeploy_config


def _build_redeploy_command(
    redeploy_config: dict[str, str], job_names: set[str], log_file: RemotePath
) -> str:
    """Buduje polecenie powłoki na podstawie konfiguracji i listy jobów.

    Args:
        redeploy_config: Słownik z konfiguracją redeployu.
        job_names: Zbiór nazw jobów do wdrożenia.
        log_file: Ścieżka do pliku logu.

    Returns:
        Gotowe polecenie powłoki do wykonania.
    """
    command_parts: list[str] = [
        f"export DISPLAY={quote_shell(redeploy_config['display'])};",
        quote_shell(redeploy_config["path_to_deployjobs"]),
        "-deploytype REDEPLOY",
        f"-profile {quote_shell(redeploy_config['meta_profile'])}",
        f"-metarepository {quote_shell(redeploy_config['meta_repo'])}",
        f"-appservername {quote_shell(redeploy_config['appserver'])}",
        f"-servermachine {quote_shell(redeploy_config['server_machine'])}",
        f"-serverport {quote_shell(redeploy_config['server_port'])}",
        f"-batchserver {quote_shell(redeploy_config['batch_server'])}",
        f"-sourcedir {quote_shell(redeploy_config['deployed_jobs_dir'])}",
        f"-deploymentdir {quote_shell(redeploy_config['deployed_jobs_dir'])}",
        f"-log {quote_shell(str(log_file))}",
        "-objects",
    ]

    command_parts.extend(quote_shell(name) for name in sorted(job_names))

    return " ".join(command_parts)


def redeploy_jobs(
    package_dir: RemotePath, config: Config, ssh_executor: SSHExecutor
) -> None:
    """Redeployuje joby zdefiniowane w meta.txt.

    Args:
        package_dir: Ścieżka do katalogu pakietu.
        config: Obiekt konfiguracji.
        ssh_executor: Executor do wykonywania poleceń SSH.

    Raises:
        UnexpectedExit: Gdy polecenie redeployu zakończy się błędem.
    """
    meta_file = package_dir / META_FILE_NAME
    job_names = _get_job_names_from_meta_file(ssh_executor, meta_file)
    if not job_names:
        return

    jobs_file = package_dir / JOBS_TO_REDEPLOY_FILENAME
    _write_jobs_to_redeploy_file(ssh_executor, jobs_file, job_names)

    redeploy_config = _get_redeploy_config(config)
    if not redeploy_config:
        return

    info(f"Ustawianie DISPLAY na {redeploy_config['display']} dla redeployu jobów")

    log_file = package_dir / LOGS_DIR_NAME / LOG_REDEPLOY_JOBS
    command = _build_redeploy_command(redeploy_config, job_names, log_file)

    try:
        info("Uruchamianie polecenia redeployu jobów")
        ssh_executor.run_command(command)
        info("Zakończono redeploy jobów.")
    except UnexpectedExit:
        error(
            f"Redeploy jobów nie powiódł się. Sprawdź log: {log_file} "
            "na serwerze zdalnym."
        )
        raise


def report_deployed_flows(remote_work_dir: RemotePath, ssh_executor: SSHExecutor) -> None:
    """Wyszukuje wpisy (DeployedFlow) w meta.txt i wypisuje notkę informacyjną.

    Args:
        remote_work_dir: Ścieżka do katalogu roboczego na serwerze.
        ssh_executor: Executor do wykonywania poleceń SSH.
    """
    meta_file = remote_work_dir / META_FILE_NAME
    if not ssh_executor.exists(meta_file):
        return
    try:
        content = ssh_executor.read_file(meta_file)
    except OSError:
        return

    pattern = re.compile(r"^(.+?)\s*\(\s*DeployedFlow\s*\)\s*$")
    flows: set[str] = set()
    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if match:
            full_path = match.group(1).strip()
            flows.add(full_path.rsplit("/", 1)[-1])

    if flows:
        list_block("Następujące flowy zostały zmienione", sorted(flows))
        warn("Upewnij się, że prawidłowe wersje znajdują się na serwerze LSF.")
