"""Minimalny logger oparty o loguru."""
from __future__ import annotations

from typing import Iterable, Any
import sys
from shutil import get_terminal_size
from loguru import logger

__all__ = ["info", "warn", "error", "setup_logging", "step", "ok", "list_block"]


def info(msg: Any, *args: Any, **kwargs: Any) -> None:
    """Loguje wiadomość na poziomie INFO.

    Args:
        msg: Wiadomość do zalogowania.
        *args: Dodatkowe argumenty pozycyjne dla logowania.
        **kwargs: Dodatkowe argumenty nazwane dla logowania.
    """
    logger.info(msg, *args, **kwargs)


def _term_width(min_width: int = 60, max_width: int = 500) -> int:
    """Zwraca wykrytą szerokość terminala.

    Args:
        min_width: Minimalna szerokość terminala.
        max_width: Maksymalna szerokość terminala.

    Returns:
        Szerokość terminala w granicach min_width i max_width.
    """
    try:
        width = get_terminal_size().columns
    except OSError:
        width = 80
    return max(min_width, min(width, max_width))


def _rule(char: str = "─", color: str | None = None) -> str:
    """Zwraca kolorowaną linię o szerokości terminala do separacji bloków.

    Args:
        char: Znak używany do rysowania linii.
        color: Kolor linii (np. 'cyan', 'magenta').

    Returns:
        Sformatowana linia z kolorami.
    """
    c = color or "cyan"
    return f"<{c}>{char * _term_width()}</{c}>"


def step(message: str) -> None:
    """Loguje wyraźnie wyróżniony krok.

    Args:
        message: Opis kroku do zalogowania.
    """
    top = _rule("─", "magenta")
    line = f"<magenta><b>▶ KROK</b></magenta> <white>{message}</white>"
    bottom = _rule("─", "magenta")
    logger.opt(raw=True, colors=True).info(f"\n{top}\n{line}\n{bottom}\n")


def ok(message: str) -> None:
    """Loguje zakończenie kroku sukcesem (OK).

    Args:
        message: Opis zakończonego kroku.
    """
    line = f"<green><b>✔ OK</b></green> <white>{message}</white>"
    sep = _rule("─", "green")
    logger.opt(raw=True, colors=True).info(f"{line}\n{sep}\n\n")


def warn(msg: Any, *args: Any, **kwargs: Any) -> None:
    """Loguje wiadomość na poziomie WARNING.

    Args:
        msg: Wiadomość do zalogowania.
        *args: Dodatkowe argumenty pozycyjne dla logowania.
        **kwargs: Dodatkowe argumenty nazwane dla logowania.
    """
    logger.warning(msg, *args, **kwargs)


def error(msg: Any, *args: Any, **kwargs: Any) -> None:
    """Loguje wiadomość na poziomie ERROR.

    Args:
        msg: Wiadomość do zalogowania.
        *args: Dodatkowe argumenty pozycyjne dla logowania.
        **kwargs: Dodatkowe argumenty nazwane dla logowania.
    """
    logger.error(msg, *args, **kwargs)


def list_block(header: str, items: Iterable[str]) -> None:
    """Wypisuje listę elementów w wyróżniony sposób (nagłówek + wypunktowanie).

    Args:
        header: Nagłówek listy.
        items: Elementy do wypisania.
    """
    lines: list[str] = []
    for it in items:
        lines.append(f"<cyan>•</cyan> <white>{it}</white>")
    if not lines:
        lines.append("<dim>(brak elementów)</dim>")

    top = _rule("─", "cyan")
    bottom = _rule("─", "cyan")
    body = "\n".join(lines)
    logger.opt(raw=True, colors=True).info(
        f"\n{top}\n<cyan><b>{header}</b></cyan>\n\n{body}\n{bottom}\n\n"
    )


def _configure_level_colors() -> None:
    """Ustawia kolory poziomów logowania w konsoli."""
    logger.level("INFO", color="<blue>")
    logger.level("WARNING", color="<yellow>")
    logger.level("ERROR", color="<red>")


def _console_format() -> str:
    """Buduje format konsolowy z wyrównanym poziomem i czasem.

    Returns:
        String formatujący dla logowania konsolowego.
    """
    return (
        "<level>{level: <8}</level> "
        "<dim>{time:YYYY-MM-DD HH:mm:ss}</dim> {message}"
    )


def setup_logging() -> None:
    """Konfiguruje logowanie do stdout z czytelnym formatem."""
    logger.remove()
    _configure_level_colors()
    logger.add(
        sys.stdout,
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=False,
        format=_console_format(),
        enqueue=True,
    )
