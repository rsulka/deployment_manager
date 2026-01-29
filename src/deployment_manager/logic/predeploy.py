"""Operacje pre_deploy: uruchamianie skryptów bash oraz SAS."""
from __future__ import annotations

from invoke.exceptions import UnexpectedExit

from ..constants import (
    LOG_PRE_DEPLOY_BASH,
    LOG_PRE_DEPLOY_SAS,
    LOGS_DIR_NAME,
    PRE_DEPLOY_BASH_SCRIPT_NAME,
    PRE_DEPLOY_SCRIPT_NAME,
)
from ..logger import info, error
from ..remote.sas_session import open_sas_session, submit_sas_code
from ..remote.ssh_executor import SSHExecutor, RemotePath, quote_shell

__all__ = ["run_predeploy_bash", "run_predeploy_sas"]


def run_predeploy_bash(package_dir: RemotePath, ssh_executor: SSHExecutor) -> None:
    """Uruchamia pre_deploy.sh (jeśli istnieje) i zapisuje log.

    Args:
        package_dir: Ścieżka do katalogu pakietu.
        ssh_executor: Executor do wykonywania poleceń SSH.

    Raises:
        UnexpectedExit: Gdy wykonanie skryptu nie powiedzie się.
    """
    script_path = package_dir / PRE_DEPLOY_BASH_SCRIPT_NAME
    log_file_full = package_dir / LOGS_DIR_NAME / LOG_PRE_DEPLOY_BASH
    if not ssh_executor.exists(script_path):
        info(f"Skrypt {PRE_DEPLOY_BASH_SCRIPT_NAME} nie znaleziony. Pomijanie.")
        return
    try:
        command = " ".join([
            f"./{PRE_DEPLOY_BASH_SCRIPT_NAME}",
            ">",
            quote_shell(str(log_file_full)),
            "2>&1",
        ])
        ssh_executor.run_command(command, cwd=package_dir)
        info("Zakończono wykonanie skryptu pre_deploy.sh.")
    except UnexpectedExit:
        error(
            f"Wykonanie skryptu pre_deploy.sh nie powiodło się. Log: {log_file_full}."
        )
        raise


def run_predeploy_sas(
    package_dir: RemotePath, env: str, ssh_executor: SSHExecutor
) -> None:
    """Uruchamia pre_deploy.sas przez saspy ustawiając &srodowisko.

    Args:
        package_dir: Ścieżka do katalogu pakietu.
        env: Nazwa środowiska (np. 'dev', 'prod').
        ssh_executor: Executor do wykonywania poleceń SSH.

    Raises:
        Exception: Gdy wykonanie skryptu SAS nie powiedzie się.
    """
    pre_deploy_script = package_dir / PRE_DEPLOY_SCRIPT_NAME
    if not ssh_executor.exists(pre_deploy_script):
        info(f"Skrypt {PRE_DEPLOY_SCRIPT_NAME} nie znaleziony. Pomijanie.")
        return
    log_file = package_dir / LOGS_DIR_NAME / LOG_PRE_DEPLOY_SAS
    try:
        with open_sas_session(env) as sas_session:
            script_content = ssh_executor.read_file(pre_deploy_script)
            full_sas_code = f"%let srodowisko = {env};\n{script_content}"
            info("Wykonywanie skryptu SAS")
            submit_sas_code(
                sas_session=sas_session,
                ssh_executor=ssh_executor,
                sas_code=full_sas_code,
                log_file=log_file,
            )
    except Exception as exc:
        error(
            "Wykonanie skryptu SAS nie powiodło się. "
            "Sprawdź logi na zdalnym serwerze. "
            f"Szczegóły: {exc}."
        )
        raise
