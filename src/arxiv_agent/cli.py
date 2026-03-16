from __future__ import annotations

from pathlib import Path

import typer

from .config import load_keyword_rules, load_settings

app = typer.Typer(help="arXiv monitoring and summarization agent")


@app.command("init-db")
def init_db(settings: Path = typer.Option(Path("config/settings.yaml"), exists=True)) -> None:
    from .db import Database

    s = load_settings(settings)
    db = Database(s.database_path)
    db.init_schema()
    typer.echo(f"DB initialized at {s.database_path}")


@app.command("run")
def run(
    settings: Path = typer.Option(Path("config/settings.yaml"), exists=True),
    keywords: Path = typer.Option(Path("config/keywords.yaml"), exists=True),
) -> None:
    from .pipeline import run_once

    s = load_settings(settings)
    r = load_keyword_rules(keywords)
    if not r.profiles:
        raise typer.BadParameter("No profiles found in keywords file")
    result = run_once(s, r)
    typer.echo(
        f"Done. run_id={result.run_id} fetched={result.fetched} "
        f"matched={result.matched} channels={','.join(result.notified_channels)}"
    )


@app.command("schedule")
def schedule(
    settings: Path = typer.Option(Path("config/settings.yaml"), exists=True),
    keywords: Path = typer.Option(Path("config/keywords.yaml"), exists=True),
) -> None:
    from .scheduler import run_scheduler

    s = load_settings(settings)
    r = load_keyword_rules(keywords)
    if not r.profiles:
        raise typer.BadParameter("No profiles found in keywords file")
    run_scheduler(s, r)


if __name__ == "__main__":
    app()
