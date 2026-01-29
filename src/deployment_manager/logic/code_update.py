"""Aktualizacja kodu modułu w lokalizacji wskazanej przez MDS.MODULY."""
from __future__ import annotations

from typing import Optional, cast

from ..constants import CODES_DIR_NAME, REPO_CODES_DIR_NAME, LOGS_DIR_NAME
from ..logger import error, info
from ..remote.sas_session import open_sas_session, submit_sas_code
from ..remote.ssh_executor import RemotePath, SSHExecutor, quote_shell

__all__ = ["update_module_code"]


def _get_module_path_from_sas(
    package_dir: RemotePath,
    env: str,
    repo: str,
    ssh_executor: SSHExecutor,
) -> str:
    """Pobiera i waliduje ścieżkę modułu z tabeli MDS.MODULY.

    Args:
        package_dir: Ścieżka do katalogu pakietu na serwerze zdalnym.
        env: Nazwa środowiska (np. 'dev', 'prod').
        repo: Nazwa repozytorium/modułu.
        ssh_executor: Executor do wykonywania poleceń SSH.

    Returns:
        Ścieżka do modułu odczytana z tabeli MDS.MODULY.

    Raises:
        RuntimeError: Gdy ścieżka nie jest skonfigurowana w tabeli.
        ValueError: Gdy odczytana ścieżka jest pusta.
    """
    try:
        with open_sas_session(env) as sas_session:
            repo_lower = repo.lower()
            sas_code = f"""
                data _null_;
                    set MDS.MODULY(where=(lowcase(MODUL) = '{repo_lower}'));
                    call symputx('sciezka', trim(SCIEZKA_DO_MODULU));
                    stop;
                run;
            """
            log_file = package_dir / LOGS_DIR_NAME / "get_module_path.log"
            info("Wykonywanie zapytania SAS o ścieżkę modułu")
            submit_sas_code(
                sas_session=sas_session,
                ssh_executor=ssh_executor,
                sas_code=sas_code,
                log_file=log_file,
            )

            raw_value = cast(Optional[str], sas_session.symget("sciezka"))  # type: ignore
            if raw_value is None:
                raise RuntimeError(
                    f"Brak skonfigurowanej ścieżki dla modułu {repo} "
                    "w tabeli MDS.MODULY."
                )
            cleaned_path = raw_value.strip()
            if not cleaned_path:
                raise ValueError(
                    f"Pusta ścieżka modułu {repo} pobrana z MDS.MODULY."
                )

            info(f"Pobrana ścieżka docelowa: {cleaned_path}")
            return cleaned_path
    except Exception as exc:
        error(f"Nie udało się pobrać ścieżki modułu. Szczegóły: {exc}.")
        raise


def update_module_code(
    package_dir: RemotePath,
    env: str,
    repo: str,
    ssh_executor: SSHExecutor,
) -> None:
    """Aktualizuje katalog kodu modułu według ścieżki z tabeli MDS.MODULY.

    Args:
        package_dir: Ścieżka do katalogu pakietu na serwerze zdalnym.
        env: Nazwa środowiska (np. 'dev', 'prod').
        repo: Nazwa repozytorium/modułu.
        ssh_executor: Executor do wykonywania poleceń SSH.
    """
    target_path_str = _get_module_path_from_sas(package_dir, env, repo, ssh_executor)

    source_dir = package_dir / CODES_DIR_NAME / REPO_CODES_DIR_NAME
    if not ssh_executor.exists(source_dir):
        info(
            f"Katalog źródłowy {source_dir} nie istnieje. "
            "Pomijanie wdrażania kodu modułu."
        )
        return

    target_path = RemotePath(target_path_str)
    target_codes_dir = target_path / REPO_CODES_DIR_NAME

    info(f"Usuwanie istniejącego katalogu '{target_codes_dir}'.")
    ssh_executor.rmdir(target_codes_dir)

    info(f"Kopiowanie '{source_dir}' do '{target_path}'.")
    ssh_executor.run_command(
        f"cp -r {quote_shell(str(source_dir))} {quote_shell(str(target_path))}"
    )
    info("Zakończono wdrażanie kodu modułu.")
