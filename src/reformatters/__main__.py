"""CLI entry point for ECMWF reformatters."""

from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track

from reformatters.ecmwf.ifs.forecast_15_day import EcmwfIfsForecast15DayDataset

app = typer.Typer(
    help="ECMWF Open Data to Zarr - Convert ECMWF forecasts to cloud-optimized Zarr format",
    no_args_is_help=True,
)
console = Console()


@app.command()
def update_template(
    storage_path: Path = typer.Option(
        None,
        "--storage-path",
        "-s",
        help="Path to zarr storage directory",
    ),
) -> None:
    """Update the zarr template (structure and metadata)."""
    console.print("[bold blue]Updating template...[/bold blue]")

    dataset = EcmwfIfsForecast15DayDataset(storage_path)
    dataset.update_template()

    console.print("[bold green]✓ Template updated successfully[/bold green]")


@app.command()
def update(
    storage_path: Path = typer.Option(
        None,
        "--storage-path",
        "-s",
        help="Path to zarr storage directory",
    ),
) -> None:
    """Run operational update (fetch latest forecast)."""
    console.print("[bold blue]Running operational update...[/bold blue]")

    dataset = EcmwfIfsForecast15DayDataset(storage_path)
    dataset.update()

    console.print("[bold green]✓ Update complete[/bold green]")


@app.command()
def backfill(
    end_date: str = typer.Argument(..., help="End date (YYYY-MM-DD)"),
    start_date: str = typer.Option(
        None,
        "--start-date",
        "-s",
        help="Start date (YYYY-MM-DD). If not provided, backfill from beginning.",
    ),
    storage_path: Path = typer.Option(
        None,
        "--storage-path",
        "-p",
        help="Path to zarr storage directory",
    ),
) -> None:
    """Backfill historical forecast data."""
    console.print(f"[bold blue]Running backfill to {end_date}...[/bold blue]")

    # Parse dates
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None

    dataset = EcmwfIfsForecast15DayDataset(storage_path)
    dataset.backfill(end_date=end_dt, start_date=start_dt)

    console.print("[bold green]✓ Backfill complete[/bold green]")


@app.command()
def validate(
    storage_path: Path = typer.Option(
        None,
        "--storage-path",
        "-s",
        help="Path to zarr storage directory",
    ),
) -> None:
    """Validate the dataset."""
    console.print("[bold blue]Validating dataset...[/bold blue]")

    dataset = EcmwfIfsForecast15DayDataset(storage_path)
    success = dataset.validate()

    if success:
        console.print("[bold green]✓ Validation passed[/bold green]")
    else:
        console.print("[bold red]✗ Validation failed[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def info(
    storage_path: Path = typer.Option(
        None,
        "--storage-path",
        "-s",
        help="Path to zarr storage directory",
    ),
) -> None:
    """Display dataset information."""
    import xarray as xr

    dataset = EcmwfIfsForecast15DayDataset(storage_path)

    if not dataset.zarr_store.exists():
        console.print("[bold red]Dataset does not exist[/bold red]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Dataset path:[/bold] {dataset.zarr_store}")

    try:
        ds = xr.open_zarr(dataset.zarr_store)

        console.print("\n[bold]Dimensions:[/bold]")
        for dim, size in ds.dims.items():
            console.print(f"  {dim}: {size}")

        console.print("\n[bold]Coordinates:[/bold]")
        for coord in ds.coords:
            console.print(f"  {coord}")

        console.print("\n[bold]Data variables:[/bold]")
        for var in ds.data_vars:
            console.print(f"  {var}: {ds[var].dims}")

        if "init_time" in ds.dims:
            console.print("\n[bold]Time range:[/bold]")
            console.print(f"  First: {ds.init_time.min().values}")
            console.print(f"  Last: {ds.init_time.max().values}")

        # Calculate size
        import numpy as np

        total_size = sum(
            ds[var].nbytes for var in ds.data_vars if hasattr(ds[var], "nbytes")
        )
        console.print(
            f"\n[bold]Estimated size:[/bold] {total_size / 1e9:.2f} GB (uncompressed)"
        )

    except Exception as e:
        console.print(f"[bold red]Error reading dataset: {e}[/bold red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
