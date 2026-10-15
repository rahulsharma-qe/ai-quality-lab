"""A team's whole setup in one file: team.yaml, team.yml or team.json. Same schema for both.

Paths inside the file are relative to the folder the file is in.
Secrets never go in the file: give the NAME of an environment variable instead
(for example auth_token_env: CLAIMS_API_TOKEN).
"""

import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from aiquality.adapters import ADAPTER_NAMES
from aiquality.checks import available_checks
from aiquality.config.company_minimums import CompanyMinimums
from aiquality.errors import ConfigError

CONFIG_FILE_NAMES = ("team.yaml", "team.yml", "team.json")
TOP_LEVEL_SETTINGS = {"team", "client", "description", "agent", "live_agent", "golden_set",
                      "policies", "plugins", "checks", "reports", "max_error_rate"}
AGENT_SETTINGS = {
    "python_function": ({"file", "function"}, set()),
    "http_endpoint": ({"url"}, {"method", "question_field", "answer_field", "headers",
                                "auth_token_env", "auth_header", "auth_prefix",
                                "timeout_seconds"}),
    "recorded_responses": ({"path"}, set()),
}
SECRET_WORDS = ("token", "secret", "password", "api_key", "apikey", "authorization")
DEFAULT_MAX_ERROR_RATE = 0.2


@dataclass
class CheckSettings:
    name: str
    threshold: float
    blocking: bool = True
    options: dict = field(default_factory=dict)


@dataclass
class TeamConfig:
    team: str
    folder: Path
    agent: dict
    golden_set: Path
    checks: dict[str, CheckSettings]
    client: Optional[str] = None
    description: str = ""
    live_agent: Optional[dict] = None
    policies: Optional[Path] = None
    reports: list[str] = field(default_factory=lambda: ["console"])
    plugins: list[Path] = field(default_factory=list)
    max_error_rate: float = DEFAULT_MAX_ERROR_RATE
    source: str = ""

    @classmethod
    def load(cls, path, company_minimums: Optional[CompanyMinimums] = None) -> "TeamConfig":
        """Load a config file, or a folder holding team.yaml / team.yml / team.json."""
        path = _find_config_file(Path(path))
        data = _read_config_file(path)
        return cls.from_dict(data, folder=path.parent, source=str(path), company_minimums=company_minimums)

    @classmethod
    def from_dict(cls, data: dict, folder: Path, source: str = "config",
                  company_minimums: Optional[CompanyMinimums] = None) -> "TeamConfig":
        from aiquality.reporting import available_reporters  # imported here to avoid a cycle

        problems = []
        if not isinstance(data, dict):
            raise ConfigError(source, ["the file must contain settings (key: value pairs)"])
        # Plugins first: a team's own checks and reporters must be registered before validation.
        plugins = _load_plugins(data.get("plugins") or [], Path(folder), source)
        unknown = sorted(set(data) - TOP_LEVEL_SETTINGS)
        if unknown:
            problems.append(f"unknown setting(s): {', '.join(unknown)}. Allowed: {', '.join(sorted(TOP_LEVEL_SETTINGS))}")
        for required in ("team", "agent", "golden_set", "checks"):
            if not data.get(required):
                problems.append(f"'{required}' is required")

        problems += _agent_problems(data.get("agent"), "agent")
        if data.get("live_agent") is not None:
            problems += _agent_problems(data["live_agent"], "live_agent")

        checks, check_problems = _parse_checks(data.get("checks"))
        problems += check_problems
        minimums = company_minimums or CompanyMinimums.load()
        if not check_problems:
            problems += minimums.problems_with(checks)

        reports = data.get("reports") or ["console"]
        unknown_reports = [r for r in reports if r not in available_reporters()]
        if unknown_reports:
            problems.append(f"unknown report(s): {', '.join(unknown_reports)}. Available: {', '.join(available_reporters())}")

        max_error_rate = data.get("max_error_rate", DEFAULT_MAX_ERROR_RATE)
        if not isinstance(max_error_rate, (int, float)) or not 0 <= max_error_rate <= 1:
            problems.append("'max_error_rate' must be a number between 0 and 1")

        if problems:
            raise ConfigError(source, problems)

        folder = Path(folder)
        golden_set = (folder / data["golden_set"]).resolve()
        if not golden_set.is_file():
            raise ConfigError(source, [f"golden_set file not found: {golden_set}"])
        policies = (folder / data["policies"]).resolve() if data.get("policies") else None
        if policies is not None and not policies.is_file():
            raise ConfigError(source, [f"policies file not found: {policies}"])

        return cls(team=str(data["team"]), folder=folder, agent=data["agent"], golden_set=golden_set,
                   checks=checks, client=data.get("client"), description=data.get("description", ""),
                   live_agent=data.get("live_agent"), policies=policies, reports=list(reports),
                   plugins=plugins, max_error_rate=float(max_error_rate), source=source)


