"""Check add-on packaging and option translation without a Supervisor host."""

import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_supervisor_options_are_all_mapped_and_secrets_are_optional():
    path = ROOT / "addons/opencook/rootfs/opt/opencook/launch.py"
    spec = importlib.util.spec_from_file_location("addon_launch", path)
    launch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launch)
    config = yaml.safe_load((ROOT / "addons/opencook/config.yaml").read_text())
    assert set(config["options"]) == set(config["schema"])
    assert set(launch.OPTION_ENV) | {"log_level"} == set(config["options"])
    environment = launch.build_environment(
        config["options"], {"OPENCOOK_VISION_API_KEY": "stale", "OPENCOOK_ADMIN_PASSWORD": "stale"}
    )
    assert "OPENCOOK_VISION_API_KEY" not in environment
    assert "OPENCOOK_ADMIN_PASSWORD" not in environment
    assert environment["OPENCOOK_DATA_DIR"] == "/data/opencook"
    assert environment["OPENCOOK_PORT"] == "8000"
    assert config["host_network"]
    assert "aarch64" in config["arch"]


def test_hacs_manifest_and_translations():
    component = ROOT / "custom_components/opencook"
    manifest = json.loads((component / "manifest.json").read_text())
    assert manifest["domain"] == component.name
    assert manifest["config_flow"]
    assert manifest["codeowners"] == ["@coding-lion"]
    english = json.loads((component / "strings.json").read_text())
    for language in ("en", "de"):
        translation = json.loads((component / f"translations/{language}.json").read_text())
        assert translation["config"]["step"].keys() == english["config"]["step"].keys()
