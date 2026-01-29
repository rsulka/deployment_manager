"""Budowanie pakietu wdrożeniowego: struktura katalogów i kopiowanie / łączenie plików."""
from __future__ import annotations

import re
from pathlib import Path

from ..constants import (
    CODES_DIR_NAME,
    EXTRA_FILES_DIR_NAME,
    LOGS_DIR_NAME,
    PRE_DEPLOY_BASH_SCRIPT_NAME,
    PRE_DEPLOY_SCRIPT_NAME,
    REPO_CODES_DIR_NAME,
    REMOTE_REPO_DIR_NAME,
    SPKS_DIR_NAME,
)
from ..logger import info, list_block
from ..remote.ssh_executor import RemotePath, SSHExecutor, quote_shell

__all__ = ["build_package"]


def _prepare_package_dirs(ssh_executor: SSHExecutor, package_dir: RemotePath) -> None:
    """Tworzy strukturę katalogów pakietu wdrożeniowego na serwerze.

    Args:
        ssh_executor: Executor do wykonywania poleceń SSH.
        package_dir: Ścieżka do katalogu pakietu.
    """
    info("Przygotowywanie struktury katalogów.")
    dirs = {
        "codes": package_dir / CODES_DIR_NAME,
        "extra_files": package_dir / CODES_DIR_NAME / EXTRA_FILES_DIR_NAME,
        "spks": package_dir / SPKS_DIR_NAME,
        "logs": package_dir / LOGS_DIR_NAME,
    }
    for d in dirs.values():
        ssh_executor.mkdir(RemotePath(d))
    info("Struktura katalogów została utworzona.")


def _copy_repo_codes_dir(
    remote_repo_dir: RemotePath, remote_codes_dir: RemotePath
) -> str:
    """Zwraca komendę kopiowania katalogu z kodami repozytorium.

    Args:
        remote_repo_dir: Ścieżka do katalogu repozytorium.
        remote_codes_dir: Ścieżka do docelowego katalogu kodów.

    Returns:
        Komenda shell do wykonania.
    """
    source_kody_dir = remote_repo_dir / REPO_CODES_DIR_NAME
    return (
        f"if [ -d {quote_shell(source_kody_dir)} ]; "
        f"then cp -r {quote_shell(source_kody_dir)} {quote_shell(remote_codes_dir)}/; fi"
    )


def _copy_extra_files(
    changed_files: set[str],
    remote_repo_dir: RemotePath,
    remote_extra_files_dir: RemotePath,
) -> tuple[list[str], set[str]]:
    """Przygotowuje komendy kopiowania dodatkowych plików i zwraca listę skopiowanych.

    Args:
        changed_files: Zbiór ścieżek zmienionych plików.
        remote_repo_dir: Ścieżka do katalogu repozytorium.
        remote_extra_files_dir: Ścieżka do katalogu plików dodatkowych.

    Returns:
        Krotka (lista komend kopiowania, zbiór skopiowanych plików).
    """
    script_commands: list[str] = []
    extra_files_to_copy = {
        f for f in changed_files if f.startswith(f"{EXTRA_FILES_DIR_NAME}/")
    }

    if not extra_files_to_copy:
        info("Brak zmienionych plików w 'dodatkowe_pliki' do przetworzenia.")
        return [], set()

    info(
        f"Kopiowanie {len(extra_files_to_copy)} zmienionych plików z "
        f"'{EXTRA_FILES_DIR_NAME}'."
    )
    for file_path_str in extra_files_to_copy:
        file_path = Path(file_path_str)
        source = remote_repo_dir / file_path_str
        destination = remote_extra_files_dir / file_path.name
        script_commands.append(f"cp {quote_shell(source)} {quote_shell(destination)}")

    return script_commands, extra_files_to_copy


def _get_files_to_merge(
    extra_files_to_copy: set[str], remote_extra_files_dir: RemotePath
) -> dict[str, list[RemotePath]]:
    """Identyfikuje pliki do scalenia na podstawie wzorca nazwy.

    Args:
        extra_files_to_copy: Zbiór ścieżek plików do skopiowania.
        remote_extra_files_dir: Ścieżka do katalogu plików dodatkowych.

    Returns:
        Słownik mapujący nazwy docelowe na listy plików do scalenia.
    """
    files_to_merge: dict[str, list[RemotePath]] = {}
    merge_pattern = re.compile(r"^CRISPR-\d+_(.*)")

    for file_path_str in extra_files_to_copy:
        filename = Path(file_path_str).name
        match = merge_pattern.match(filename)
        if match:
            target_name = match.group(1)
            files_to_merge.setdefault(target_name, []).append(
                remote_extra_files_dir / filename
            )
    return files_to_merge


