"""Analiza i scalanie pull requestów oraz zbieranie zmienionych plików."""
from __future__ import annotations

from invoke.exceptions import UnexpectedExit

from ..bitbucket import BitbucketPlatform, get_pull_requests, PullRequest
from ..constants import REMOTE_REPO_DIR_NAME
from ..logger import info, warn, error, list_block
from ..remote.ssh_executor import SSHExecutor, RemotePath, quote_shell

__all__ = ["analyze_pull_requests", "merge_local", "merge_remote"]


def merge_remote(platform: BitbucketPlatform, prs: list[PullRequest]) -> None:
    """Scala podane PRy w Bitbucket.

    Args:
        platform: Obiekt platformy Bitbucket.
        prs: Lista obiektów PullRequest do scalenia.

    Raises:
        RuntimeError: Gdy scalenie któregokolwiek PR nie powiedzie się.
    """
    if not prs:
        info("Brak pull requestów do scalenia w Bitbucket.")
        return

    info(f"Scalanie {len(prs)} PR w Bitbucket.")

    for pr in sorted(prs):
        info(f"Scalanie PR #{pr.id}: {pr.title}")
        ok_flag, reason = platform.merge_pull_request(pr)
        if ok_flag:
            info(f"PR #{pr.id} został scalony w Bitbucket.")
        else:
            raise RuntimeError(f"Nie udało się scalić PR #{pr.id}: {reason}")
    info("Zakończono scalanie PR.")


def _clone_repo(
    platform: BitbucketPlatform,
    ssh_executor: SSHExecutor,
    remote_work_dir: RemotePath,
    git_executable: str,
) -> None:
    """Klonuje repozytorium do katalogu roboczego na serwerze zdalnym.

    Args:
        platform: Obiekt platformy Bitbucket.
        ssh_executor: Executor do wykonywania poleceń SSH.
        remote_work_dir: Ścieżka do katalogu roboczego na serwerze.
        git_executable: Ścieżka do pliku wykonywalnego git.
    """
    info("Klonowanie repozytorium na serwerze zdalnym.")
    clone_url = platform.get_clone_url()
    clone_cmd = " ".join([
        f"{git_executable}",
        "clone",
        "--branch",
        "master",
        quote_shell(clone_url),
        quote_shell(REMOTE_REPO_DIR_NAME),
    ])
    ssh_executor.run_command(clone_cmd, cwd=remote_work_dir)

def _collect_changed_files_for_branch(
    ssh_executor: SSHExecutor, repo_dir: RemotePath, git_executable: str, branch: str
) -> set[str]:
    """Zwraca zbiór plików zmienionych między HEAD a origin/branch.

    Wykorzystuje git diff z wykrywaniem przeniesień/kopii (-M -C) i filtruje
    na typy A/M/R/C.

    Args:
        ssh_executor: Executor do wykonywania poleceń SSH.
        repo_dir: Ścieżka do katalogu repozytorium.
        git_executable: Ścieżka do pliku wykonywalnego git.
        branch: Nazwa gałęzi do porównania.

    Returns:
        Zbiór ścieżek zmienionych plików.
    """
    changed: set[str] = set()
    ssh_executor.run_command(f"{git_executable} fetch origin {quote_shell(branch)}", cwd=repo_dir)
    merge_base_out = ssh_executor.run_command(
        f"{git_executable} merge-base HEAD {quote_shell(f'origin/{branch}')} ",
        cwd=repo_dir,
    )
    merge_base = merge_base_out.stdout.strip().splitlines()[0]
    diff_cmd = (
        f"{git_executable} diff -M -C --name-status --diff-filter=ACMR "
        + quote_shell(f"{merge_base}..origin/{branch}")
    )
    diff_out = ssh_executor.run_command(diff_cmd, cwd=repo_dir)
    for line in diff_out.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split('\t')
        status_full = parts[0]
        status = status_full[0]
        if status in {"A", "M"} and len(parts) >= 2:
            changed.add(parts[1])
        elif status in {"R", "C"} and len(parts) >= 3:
            changed.add(parts[2])
    return changed

def _collect_pr_changes(
    platform: BitbucketPlatform,
    ssh_executor: SSHExecutor,
    remote_repo_dir: RemotePath,
    git_executable: str,
    active_prs: list[PullRequest],
) -> tuple[set[str], list[tuple[PullRequest, str]]]:
    """Zbiera zmienione pliki i listę (PR, gałąź) dla późniejszego scalania.

    Args:
        platform: Obiekt platformy Bitbucket.
        ssh_executor: Executor do wykonywania poleceń SSH.
        remote_repo_dir: Ścieżka do katalogu repozytorium.
        git_executable: Ścieżka do pliku wykonywalnego git.
        active_prs: Lista aktywnych PR do analizy.

    Returns:
        Krotka (zbiór zmienionych plików, lista par (PR, gałąź)).
    """
    changed_files: set[str] = set()
    pr_branch_pairs: list[tuple[PullRequest, str]] = []

    for pr in active_prs:
        branch = pr.source_branch
        if not branch:
            warn(f"Brak gałęzi dla PR #{pr.id} - pomijanie.")
            continue
        info(f"Analizowanie PR #{pr.id}: {pr.title} ({branch})")
        try:
            branch_changed = _collect_changed_files_for_branch(
                ssh_executor, remote_repo_dir, git_executable, branch
            )
            list_block(f"Pliki w PR #{pr.id} ({branch}):", sorted(branch_changed))
            changed_files.update(branch_changed)
            pr_branch_pairs.append((pr, branch))
        except UnexpectedExit:
            error(f"Analiza zmian PR #{pr.id} ({branch}) nie powiodła się.")
            continue

    return changed_files, pr_branch_pairs


