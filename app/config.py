from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MapConfig:
    place_name: str = "Helsinki, Suomi"
    network_type: str = "drive"
    simplify: bool = True
    retain_all: bool = False


@dataclass
class ExperimentConfig:
    seed: int = 42
    target_count: int = 20
    max_attempts: int = 100


@dataclass
class EventScenarioConfig:
    change_type: str
    cost_multiplier: float | None = None


@dataclass
class EventConfig:
    scenarios: list[EventScenarioConfig] = field(default_factory=lambda: [
        EventScenarioConfig(change_type="remove", cost_multiplier=None),
        EventScenarioConfig(change_type="increase_cost", cost_multiplier=3.0),
    ])


@dataclass
class PathConfig:
    project_root: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = project_root / "data"
    raw_dir: Path = data_dir / "raw"
    outputs_dir: Path = data_dir / "outputs"


@dataclass
class AppConfig:
    map: MapConfig = field(default_factory=MapConfig)
    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)
    event: EventConfig = field(default_factory=EventConfig)
    paths: PathConfig = field(default_factory=PathConfig)


def get_config() -> AppConfig:
    return AppConfig()