def _load_plugins(plugin_files, folder: Path, source: str) -> list[Path]:
    """Import a team's own plugin files (checks, reporters) so their @register_... decorators run."""
    if not isinstance(plugin_files, list):
        raise ConfigError(source, ["'plugins' must be a list of .py files, e.g. [my_checks.py]"])
    loaded = []
    for name in plugin_files:
        path = (folder / name).resolve()
        if path.suffix != ".py" or not path.is_file():
            raise ConfigError(source, [f"plugin file not found (must be a .py file): {path}"])
        module_name = "aiquality_plugin_" + hashlib.sha1(str(path).encode()).hexdigest()[:10] + f"_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as error:
            sys.modules.pop(module_name, None)
            raise ConfigError(source, [f"plugin {path.name} failed to load: {type(error).__name__}: {error}"])
        loaded.append(path)
    return loaded


def _find_config_file(path: Path) -> Path:
    if path.is_dir():
        for name in CONFIG_FILE_NAMES:
            if (path / name).is_file():
                return path / name
        raise ConfigError(str(path), [f"no {' / '.join(CONFIG_FILE_NAMES)} in this folder"])
    if not path.is_file():
        raise ConfigError(str(path), ["config file not found"])
    return path


def _read_config_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix.lower() in (".yaml", ".yml"):
            return yaml.safe_load(text) or {}
        if path.suffix.lower() == ".json":
            return json.loads(text)
    except (yaml.YAMLError, json.JSONDecodeError) as error:
        raise ConfigError(str(path), [f"could not read the file: {error}"])
    raise ConfigError(str(path), ["config must be .yaml, .yml or .json"])


def _agent_problems(settings, label: str) -> list[str]:
    if settings is None:
        return []
    if not isinstance(settings, dict):
        return [f"'{label}' must be a block of settings"]
    adapter = settings.get("adapter")
    if adapter not in AGENT_SETTINGS:
        return [f"'{label}.adapter' must be one of: {', '.join(ADAPTER_NAMES)}"]
    required, optional = AGENT_SETTINGS[adapter]
    problems = [f"'{label}.{key}' is required for the {adapter} adapter" for key in sorted(required - set(settings))]
    unknown = set(settings) - required - optional - {"adapter"}
    for key in sorted(unknown):
        if _looks_like_secret(key):
            problems.append(f"'{label}.{key}' looks like a secret. Put it in an environment "
                            f"variable and give only its name, e.g. auth_token_env")
        else:
            problems.append(f"'{label}.{key}' is not a setting of the {adapter} adapter")
    for header in (settings.get("headers") or {}):
        if _looks_like_secret(header):
            problems.append(f"'{label}.headers.{header}' would put a secret in the config; use auth_token_env")
    return problems


def _looks_like_secret(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return not lowered.endswith("_env") and any(word in lowered for word in SECRET_WORDS + ("key",))


def _parse_checks(raw) -> tuple[dict[str, CheckSettings], list[str]]:
    if not isinstance(raw, dict) or not raw:
        return {}, ["'checks' must list at least one check, e.g. required_phrases: {threshold: 0.9}"]
    checks, problems = {}, []
    known = set(available_checks())
    for name, settings in raw.items():
        if name not in known:
            problems.append(f"unknown check '{name}'. Available: {', '.join(sorted(known))}")
            continue
        settings = settings or {}
        threshold = settings.get("threshold")
        if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
            problems.append(f"check '{name}': 'threshold' must be a number from 0 to 1 (a pass rate)")
            continue
        blocking = settings.get("blocking", True)
        options = {k: v for k, v in settings.items() if k not in ("threshold", "blocking")}
        checks[name] = CheckSettings(name=name, threshold=float(threshold), blocking=bool(blocking), options=options)
    return checks, problems
