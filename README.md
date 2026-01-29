# Deployment Manager

Narzędzie do automatyzacji procesu wdrażania opartego o PR Bitbucket.

Wszystkie operacje wykonywane są przez SSH na serwerze zdalnym w kontekście użytkownika `deploy_user`
pobieranego z konfiguracji (np.`misadmin`).
Skrypt można uruchamiać z dowolnego serwera lub stacji roboczej, o ile spełnione są poniższe wymagania.

## Wymagania

- Python 3.9+
- Dostęp do serwera zdalnego przez SSH (klucze wymienione dla użytkownika `deploy_user`)
- Zainstalowany i działający klient `git` na serwerze zdalnym.
- Narzędzia SAS (ExportPackage, ImportPackage, DeployJobs) dostępne na serwerze zdalnym.
- Poprawnie skonfigurowane profile metadanych SAS dla `deploy_user`.

## Instalacja

Zalecane jest użycie wirtualnego środowiska.

```bash
python3 -m venv .venv
```

Na AIX, ze względu na problem z kompilacją pakietów, lepiej użyć wirtualnego środowiska z dostępem do pakietów systemowych.

```bash
python3 -m venv .venv --system-site-packages
```

Aktywacja środowiska:

- Linux / AIX: `source .venv/bin/activate`
- Windows: `.venv\Scripts\Activate.ps1`

Następnie zainstaluj narzędzie w aktywnym środowisku (w katalogu projektu):

```bash
pip install -e .
```

## Konfiguracja

Konfiguracja jest wczytywana z plików JSON w katalogu `configs/`. Pliki wczytywane są w kolejności: `common.json` → `<środowisko>.json` → `local.json`. Ustawienia z kolejnych plików nadpisują poprzednie.

1. **`common.json`**: Zawiera ustawienia wspólne dla wszystkich środowisk.
2. **`<środowisko>.json`** (`dev.json`, `uat.json`, `prod.json`): Specyficzne ustawienia dla danego środowiska.
3. **`local.json`**: Ustawienia lokalne, które nie powinny być częścią repozytorium (np. tokeny). Ten plik jest ignorowany przez Git.

### Token dostępu do BitBucket

W BitBucket wybrać `Manage Account` → `HTTP access tokens`, stworzyć nowy token.
Token dostępu do BitBucket można ustawić na dwa sposoby:

1. **Zmienna środowiskowa:**

   ```bash
   export BITBUCKET_API_TOKEN="wygenerowany_token"
   ```

2. **Plik `configs/local.json`:**

   ```json
   {
       "bitbucket_api_token": "wygenerowany_token"
   }
   ```

### Konfiguracja katalogu runtime

Katalogi robocze na serwerze zdalnym tworzone są w katalogu bazowym zdefiniowanym w `dm_runtime_base_dir` (np. w `configs/common.json`).

```json
{
    "dm_runtime_base_dir": "/migracje/dm_runtime"
}
```

### Konfiguracja klienta SSH na Windows

Z jakiegoś powodu Saspy wymaga wskazania na jakim użytkowniku ma się łączyć w pliku `.ssh/config`,
mimo, że konfiguracja użytkownika jest w `configs/sascfg_personal.py`.
Przykładowa konfiguracja w `.ssh/config`:

```text
Host misdev1
    HostName misdev1
    User misadmin
    IdentityFile ~/.ssh/id_rsa
 
Host misuat
    HostName misuat
    User misadmin
    IdentityFile ~/.ssh/id_rsa

Host misprod
    HostName misprod
    User rafsul033000
    IdentityFile ~/.ssh/id_rsa
```

## Użycie

Po instalacji narzędzie jest dostępne jako komenda `dm`.

Uruchom ze wskazaniem repozytorium Bitbucket oraz środowiska docelowego:

```bash
dm -r NAZWA_REPO -e DEV
```

Dostępne środowiska: `DEV`, `UAT`, `PROD`.

### Logika liczby akceptacji PR

Liczba wymaganych akceptacji dla Pull Requestu jest definiowana w pliku konfiguracyjnym danego środowiska (np. `configs/dev.json`) w kluczu `approvals`.

- **DEV**: 0 akceptacji (wszystkie aktywne PR)
- **UAT**: ≥1 akceptacja
- **PROD**: ≥2 akceptacje

### Przebieg procesu wdrożenia

1. Klonowanie repozytorium na serwer zdalny i zebranie/połączenie zmian z zakwalifikowanych PR.
2. Zbudowanie pakietu w katalogu roboczym (`<dm_runtime_base_dir>/dm_<timestamp>_<uuid>`).
3. Wykonanie skryptu `pre_deploy.sh` (jeśli istnieje).
4. Wdrożenie kodu modułu do ścieżki z tabeli SAS `MDS.MODULY`.
5. Aktualizacja słowników MDS (dla środowisk innych niż DEV).
6. Wykonanie skryptu `pre_deploy.sas` (jeśli istnieje).
7. Eksport i import metadanych SAS (jeśli istnieje plik `meta.txt`).
8. Redeploy jobów SAS (jeśli zdefiniowano w `meta.txt`).

## Logi

Wszystkie logi z operacji na serwerze zdalnym trafiają do podkatalogu `logs/` w katalogu roboczym.
