# Instrukcje dla asystentów AI

Ten plik zawiera reguły i kontekst projektu, które powinny być przestrzegane przez
wszystkie narzędzia AI (Google Antigravity, Gemini CLI, Cursor, GitHub Copilot).

## Język i styl

| Element | Język |
|---------|-------|
| Komunikaty w aplikacji (UI) | Polski |
| Komentarze w kodzie | Polski |
| Docstringi | Polski, Google Style (`Args:`, `Returns:`, `Raises:`) |
| Commit messages | Polski |
| Nazwy gałęzi git | Polski |
| Pliki `.md` | Bez ostrzeżeń markdownlint |

## Stack technologiczny

- **Python:** 3.13+
- **Konfiguracja:** `pyproject.toml` (nie requirements.txt)

## Narzędzia i komendy

Używaj `make` do standardowych operacji:

## Konwencje kodu

### Python

- **Formatter:** Ruff (linia max 120 znaków)
- **Linter:** Ruff z regułami: E, F, I, B, C4, UP, ARG, SIM, RUF
- **Typy:** mypy w trybie strict
- **Testy:** pytest

## Workflow

1. **Commit:** Wiadomość po polsku, np. `Dodano obsługę eksportu CSV`
2. **Dokumentacja:** Aktualizuj `README.md` jeśli zmiany tego wymagają

## Ważne uwagi

- **Nie używaj requirements.txt** – wszystko przez `pyproject.toml`
- **Nie pisz komentarzy po angielsku** – komentarze i docstringi po polsku
- **Nie twórz komentarzy w kodzie** – kod powinien być czytelny sam w sobie
- **Aktualizuj README.md** po dodaniu nowych funkcji
- **Utrzymuj aktualność dokumentacji w `docs/`**
- **Nie twórz kodów testów**
