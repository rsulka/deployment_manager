"""Główny moduł aplikacji Deployment Manager."""
import argparse
from datetime import datetime
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, cast, Tuple, Optional, Union

from .bitbucket import BitbucketPlatform, create_platform
from .config import Config
from .constants import DEPLOY_DIR_PREFIX
from .logger import error, info, ok, setup_logging, step, warn
from .logic.pr_analysis import analyze_pull_requests, merge_local, merge_remote
from .logic.packaging import build_package
from .logic.metadata import export_metadata, import_metadata
from .logic.predeploy import run_predeploy_bash, run_predeploy_sas
from .logic.code_update import update_module_code
from .logic.dictionaries import update_dictionaries
from .logic.jobs import redeploy_jobs, report_deployed_flows
from .remote.ssh_executor import RemotePath, SSHExecutor

CONFIG_DIR_NAME = "configs"

# Type alias dla executora (prawdziwy lub mock)
SSHExecutorType = Union[SSHExecutor, "MockSSHExecutor"]  # type: ignore


def _run_step(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> None:
    """Uruchamia przekazaną funkcję i loguje powodzenie tylko jeśli nie wystąpił błąd.

    Args:
        func: Funkcja do wykonania.
        *args: Argumenty pozycyjne dla funkcji.
        **kwargs: Argumenty nazwane dla funkcji.
    """
    func(*args, **kwargs)
    ok("Krok zakończony pomyślnie")


def _parse_args() -> argparse.Namespace:
    """Parsuje argumenty wiersza poleceń.

    Returns:
        Sparsowane argumenty aplikacji.
    """
    parser = argparse.ArgumentParser(description="Deployment Manager.")
    parser.add_argument(
        "-r",
        "--repo",
        required=True,
        help="Nazwa repozytorium Bitbucket.",
    )
    parser.add_argument(
        "-e",
        "--env",
        required=True,
        choices=["DEV", "UAT", "PROD"],
        type=str.upper,
        help="Środowisko docelowe (DEV, UAT lub PROD).",
    )
    parser.add_argument(
        "--merge",
        "--mergo",
        action="store_true",
        help=(
            "Po udanym wdrożeniu na PROD scali (merge) wszystkie PR,"
            "które brały udział w wdrożeniu. "
            "Dla DEV/UAT parametr jest ignorowany z ostrzeżeniem."
        ),
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help=(
            "Tryb testowy - symuluje operacje bez połączenia z SAS, "
            "Bitbucket i SSH. Używa lokalnego systemu plików."
        ),
    )
    return parser.parse_args()


def _setup_env(
    config: Config,
) -> Tuple[SSHExecutor, RemotePath]:
    """Konfiguruje środowisko wykonawcze.

    Args:
        config: Obiekt konfiguracji.

    Returns:
        Krotka (executor SSH, ścieżka do katalogu roboczego).

    Raises:
        ValueError: Gdy DM_RUNTIME_BASE_DIR jest pusty lub nieprawidłowy.
    """
    ssh_user = cast(str, config.get("deploy_user"))
    ssh_host = cast(str, config.get("ssh_host"))
    ssh_executor = SSHExecutor(ssh_host, ssh_user)

    runtime_base_dir = cast(str, config.get("dm_runtime_base_dir"))
    runtime_base_dir_clean = runtime_base_dir.strip().rstrip("/")
    if not runtime_base_dir_clean:
        raise ValueError("Pusta wartość klucza DM_RUNTIME_BASE_DIR w konfiguracji.")
    if not runtime_base_dir_clean.startswith("/"):
        raise ValueError(
            "DM_RUNTIME_BASE_DIR musi być bezwzględną ścieżką (zaczynać się od '/')."
        )

    setup_logging()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_work_dir = RemotePath(
        f"{runtime_base_dir_clean}/{DEPLOY_DIR_PREFIX}" f"{timestamp}_{uuid.uuid4()}"
    )
    info(
        f"Tworzenie zdalnego katalogu roboczego: "
        f"{ssh_user}@{ssh_host}:{remote_work_dir}"
    )
    ssh_executor.mkdir(remote_work_dir)
    return ssh_executor, remote_work_dir


def _setup_mock_env() -> Tuple["MockSSHExecutor", RemotePath]:  # type: ignore
    """Konfiguruje mockowe środowisko wykonawcze.

    Returns:
        Krotka (mockowy executor SSH, ścieżka do katalogu roboczego).
    """
    from .mock import MockSSHExecutor

    setup_logging()
    info("[MOCK] Uruchamianie w trybie testowym")

    # Tworzymy tymczasowy katalog lokalny
    mock_base = Path(tempfile.gettempdir()) / "dm_mock"
    mock_base.mkdir(parents=True, exist_ok=True)

    ssh_executor = MockSSHExecutor(mock_base)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_work_dir = RemotePath(
        f"/mock_runtime/{DEPLOY_DIR_PREFIX}{timestamp}_{uuid.uuid4()}"
    )
    info(f"[MOCK] Katalog roboczy: {remote_work_dir}")
    ssh_executor.mkdir(remote_work_dir)
    return ssh_executor, remote_work_dir


def _run_deployment_steps(
    args: argparse.Namespace,
    config: Config,
    ssh_executor: SSHExecutorType,
    remote_work_dir: RemotePath,
    mock_mode: bool = False,
) -> None:
    """Wywołuje kroki wdrożenia.

    Args:
        args: Sparsowane argumenty wiersza poleceń.
        config: Obiekt konfiguracji.
        ssh_executor: Executor SSH (prawdziwy lub mock).
        remote_work_dir: Ścieżka do katalogu roboczego.
        mock_mode: Czy uruchamiać w trybie mock.
    """
    if mock_mode:
        from .mock import MockBitbucketPlatform, get_mock_pull_requests

        bitbucket_platform: BitbucketPlatform = MockBitbucketPlatform(args.repo)
        prs = get_mock_pull_requests()
        # Filtruj wg wymaganych akceptacji
        required = cast(int, config.get("approvals", 0))
        if required > 0:
            prs = [pr for pr in prs if pr.approval_count >= required]
    else:
        bitbucket_platform = create_platform(config, args.repo)
        prs = analyze_pull_requests(
            platform=bitbucket_platform,
            required_approvals=cast(int, config.get("approvals")),
        )
    changed_files, merged_locally = merge_local(
        platform=bitbucket_platform,
        ssh_executor=ssh_executor,
        remote_work_dir=remote_work_dir,
        git_executable=cast(str, config.get("remote_git_path")),
        pull_requests=prs,
    )

    if not changed_files:
        info("Brak zmian do wdrożenia.")
        return

    build_package(
        ssh_executor=ssh_executor,
        remote_work_dir=remote_work_dir,
        changed_files=changed_files,
    )
    package_dir = remote_work_dir

    step("Wykonywanie pre_deploy.sh")
    _run_step(run_predeploy_bash, package_dir=package_dir, ssh_executor=ssh_executor)

    step("Wdrażanie kodu modułu")
    _run_step(
        update_module_code,
        package_dir=package_dir,
        env=args.env,
        repo=args.repo,
        ssh_executor=ssh_executor,
    )

    step("Importowanie słowników MDS")
    if mock_mode:
        info("[MOCK] Pomijanie aktualizacji słowników MDS (wymaga SAS)")
        ok("Krok pominięty")
    else:
        _run_step(update_dictionaries, package_dir=package_dir, env=args.env, ssh_executor=ssh_executor)

    step("Wykonywanie pre_deploy.sas")
    if mock_mode:
        info("[MOCK] Pomijanie pre_deploy.sas (wymaga SAS)")
        ok("Krok pominięty")
    else:
        _run_step(run_predeploy_sas, package_dir=package_dir, env=args.env, ssh_executor=ssh_executor)

    step("Eksportowanie metadanych")
    _run_step(export_metadata, package_dir=package_dir, config=config, ssh_executor=ssh_executor)

    step("Importowanie metadanych")
    _run_step(import_metadata, package_dir=package_dir, config=config, ssh_executor=ssh_executor)

    step("Redeployowanie jobów")
    _run_step(redeploy_jobs, package_dir=package_dir, config=config, ssh_executor=ssh_executor)

    report_deployed_flows(remote_work_dir=package_dir, ssh_executor=ssh_executor)

    if args.merge:
        if mock_mode:
            info("[MOCK] Pomijanie merge PR (tryb mock)")
        elif args.env != "PROD":
            warn("Parametr --merge jest dostępny tylko dla PROD i zostanie zignorowany.")
        elif not merged_locally:
            info("Brak pull requestów do scalenia po wdrożeniu.")
        else:
            step("Scalanie pull requestów w Bitbucket po wdrożeniu")
            platform = create_platform(config, args.repo)
            _run_step(merge_remote, platform, merged_locally)


def main() -> None:
    """Główna funkcja wykonująca wszystkie kroki"""
    args = _parse_args()
    mock_mode = args.mock

    remote_work_dir: Optional[RemotePath] = None
    success = False

    try:
        if mock_mode:
            # Tryb mock - nie wymaga konfiguracji
            from .mock import MockSSHExecutor

            setup_logging()
            info("="*60)
            info("[MOCK] TRYB TESTOWY - operacje są symulowane")
            info("="*60)

            mock_base = Path(tempfile.gettempdir()) / "dm_mock"
            ssh_executor: SSHExecutorType = MockSSHExecutor(mock_base)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            remote_work_dir = RemotePath(
                f"/mock_runtime/{DEPLOY_DIR_PREFIX}{timestamp}_{uuid.uuid4()}"
            )
            ssh_executor.mkdir(remote_work_dir)

            # Mockowa konfiguracja
            from unittest.mock import MagicMock
            config = MagicMock()
            config.get = lambda key, default=None: {
                "approvals": 0,
                "remote_git_path": "git",
            }.get(key, default or "mock_value")
        else:
            config_path = Path(__file__).resolve().parents[2] / CONFIG_DIR_NAME
            config = Config(config_path, args.env)
            ssh_executor, remote_work_dir = _setup_env(config)

        _run_deployment_steps(args, config, ssh_executor, remote_work_dir, mock_mode=mock_mode)
        success = True
    except Exception as exc:  # pylint: disable=broad-except
        error(f"Wystąpił błąd: {exc}")
    finally:
        if success:
            info("Wdrożenie zakończone pomyślnie")
        else:
            error("Wdrożenie zakończone niepowodzeniem")
        if remote_work_dir is not None:
            if mock_mode:
                mock_local_path = Path(tempfile.gettempdir()) / "dm_mock" / str(remote_work_dir).lstrip("/")
                info(f"[MOCK] Wyniki znajdują się w katalogu: {mock_local_path}")
            else:
                info(f"Wyniki znajdują się w katalogu: {remote_work_dir}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
