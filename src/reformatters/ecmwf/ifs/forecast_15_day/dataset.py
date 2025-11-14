"""Dataset orchestration for ECMWF IFS 15-day forecast."""

from pathlib import Path

from reformatters.common.dataset import Dataset
from reformatters.common.region_job import RegionJob
from reformatters.common.template_config import TemplateConfig
from reformatters.ecmwf.ifs.forecast_15_day.region_job import (
    EcmwfIfsForecast15DayRegionJob,
)
from reformatters.ecmwf.ifs.forecast_15_day.template_config import (
    EcmwfIfsForecast15DayTemplateConfig,
)


class EcmwfIfsForecast15DayDataset(Dataset):
    """ECMWF IFS 15-day high-resolution forecast dataset.

    Orchestrates template creation, data updates, and validation
    for ECMWF IFS forecasts.
    """

    def __init__(self, storage_path: Path | None = None):
        """Initialize dataset.

        Args:
            storage_path: Path to zarr storage (default: data/ecmwf/ifs/forecast-15-day/)
        """
        if storage_path is None:
            storage_path = Path("data/ecmwf/ifs/forecast-15-day")

        super().__init__(storage_path)

    def template_config(self) -> TemplateConfig:
        """Return template configuration."""
        return EcmwfIfsForecast15DayTemplateConfig()

    def region_job(self) -> RegionJob:
        """Return region job for processing."""
        return EcmwfIfsForecast15DayRegionJob(
            zarr_store=self.zarr_store, cache_dir=Path(".cache/ecmwf")
        )
