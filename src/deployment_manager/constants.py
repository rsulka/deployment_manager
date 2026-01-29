"""Stałe używane w procesie wdrożenia (ścieżki, nazwy plików, logów)."""
from __future__ import annotations

CODES_DIR_NAME = "codes"
REPO_CODES_DIR_NAME = "kody"
EXTRA_FILES_DIR_NAME = "dodatkowe_pliki"
META_FILE_NAME = "meta.txt"
PRE_DEPLOY_SCRIPT_NAME = "pre_deploy.sas"
PRE_DEPLOY_BASH_SCRIPT_NAME = "pre_deploy.sh"
SPKS_DIR_NAME = "spks"
LOGS_DIR_NAME = "logs"

METADATA_SPK_NAME = "metadata.spk"
METADATA_SUBPROP_NAME = "metadata.subprop"

LOG_METADATA_EXPORT = "metadata_export.log"
LOG_METADATA_IMPORT = "metadata_import.log"
LOG_PRE_DEPLOY_SAS = "pre_deploy_sas.log"
LOG_PRE_DEPLOY_BASH = "pre_deploy_bash.log"
LOG_REDEPLOY_JOBS = "redeploy_jobs.log"
LOG_UPDATE_DICTIONARIES = "update_dictionaries.log"

REMOTE_REPO_DIR_NAME = "repo"
JOBS_TO_REDEPLOY_FILENAME = "jobs_to_redeploy.txt"
DEPLOY_DIR_PREFIX = "dm_"

__all__ = [
    "CODES_DIR_NAME",
    "REPO_CODES_DIR_NAME",
    "EXTRA_FILES_DIR_NAME",
    "META_FILE_NAME",
    "PRE_DEPLOY_SCRIPT_NAME",
    "PRE_DEPLOY_BASH_SCRIPT_NAME",
    "SPKS_DIR_NAME",
    "LOGS_DIR_NAME",
    "METADATA_SPK_NAME",
    "METADATA_SUBPROP_NAME",
    "LOG_METADATA_EXPORT",
    "LOG_METADATA_IMPORT",
    "LOG_PRE_DEPLOY_SAS",
    "LOG_PRE_DEPLOY_BASH",
    "LOG_REDEPLOY_JOBS",
    "REMOTE_REPO_DIR_NAME",
    "JOBS_TO_REDEPLOY_FILENAME",
    "LOG_UPDATE_DICTIONARIES",
    "DEPLOY_DIR_PREFIX",
]