def _merge_pull_requests(
    ssh_executor: SSHExecutor,
    remote_repo_dir: RemotePath,
    git_executable: str,
    pr_branch_pairs: list[tuple[PullRequest, str]],
) -> None:
    """Scala podane PR przez fetch + merge; w razie konfliktu przerywa merge.

    Args:
        ssh_executor: Executor do wykonywania poleceń SSH.
        remote_repo_dir: Ścieżka do katalogu repozytorium.
        git_executable: Ścieżka do pliku wykonywalnego git.
        pr_branch_pairs: Lista par (PR, nazwa gałęzi) do scalenia.
    """
    info(f"Scalanie {len(pr_branch_pairs)} PR.")

    for pr, branch in sorted(pr_branch_pairs, key=lambda x: x[0].id):
        info(f"Scalanie PR #{pr.id}: {pr.title} ({branch})")
        try:
            ssh_executor.run_command(
                f"{git_executable} fetch origin {quote_shell(branch)}",
                cwd=remote_repo_dir,
            )
            branch_ref = f"origin/{branch}"
            merge_cmd = f"{git_executable} merge --no-ff {quote_shell(branch_ref)}"
            ssh_executor.run_command(
                merge_cmd,
                cwd=remote_repo_dir,
            )
        except UnexpectedExit:
            error(
                f"Scalanie gałęzi '{branch}' dla PR #{pr.id} nie powiodło się."
            )
            ssh_executor.run_command(
                f"{git_executable} merge --abort",
                cwd=remote_repo_dir,
                suppress_error_print=True,
            )
            continue
    info("Zakończono scalanie wszystkich wybranych PR.")


def analyze_pull_requests(
    platform: BitbucketPlatform,
    required_approvals: int,
) -> list[PullRequest]:
    """Zwraca listę PR spełniających minimalną liczbę akceptacji.

    Args:
        platform: Obiekt platformy Bitbucket.
        required_approvals: Minimalna wymagana liczba akceptacji.

    Returns:
        Lista obiektów PullRequest spełniających kryteria.
    """
    info(f"Sprawdzanie pull requestów: {platform.repo}")
    prs = get_pull_requests(platform)
    if not prs:
        info("Brak aktywnych pull requestów.")
        return []

    if required_approvals > 0:
        prs = [pr for pr in prs if pr.approval_count >= required_approvals]
        if not prs:
            info(
                "Brak PR spełniających wymóg akceptacji "
                f"(>= {required_approvals})."
            )
            return []
        info(
            f"PR po odfiltrowaniu (>= {required_approvals} akceptacji): {len(prs)}"
        )
    info(f"Znaleziono {len(prs)} pull requestów do analizy.")
    return prs


def merge_local(
    platform: BitbucketPlatform,
    ssh_executor: SSHExecutor,
    remote_work_dir: RemotePath,
    git_executable: str,
    pull_requests: list[PullRequest],
) -> tuple[set[str], list[PullRequest]]:
    """Klonuje repo, zbiera zmienione pliki, scala PR lokalnie.

    Args:
        platform: Obiekt platformy Bitbucket.
        ssh_executor: Executor do wykonywania poleceń SSH.
        remote_work_dir: Ścieżka do katalogu roboczego na serwerze.
        git_executable: Ścieżka do pliku wykonywalnego git.
        pull_requests: Lista PR do scalenia.

    Returns:
        Krotka (zbiór zmienionych plików, lista scalonych PR).
    """
    if not pull_requests:
        return set(), []

    remote_repo_dir = remote_work_dir / REMOTE_REPO_DIR_NAME
    _clone_repo(platform, ssh_executor, remote_work_dir, git_executable)

    changed_files, pr_branch_pairs = _collect_pr_changes(
        platform=platform,
        ssh_executor=ssh_executor,
        remote_repo_dir=remote_repo_dir,
        git_executable=git_executable,
        active_prs=pull_requests,
    )

    if not pr_branch_pairs:
        warn("Brak PR do scalenia po analizie.")
        return changed_files, []

    _merge_pull_requests(
        ssh_executor=ssh_executor,
        remote_repo_dir=remote_repo_dir,
        git_executable=git_executable,
        pr_branch_pairs=pr_branch_pairs,
    )
    merged_prs = [pr for pr, _ in pr_branch_pairs]
    return changed_files, merged_prs