def _get_merge_commands(
    files_to_merge: dict[str, list[RemotePath]], remote_work_dir: RemotePath
) -> list[str]:
    """Generuje komendy bash do scalenia plików.

    Args:
        files_to_merge: Słownik plików do scalenia.
        remote_work_dir: Ścieżka do katalogu roboczego.

    Returns:
        Lista komend shell do wykonania.
    """
    script_commands: list[str] = []
    if not files_to_merge:
        info(
            "Nie znaleziono plików pasujących do wzorca łączenia "
            "(np. CRISPR-123_meta.txt)."
        )
        return []

    info("Przygotowywanie poleceń łączenia plików.")
    for target_name, source_files in files_to_merge.items():
        ordered_sources = sorted(source_files, key=str)
        target_file = remote_work_dir / target_name
        list_block(f"Łączenie do {target_file}:", [str(f) for f in ordered_sources])

        target_q = quote_shell(target_file)
        cats = " ".join(
            f"cat {quote_shell(src)}; printf '\\n';" for src in ordered_sources
        )

        if target_name == PRE_DEPLOY_SCRIPT_NAME:
            line_to_add = r"%let srodowisko = %sysget(srodowisko);"
            cmd = (
                "{ "
                + "printf '%s\\n' "
                + quote_shell(line_to_add)
                + "; "
                + cats
                + f" }} > {target_q}"
            )
            script_commands.append(cmd)
        elif target_name == PRE_DEPLOY_BASH_SCRIPT_NAME:
            cmd_build = (
                "{ "
                "printf '%s\\n' '#!/bin/bash'; "
                "printf '%s\\n' 'set -euo pipefail'; "
                + cats
                + f" }} > {target_q}"
            )
            script_commands.append(cmd_build)
            script_commands.append(f"chmod +x {target_q}")
        else:
            cmd = "{ " + cats + f" }} > {target_q}"
            script_commands.append(cmd)
    return script_commands


def _copy_and_merge_files(
    ssh_executor: SSHExecutor, changed_files: set[str], remote_work_dir: RemotePath
) -> None:
    """Kopiuje zmienione pliki i scala pliki CRISPR-*_*.txt do docelowych nazw.

    Args:
        ssh_executor: Executor do wykonywania poleceń SSH.
        changed_files: Zbiór ścieżek zmienionych plików.
        remote_work_dir: Ścieżka do katalogu roboczego.
    """
    remote_repo_dir = remote_work_dir / REMOTE_REPO_DIR_NAME
    remote_codes_dir = remote_work_dir / CODES_DIR_NAME
    remote_extra_files_dir = remote_codes_dir / EXTRA_FILES_DIR_NAME

    all_commands: list[str] = []

    all_commands.append(_copy_repo_codes_dir(remote_repo_dir, remote_codes_dir))

    copy_commands, copied_files = _copy_extra_files(
        changed_files, remote_repo_dir, remote_extra_files_dir
    )
    all_commands.extend(copy_commands)

    files_to_merge = _get_files_to_merge(copied_files, remote_extra_files_dir)
    merge_commands = _get_merge_commands(files_to_merge, remote_work_dir)
    all_commands.extend(merge_commands)

    if all_commands:
        for cmd in all_commands:
            ssh_executor.run_command(cmd)
        info("Pliki zostały pomyślnie skopiowane i połączone.")


def build_package(
    changed_files: set[str], ssh_executor: SSHExecutor, remote_work_dir: RemotePath
) -> None:
    """Buduje pakiet wdrożeniowy (struktura + kopiowanie/łączenie plików).

    Args:
        changed_files: Zbiór ścieżek zmienionych plików.
        ssh_executor: Executor do wykonywania poleceń SSH.
        remote_work_dir: Ścieżka do katalogu roboczego.
    """
    info(f"Tworzenie struktury wdrożeniowej: {remote_work_dir}.")
    _prepare_package_dirs(ssh_executor, remote_work_dir)
    _copy_and_merge_files(ssh_executor, changed_files, remote_work_dir)
