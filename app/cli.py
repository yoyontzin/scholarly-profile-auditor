"""CLI con Typer: `spa audit` y `spa serve`."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.core.config import get_config
from app.core.logging import setup_logging
from app.services.exports import export_all
from app.services.pipeline import PipelineInput, run_pipeline

app = typer.Typer(
    help="scholarly-profile-auditor — auditoría bibliográfica reproducible.",
    add_completion=False,
)
console = Console()


@app.command()
def audit(
    orcid: str = typer.Option(..., "--orcid", help="ORCID iD del autor."),
    scholar: str | None = typer.Option(None, "--scholar", help="URL pública de Google Scholar."),
    refs: Path | None = typer.Option(None, "--refs", help="Archivo de referencias (.bib/.ris/.csv/.json)."),
    aliases: list[str] = typer.Option([], "--alias", help="Alias adicionales del autor (repetible)."),
    whitelist: Path | None = typer.Option(None, "--whitelist", help="Archivo con títulos a forzar como confirmados."),
    blacklist: Path | None = typer.Option(None, "--blacklist", help="Archivo con títulos a descartar."),
    area: str | None = typer.Option(None, "--area", help="Área SNII (fisico_matematicas, ciencias_biologicas_quimicas)."),
    out: Path = typer.Option(Path("./out"), "--out", help="Carpeta de salida."),
) -> None:
    """Ejecuta el pipeline completo y genera todos los artefactos."""
    setup_logging()
    cfg = get_config()

    wl: set[str] = set()
    if whitelist and whitelist.exists():
        wl = {line.strip().lower() for line in whitelist.read_text().splitlines() if line.strip()}
    bl: set[str] = set()
    if blacklist and blacklist.exists():
        bl = {line.strip().lower() for line in blacklist.read_text().splitlines() if line.strip()}

    inp = PipelineInput(
        orcid=orcid,
        scholar_url=scholar,
        user_refs_path=refs,
        aliases=aliases,
        area_snii=area,
        whitelist_titles=wl,
        blacklist_titles=bl,
    )

    console.print(f"[bold blue]→ Auditando ORCID {orcid}...[/bold blue]")
    result = asyncio.run(run_pipeline(inp))

    out_dir = out / orcid.replace("/", "_")
    artifacts = export_all(result, out_dir)

    # Resumen visual
    table = Table(title="Resumen de la auditoría")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", justify="right")
    table.add_row("Obras analizadas", str(len(result.works)))
    table.add_row("Confirmadas", f"[green]{len(result.confirmed)}[/green]")
    table.add_row("Ambiguas (revisar)", f"[yellow]{len(result.ambiguous)}[/yellow]")
    table.add_row("Rechazadas", f"[red]{len(result.rejected)}[/red]")
    table.add_row("Conflictos detectados", str(len(result.conflicts)))
    for src, c in result.metrics.by_source.items():
        table.add_row(f"Citas ({src.value})", str(c))
    console.print(table)

    console.print("\n[bold]Artefactos generados:[/bold]")
    for name, path in artifacts.items():
        console.print(f"  • {name} → {path}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8088, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Levanta FastAPI con el widget montado."""
    import uvicorn
    setup_logging()
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command()
def config_show() -> None:
    """Imprime la configuración efectiva (debug)."""
    setup_logging()
    cfg = get_config()
    console.print("[bold]Env:[/bold]", cfg.env.model_dump())
    console.print("[bold]config.yaml:[/bold]", cfg.config)
    console.print("[bold]snii_reference_params.yaml:[/bold]", cfg.snii_params)


if __name__ == "__main__":
    app()
