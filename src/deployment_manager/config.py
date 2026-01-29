"""Wczytywanie pliku dm.conf (format key=value) do słownika."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .logger import error


class Config:
    """Zarządza konfiguracją, łącząc ustawienia z plików JSON.

    Attributes:
        BASE_REQUIRED_KEYS: Lista wymaganych kluczy bazowych.
        ENV_REQUIRED_KEYS: Lista wymaganych kluczy środowiskowych.
    """

    BASE_REQUIRED_KEYS: list[str] = [
        "remote_git_path",
        "path_to_exportpackage",
        "path_to_importpackage",
        "path_to_deployjobs",
        "meta_repo",
        "appserver",
        "display",
        "batch_server",
        "is_bitbucket_server",
        "bitbucket_project_or_workspace",
        "bitbucket_host",
        "dm_runtime_base_dir",
    ]

    ENV_REQUIRED_KEYS: list[str] = [
        "deploy_user",
        "server_machine",
        "server_port",
        "deployed_jobs_dir",
        "meta_profile",
        "ssh_host",
        "approvals",
    ]

    def __init__(self, config_dir: Path, env: str):
        """Inicjalizuje konfigurację z plików JSON.

        Args:
            config_dir: Ścieżka do katalogu z plikami konfiguracyjnymi.
            env: Nazwa środowiska (np. 'dev', 'prod').

        Raises:
            ValueError: Gdy brakuje wymaganych kluczy lub są puste.
        """
        self._config: dict[str, Any] = {}
        self._load_config(config_dir, "common")
        self._load_config(config_dir, env.lower())
        self._load_config(config_dir, "local")
        self._load_token_from_env()
        self._validate_schema()

    def _load_config(self, config_dir: Path, name: str) -> None:
        """Wczytuje plik konfiguracyjny JSON.

        Args:
            config_dir: Ścieżka do katalogu z plikami konfiguracyjnymi.
            name: Nazwa pliku (bez rozszerzenia).
        """
        config_file = config_dir / f"{name}.json"
        if not config_file.is_file():
            if name == "local":
                return
            error(f"Plik konfiguracyjny '{config_file}' nie został znaleziony.")
            return

        try:
            with config_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                if not isinstance(data, dict):
                    raise ValueError(
                        f"Plik '{config_file}' nie zawiera obiektu JSON typu dict."
                    )
                self._config.update(data)
        except (json.JSONDecodeError, ValueError) as e:
            error(f"Błąd podczas wczytywania pliku '{config_file}': {e}")
        except OSError as e:
            error(f"Nie można wczytać konfiguracji z '{config_file}': {e}")

    def _load_token_from_env(self) -> None:
        """Wczytuje token Bitbucket z zmiennych środowiskowych i zapisuje go w konfiguracji."""
        token = os.getenv("BITBUCKET_API_TOKEN")
        if token:
            self._config["bitbucket_api_token"] = token

    def _validate_schema(self) -> None:
        """Sprawdza, czy wszystkie wymagane klucze konfiguracyjne są obecne i niepuste."""
        required_keys = set(self.BASE_REQUIRED_KEYS + self.ENV_REQUIRED_KEYS)
        if "bitbucket_api_token" not in self._config:
            required_keys.add("bitbucket_api_token")

        missing_keys = required_keys - self._config.keys()
        if missing_keys:
            raise ValueError(
                "Brak wymaganych kluczy w konfiguracji: "
                f"{', '.join(sorted(missing_keys))}"
            )

        allowed_empty = {"display"}
        keys_to_check = required_keys - allowed_empty
        problematic_keys = {key for key in keys_to_check if not self._config.get(key)}

        if problematic_keys:
            raise ValueError(
                "Puste wartości dla wymaganych kluczy: "
                f"{', '.join(sorted(problematic_keys))}"
            )

    def get(self, key: str, default: Any = None) -> Any:
        """Pobiera wartość z konfiguracji.

        Args:
            key: Klucz konfiguracyjny.
            default: Wartość domyślna gdy klucz nie istnieje.

        Returns:
            Wartość dla podanego klucza lub wartość domyślna.
        """
        return self._config.get(key, default)

    def __contains__(self, key: str) -> bool:
        """Sprawdza czy klucz istnieje w konfiguracji.

        Args:
            key: Klucz do sprawdzenia.

        Returns:
            True jeśli klucz istnieje, False w przeciwnym przypadku.
        """
        return key in self._config

    def __repr__(self) -> str:
        """Zwraca reprezentację tekstową obiektu.

        Returns:
            Reprezentacja tekstowa z listą kluczy.
        """
        return f"Config(keys={list(self._config)})"
