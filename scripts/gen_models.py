# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6"]
# ///
"""Generate Fuzzball application templates for vLLM model deployments.

Input is a checkout of https://github.com/vllm-project/recipes: one YAML per
model under `models/<hf_org>/<hf_repo>.yaml`, the serving-strategy definitions
under `strategies/`, and the hardware vocabulary in `taxonomy.yaml`.

For every model this writes `applications/vllm_<repo>/{template.yaml,
values.yaml,metadata.md}` — an autoscaled vLLM service pool fronted by an
optional LiteLLM proxy, modelled on `applications/vllm/`. Everything the recipe
pins (vLLM flags, env, container image, GPU count, tensor-parallel layout) is
baked in per validated configuration; the user only picks hardware, serving
strategy, checkpoint variant, optional model features, and the usual
scaling/storage/access knobs.

The flag/env layering mirrors the recipes site's own command synthesis
(`src/lib/command-synthesis.js`) so a generated template emits the same
`vllm serve` invocation the recipe page shows for that configuration.

Only single-node serving strategies are generated: a Fuzzball service runs in
one container on one node, so multi-node strategies (multi_node_*, pd_cluster)
and the `--omni` diffusion/audio recipes are skipped and reported.

Usage:
    uv run scripts/gen_models.py --recipes-dir ~/path/to/recipes
    uv run scripts/gen_models.py --recipes-dir ~/path/to/recipes --model openai/gpt-oss-120b
    uv run scripts/gen_models.py --recipes-dir ~/path/to/recipes --dry-run
"""

from __future__ import annotations

import argparse
import itertools
import re
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ── Recipe vocabulary ────────────────────────────────────────────────────────

# Precisions that only run on specific hardware unless a variant overrides it
# with `precision_hardware` (command-synthesis.js: PRECISION_HARDWARE_CONSTRAINTS).
PRECISION_HARDWARE_CONSTRAINTS = {
    "nvfp4": {"brand": "NVIDIA", "generation": "blackwell"},
    "fp4": {"brand": "NVIDIA", "generation": "blackwell"},
}

# A Fuzzball service is one container on one node, so only the strategies that
# keep a single `vllm serve` process on a single node can be expressed.
SINGLE_NODE_DEPLOY_TYPE = "single_node"

# Fuzzball resource device keys, by taxonomy brand. Brands without a key (Google
# TPU, Intel CPU/XPU) are dropped from the hardware matrix.
BRAND_DEVICE_VENDOR = {"NVIDIA": "nvidia.com", "AMD": "amd.com"}

# Container image defaults per brand, used when the recipe pins nothing.
# NVIDIA resolves to an explicit `v<min_vllm_version>` tag (the style guide asks
# for explicit tags); ROCm publishes no matching per-release tag, so it keeps the
# image the hand-written `applications/vllm` app uses.
IMAGE_NVIDIA_NIGHTLY = "vllm/vllm-openai:nightly"
IMAGE_NVIDIA_FALLBACK = "vllm/vllm-openai:latest"
IMAGE_AMD_DEFAULT = (
    "rocm/vllm:rocm7.14.0_cdna_ubuntu24.04_py3.14_pytorch_2.11.0_vllm_0.23.0"
)
IMAGE_AMD_NIGHTLY = "vllm/vllm-openai-rocm:nightly"
LITELLM_IMAGE = "ghcr.io/berriai/litellm:v1.97.0"

RELEASE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ── Loading ──────────────────────────────────────────────────────────────────


def load_yaml(path: Path) -> Any:
    with path.open() as fh:
        return yaml.safe_load(fh)


@dataclass
class Catalog:
    """The recipes repo, parsed."""

    taxonomy: dict
    strategies: dict
    recipes: OrderedDict  # "org/repo" -> recipe dict

    @property
    def hardware_profiles(self) -> dict:
        return self.taxonomy.get("hardware_profiles") or {}


def load_catalog(recipes_dir: Path) -> Catalog:
    taxonomy = load_yaml(recipes_dir / "taxonomy.yaml")
    strategies = {}
    for path in sorted((recipes_dir / "strategies").glob("*.yaml")):
        strategy = load_yaml(path)
        strategies[strategy["name"]] = strategy
    recipes = OrderedDict()
    for path in sorted((recipes_dir / "models").rglob("*.yaml")):
        key = f"{path.parent.name}/{path.stem}"
        recipes[key] = load_yaml(path)
    return Catalog(taxonomy=taxonomy, strategies=strategies, recipes=recipes)


# ── Command synthesis (port of recipes/src/lib/command-synthesis.js) ─────────


def normalize_generation(gen: Any) -> str | None:
    """Consumer cards carry a generation list; the first entry is the lookup key."""
    if isinstance(gen, list):
        return gen[0] if gen else None
    return gen


def hardware_keyed_value(mapping: Any, hw: dict, hw_id: str | None) -> Any:
    """Resolve a hardware-keyed map: exact GPU id > generation > brand > default."""
    if not isinstance(mapping, dict):
        return None
    gen = normalize_generation(hw.get("generation") or hw.get("gpu_generation"))
    brand = hw.get("brand")
    brand = brand.lower() if isinstance(brand, str) else None
    for key in (hw_id, gen, brand):
        if key is not None and key in mapping:
            return mapping[key]
    return mapping.get("default")


def generation_override(block: Any, hw: dict, key: str) -> Any:
    """A `hardware_overrides` entry for this generation, or the NVIDIA-wide one."""
    if not isinstance(block, dict):
        return None
    gen = normalize_generation(hw.get("generation") or hw.get("gpu_generation"))
    override = block.get(gen) if gen else None
    if override is None and hw.get("brand") == "NVIDIA":
        override = block.get("nvidia")
    return override if isinstance(override, dict) else None


def auto_fit_tp(vram_min_gb: float, per_gpu_vram: float, gpu_count: int) -> int:
    """TP=1 when the weights fit one GPU, else fan out across the node."""
    if not vram_min_gb or per_gpu_vram <= 0:
        return gpu_count
    return 1 if vram_min_gb <= per_gpu_vram else gpu_count


def declared_tp(raw: Any, hw: dict, hw_id: str) -> Any:
    return raw if isinstance(raw, int) else hardware_keyed_value(raw, hw, hw_id)


def resolve_single_node_tp(
    recipe: dict, variant: dict, hw: dict, strategy_name: str, hw_id: str
) -> int:
    """Parallel size for a single-node strategy.

    TEP/DEP need the full node by topology. single_node_tp takes, in order, the
    variant's `tp` declaration, the recipe's `strategy_overrides.single_node_tp.tp`,
    then an auto-fit from the variant's VRAM footprint.
    """
    gpu_count = hw.get("gpu_count") if isinstance(hw.get("gpu_count"), int) else 1
    if strategy_name != "single_node_tp":
        return gpu_count
    variant_tp = declared_tp(variant.get("tp"), hw, hw_id)
    if isinstance(variant_tp, int) and variant_tp > 0:
        return min(variant_tp, gpu_count)
    recipe_tp = ((recipe.get("strategy_overrides") or {}).get(strategy_name) or {}).get("tp")
    if isinstance(recipe_tp, int) and recipe_tp > 0:
        return min(recipe_tp, gpu_count)
    vram_gb = hw.get("vram_gb") or 0
    per_gpu = vram_gb / gpu_count if gpu_count else 0
    return auto_fit_tp(variant.get("vram_minimum_gb") or 0, per_gpu, gpu_count)


def effective_compatible_strategies(recipe: dict) -> list[str]:
    """`compatible_strategies` plus strategies opted in per hardware."""
    listed = list(recipe.get("compatible_strategies") or [])
    opt_ins = [
        name
        for name, gate in (recipe.get("strategy_hardware") or {}).items()
        if name not in listed and isinstance(gate, dict) and "supported" in gate.values()
    ]
    return listed + opt_ins


def is_strategy_supported_on_hardware(
    recipe: dict, strategy_name: str, hw: dict, hw_id: str
) -> bool:
    gate = hardware_keyed_value(
        (recipe.get("strategy_hardware") or {}).get(strategy_name), hw, hw_id
    )
    if gate is not None:
        return gate != "unsupported"
    return strategy_name in (recipe.get("compatible_strategies") or [])


def min_gpus_from_block(block: Any, key: str) -> int:
    if block is None:
        return 0
    if isinstance(block, int):
        return block
    if not isinstance(block, dict):
        return 0
    for candidate in (key, f"multi_node_{key}", f"single_node_{key}"):
        if candidate in block and isinstance(block[candidate], int):
            return block[candidate]
    return 0


def min_gpus_for_strategy(recipe: dict, strategy_name: str, hw_id: str) -> int:
    """The recipe's GPU floor for a strategy, including any per-GPU floor."""
    cfg = recipe.get("strategy_min_gpus")
    if cfg is None:
        return 0
    if isinstance(cfg, int):
        return cfg
    return max(
        min_gpus_from_block(cfg, strategy_name),
        min_gpus_from_block(cfg.get(hw_id), strategy_name),
    )


def matches_constraint(hw: dict, constraint: dict | None) -> bool:
    if not constraint:
        return True
    if constraint.get("brand") and hw.get("brand") != constraint["brand"]:
        return False
    wanted_gen = constraint.get("generation")
    if wanted_gen:
        gen = hw.get("generation") or hw.get("gpu_generation")
        gens = gen if isinstance(gen, list) else [gen]
        if wanted_gen not in gens:
            return False
    return True


def is_precision_compatible(hw: dict, variant: dict) -> bool:
    constraint = variant.get("precision_hardware") or PRECISION_HARDWARE_CONSTRAINTS.get(
        variant.get("precision")
    )
    return matches_constraint(hw, constraint)


def fits_single_node(hw: dict, variant: dict) -> bool:
    """Single-node strategies cannot add VRAM, so the node must hold the weights."""
    node_vram = hw.get("vram_gb") or 0
    model_vram = variant.get("vram_minimum_gb") or 0
    if model_vram <= 0 or node_vram <= 0:
        return True
    return model_vram <= node_vram


def is_variant_hardware_supported(variant: dict, hw_id: str) -> bool:
    allowed = variant.get("supported_hardware")
    if not isinstance(allowed, list) or not allowed:
        return True
    return hw_id in allowed


def is_feature_allowed_for_strategy(feature: dict, strategy_name: str) -> bool:
    allowed = feature.get("strategies")
    if not isinstance(allowed, list) or not allowed:
        return True
    return strategy_name in allowed


def is_mode_supported(mode: dict, hw: dict, hw_id: str) -> bool:
    gate = mode.get("hardware")
    if not isinstance(gate, dict):
        return True
    gen = normalize_generation(hw.get("generation") or hw.get("gpu_generation"))
    if gen and gate.get(gen) == "unsupported":
        return False
    return gate.get(hw_id) != "unsupported"


def is_mode_allowed_for_variant(mode: dict, variant_key: str) -> bool:
    allowed = mode.get("variants")
    if not isinstance(allowed, list) or not allowed:
        return True
    return variant_key in allowed


def resolve_mode_key(
    feature: dict, feature_key: str, variant: dict, variant_key: str, hw: dict, hw_id: str
) -> str | None:
    """Which sub-mode of a single-select feature applies here (no user pick)."""
    modes = feature.get("modes")
    if not isinstance(modes, dict):
        return None
    allowed = [
        key
        for key, mode in modes.items()
        if is_mode_allowed_for_variant(mode, variant_key) and is_mode_supported(mode, hw, hw_id)
    ]
    if not allowed:
        return None
    for candidate in (
        (variant.get("default_modes") or {}).get(feature_key),
        feature.get("default_mode"),
    ):
        if candidate and candidate in allowed:
            return candidate
    return allowed[0]


def feature_args(
    recipe: dict,
    feature_key: str,
    strategy_name: str,
    variant: dict,
    variant_key: str,
    hw: dict,
    hw_id: str,
) -> list[str]:
    """Args a feature contributes for one configuration; empty when gated out."""
    feature = (recipe.get("features") or {}).get(feature_key) or {}
    if not is_feature_allowed_for_strategy(feature, strategy_name):
        return []
    if feature.get("companion", {}).get("command"):
        # A companion process has to run beside `vllm serve` on the same node;
        # the service runs one command, so the feature is not expressible.
        return []
    if isinstance(feature.get("modes"), dict):
        mode_key = resolve_mode_key(feature, feature_key, variant, variant_key, hw, hw_id)
        mode = feature["modes"].get(mode_key) if mode_key else None
        if not mode:
            return []
        override = hardware_keyed_value(mode.get("hardware_overrides"), hw, hw_id)
        if isinstance(override, dict) and override.get("args") is not None:
            return list(override["args"])
        return list(mode.get("args") or [])
    override = generation_override(feature.get("hardware_overrides"), hw, "args")
    if override is not None and override.get("args") is not None:
        return list(override["args"])
    return list(feature.get("args") or [])


def build_args(
    recipe: dict,
    variant: dict,
    variant_key: str,
    strategy: dict,
    strategy_name: str,
    hw: dict,
    hw_id: str,
) -> list[str]:
    """Base `vllm serve` args for one configuration, features excluded.

    Order (command-synthesis.js buildArgs): base_args, variant, strategy +
    parallel flag, strategy overrides, hardware overrides. Features are appended
    by the template at render time, since they are user toggles.
    """
    args: list[str] = []
    args += list((recipe.get("model") or {}).get("base_args") or [])
    args += list(variant.get("extra_args") or [])

    variant_exact = (variant.get("hardware_overrides") or {}).get(hw_id) or {}
    args += list(variant_exact.get("extra_args") or [])

    args += list(strategy.get("vllm_args") or [])
    parallel_flag = strategy.get("parallel_flag") or "--tensor-parallel-size"
    args += [parallel_flag, str(resolve_single_node_tp(recipe, variant, hw, strategy_name, hw_id))]

    overrides = (recipe.get("strategy_overrides") or {}).get(strategy_name) or {}
    args += list(overrides.get("extra_args") or [])
    args += list(overrides.get("vllm_args") or [])

    # A per-strategy generation override replaces the recipe baseline and the
    # variant delta; otherwise both apply, recipe first.
    strategy_gen = generation_override(overrides.get("hardware_overrides"), hw, "extra_args")
    if strategy_gen:
        args += list(strategy_gen.get("extra_args") or [])
    else:
        recipe_gen = generation_override(recipe.get("hardware_overrides"), hw, "extra_args")
        if recipe_gen:
            args += list(recipe_gen.get("extra_args") or [])
        variant_gen = generation_override(variant.get("hardware_overrides"), hw, "extra_args")
        if variant_gen:
            args += list(variant_gen.get("extra_args") or [])

    strategy_exact = (overrides.get("hardware_overrides") or {}).get(hw_id) or {}
    args += list(strategy_exact.get("extra_args") or [])

    return dedupe_args([a for a in args if a not in (None, "")])


def build_env(
    recipe: dict,
    variant: dict,
    strategy: dict,
    strategy_name: str,
    hw: dict,
    hw_id: str,
) -> dict[str, str]:
    """Environment for one configuration, layered like build_args."""
    env: dict[str, str] = {}
    env.update((recipe.get("model") or {}).get("base_env") or {})
    env.update(variant.get("extra_env") or {})
    env.update(((variant.get("hardware_overrides") or {}).get(hw_id) or {}).get("extra_env") or {})
    env.update(strategy.get("env") or {})

    overrides = (recipe.get("strategy_overrides") or {}).get(strategy_name) or {}
    env.update(overrides.get("env") or {})
    env.update(overrides.get("extra_env") or {})

    strategy_gen = generation_override(overrides.get("hardware_overrides"), hw, "extra_env")
    if strategy_gen:
        env.update(strategy_gen.get("extra_env") or {})
    else:
        recipe_gen = generation_override(recipe.get("hardware_overrides"), hw, "extra_env")
        if recipe_gen:
            env.update(recipe_gen.get("extra_env") or {})
        variant_gen = generation_override(variant.get("hardware_overrides"), hw, "extra_env")
        if variant_gen:
            env.update(variant_gen.get("extra_env") or {})

    strategy_exact = (overrides.get("hardware_overrides") or {}).get(hw_id) or {}
    env.update(strategy_exact.get("extra_env") or {})

    return {str(k): str(v) for k, v in env.items()}


def parse_units(args: list[str]) -> list[tuple[str, str | None]]:
    """Split an arg list into (flag, value) units so pairs stay together."""
    units: list[tuple[str, str | None]] = []
    index = 0
    while index < len(args):
        current = str(args[index])
        if current.startswith("-"):
            following = args[index + 1] if index + 1 < len(args) else None
            if following is not None and not str(following).startswith("-"):
                units.append((current, str(following)))
                index += 2
                continue
        units.append((current, None))
        index += 1
    return units


def dedupe_args(args: list[str]) -> list[str]:
    """Last occurrence of a flag wins, matching the recipes site and argparse."""
    units = parse_units(args)
    keep = [False] * len(units)
    seen: set[str] = set()
    for position in range(len(units) - 1, -1, -1):
        flag, _ = units[position]
        if not flag.startswith("-"):
            keep[position] = True
        elif flag not in seen:
            seen.add(flag)
            keep[position] = True

    out: list[str] = []
    for position, (flag, value) in enumerate(units):
        if not keep[position]:
            continue
        out.append(flag)
        if value is not None:
            out.append(value)
    return out


SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_./=:@,+%-]+$")


def shell_quote(value: str) -> str:
    if not value:
        return "''"
    if SAFE_TOKEN_RE.match(value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def arg_lines(args: list[str]) -> list[str]:
    """Pair each flag with its value on one shell line, as the recipe page does."""
    lines: list[str] = []
    index = 0
    while index < len(args):
        current = str(args[index])
        following = args[index + 1] if index + 1 < len(args) else None
        if current.startswith("-") and following is not None and not str(following).startswith("-"):
            lines.append(f"{current} {shell_quote(str(following))}")
            index += 2
        else:
            lines.append(current)
            index += 1
    return lines


def resolve_image(recipe: dict, variant: dict, hw: dict, hw_id: str) -> str:
    """Container image for a configuration (port of computeDockerMeta)."""
    brand_key = "amd" if hw.get("brand") == "AMD" else "nvidia"
    nightly = (recipe.get("model") or {}).get("nightly_required") is True

    exact = ((variant.get("hardware_overrides") or {}).get(hw_id) or {}).get("docker_image")
    if isinstance(exact, str):
        return exact

    for pin in (variant.get("docker_image"), (recipe.get("model") or {}).get("docker_image")):
        if isinstance(pin, str):
            if brand_key == "nvidia":
                return pin
            continue
        if isinstance(pin, dict):
            branded = pin.get(brand_key)
            if isinstance(branded, str):
                return branded
            if brand_key == "nvidia":
                cuda_map = branded if isinstance(branded, dict) else pin
                if isinstance(cuda_map, dict) and ("cu130" in cuda_map or "cu129" in cuda_map):
                    tag = cuda_map.get("cu130") or cuda_map.get("cu129")
                    if isinstance(tag, str):
                        return tag

    if brand_key == "amd":
        return IMAGE_AMD_NIGHTLY if nightly else IMAGE_AMD_DEFAULT
    if nightly:
        return IMAGE_NVIDIA_NIGHTLY
    version = str((recipe.get("model") or {}).get("min_vllm_version") or "")
    if RELEASE_VERSION_RE.match(version):
        return f"vllm/vllm-openai:v{version}"
    return IMAGE_NVIDIA_FALLBACK


# ── Configuration matrix ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Combo:
    """One validated (hardware, strategy, variant) configuration."""

    hw_id: str
    strategy: str
    variant: str
    model_id: str
    vendor: str
    gpus: int  # GPUs requested per replica — the strategy's parallel size
    node_gpus: int  # GPUs the hardware profile has per node
    image: str
    args: tuple[str, ...]  # shell lines, flag and value paired
    raw_args: tuple[str, ...]
    env: tuple[tuple[str, str], ...]

    @property
    def key(self) -> str:
        return f"{self.hw_id}|{self.strategy}|{self.variant}"


def single_node_strategies(catalog: Catalog, recipe: dict) -> list[str]:
    return [
        name
        for name in effective_compatible_strategies(recipe)
        if (catalog.strategies.get(name) or {}).get("deploy_type") == SINGLE_NODE_DEPLOY_TYPE
    ]


def eligible_hardware(catalog: Catalog, recipe: dict) -> list[str]:
    """Hardware profiles this recipe could run on, before variant/strategy gates."""
    declared = (recipe.get("meta") or {}).get("hardware") or {}
    out = []
    for hw_id, hw in catalog.hardware_profiles.items():
        if hw.get("brand") not in BRAND_DEVICE_VENDOR:
            continue  # no Fuzzball device key for TPU / CPU / XPU
        if hw.get("restricted") and hw_id not in declared:
            continue
        if declared.get(hw_id) == "unsupported":
            continue
        out.append(hw_id)
    return out


def build_combos(catalog: Catalog, recipe: dict) -> list[Combo]:
    combos: list[Combo] = []
    variants = recipe.get("variants") or {}
    base_model = (recipe.get("model") or {}).get("model_id") or ""
    architecture = (recipe.get("model") or {}).get("architecture")

    for hw_id in eligible_hardware(catalog, recipe):
        hw = catalog.hardware_profiles[hw_id]
        gpus = hw.get("gpu_count") if isinstance(hw.get("gpu_count"), int) else 1
        for strategy_name in single_node_strategies(catalog, recipe):
            strategy = catalog.strategies[strategy_name]
            match = strategy.get("hardware_match") or {}
            if match.get("architecture") and match["architecture"] != architecture:
                continue
            if gpus < (match.get("min_gpus") or 1):
                continue
            if not is_strategy_supported_on_hardware(recipe, strategy_name, hw, hw_id):
                continue
            if gpus < min_gpus_for_strategy(recipe, strategy_name, hw_id):
                continue
            for variant_key, variant in variants.items():
                if not isinstance(variant, dict):
                    continue
                if not is_precision_compatible(hw, variant):
                    continue
                if not is_variant_hardware_supported(variant, hw_id):
                    continue
                if not fits_single_node(hw, variant):
                    continue
                args = build_args(
                    recipe, variant, variant_key, strategy, strategy_name, hw, hw_id
                )
                env = build_env(recipe, variant, strategy, strategy_name, hw, hw_id)
                # A replica gets exactly the GPUs its parallel size shards
                # across: the resolved TP for single_node_tp (which is 1 when the
                # weights fit one GPU), the whole node for TEP/DEP.
                parallel_size = resolve_single_node_tp(
                    recipe, variant, hw, strategy_name, hw_id
                )
                combos.append(
                    Combo(
                        hw_id=hw_id,
                        strategy=strategy_name,
                        variant=variant_key,
                        model_id=variant.get("model_id") or base_model,
                        vendor=BRAND_DEVICE_VENDOR[hw["brand"]],
                        gpus=parallel_size,
                        node_gpus=gpus,
                        image=resolve_image(recipe, variant, hw, hw_id),
                        args=tuple(arg_lines(args)),
                        raw_args=tuple(args),
                        env=tuple(env.items()),
                    )
                )
    return combos


def default_hardware(catalog: Catalog, recipe: dict, combos: list[Combo]) -> str:
    """The hardware the app opens on: the recipe's pick, else Hopper, else Blackwell."""
    available = [c.hw_id for c in combos]
    declared = (recipe.get("meta") or {}).get("default_hardware")
    if declared in available:
        return declared
    for preferred in ("h200", "b200", "b300", "h100", "mi355x", "mi300x"):
        if preferred in available:
            return preferred
    return available[0]


def default_strategy(recipe: dict, combos: list[Combo], hw_id: str) -> str:
    """Serving strategy the app opens on, restricted to what this hardware offers."""
    offered = [c.strategy for c in combos if c.hw_id == hw_id]
    declared = recipe.get("default_strategy")
    if declared in offered:
        return declared
    if "single_node_tp" in offered:
        return "single_node_tp"
    return offered[0]


def default_variant(combos: list[Combo], hw_id: str, strategy: str) -> str:
    offered = [c.variant for c in combos if c.hw_id == hw_id and c.strategy == strategy]
    return "default" if "default" in offered else offered[0]


def feature_matrix(recipe: dict, catalog: Catalog, combos: list[Combo]) -> dict[str, dict[str, tuple[str, ...]]]:
    """Per-feature args for every combo, as {feature: {combo key: arg lines}}."""
    variants = recipe.get("variants") or {}
    matrix: dict[str, dict[str, tuple[str, ...]]] = {}
    for feature_key in (recipe.get("features") or {}):
        per_combo: dict[str, tuple[str, ...]] = {}
        for combo in combos:
            hw = catalog.hardware_profiles[combo.hw_id]
            variant = variants.get(combo.variant) or {}
            args = feature_args(
                recipe, feature_key, combo.strategy, variant, combo.variant, hw, combo.hw_id
            )
            # A feature often repeats a flag the configuration already sets to
            # the same value (a hardware override that pins the same parser, for
            # example). Emitting it twice changes nothing but reads as a bug.
            already_set = dict(parse_units(list(combo.raw_args)))
            kept: list[str] = []
            for flag, value in parse_units(dedupe_args(args)):
                if flag in already_set and already_set[flag] == value:
                    continue
                kept.append(flag)
                if value is not None:
                    kept.append(value)
            per_combo[combo.key] = tuple(arg_lines(kept))
        if any(per_combo.values()):
            matrix[feature_key] = per_combo
    return matrix


def default_on_features(recipe: dict, matrix: dict, hw_id: str) -> dict[str, bool]:
    """Recipe defaults: on unless listed opt-in, globally or for this hardware."""
    opt_in = set(recipe.get("opt_in_features") or [])
    opt_in.update((recipe.get("hardware_opt_in_features") or {}).get(hw_id) or [])
    return {feature: feature not in opt_in for feature in matrix}


# ── Emission helpers ─────────────────────────────────────────────────────────


def value_name(feature_key: str) -> str:
    """`tool_calling` -> `EnableToolCalling`."""
    return "Enable" + "".join(part.capitalize() for part in feature_key.split("_"))


def app_slug(repo: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", repo.lower()).strip("_")
    return f"vllm_{slug}"


def group_by_value(per_combo: dict[str, tuple[str, ...]]) -> list[tuple[tuple[str, ...], list[str]]]:
    """Collapse combos that resolve to the same lines into one branch."""
    groups: OrderedDict[tuple[str, ...], list[str]] = OrderedDict()
    for combo_key, lines in per_combo.items():
        groups.setdefault(lines, []).append(combo_key)
    return list(groups.items())


def axis_test(key: tuple[tuple[str, str], ...]) -> str:
    """One configuration key as a template test: `(and (eq $hw "b200") ...)`."""
    tests = [f'(eq {var} "{value}")' for var, value in key]
    if len(tests) == 1:
        return tests[0]
    return "(and " + " ".join(tests) + ")"


def axis_condition(
    keys: list[tuple[tuple[str, str], ...]], keyword: str, indent: str = ""
) -> str:
    """`{{- if or <test> <test> }}` over configuration keys, wrapped when long."""
    tests = [axis_test(key) for key in keys]
    if len(tests) == 1:
        return f"{indent}{{{{- {keyword} {tests[0][1:-1]} }}}}"
    body = " ".join(tests)
    if len(body) <= 100:
        return f"{indent}{{{{- {keyword} or {body} }}}}"
    wrapped = f"\n{indent}      ".join(tests)
    return f"{indent}{{{{- {keyword} or {wrapped} }}}}"


AXIS_VARS = ("$hw", "$strategy", "$variant")
AXIS_FIELDS = {"$hw": "hw_id", "$strategy": "strategy", "$variant": "variant"}
AXIS_KNOBS = {"$hw": "Hardware", "$strategy": "Strategy", "$variant": "Variant"}


@dataclass
class Matrix:
    """The configuration space of one application, for writing template tests."""

    offered: dict[str, list[str]]  # axis -> values the application accepts
    varying: list[str]  # axes with more than one value; the rest are constants
    valid: set[tuple[str, str, str]]
    invalid: set[tuple[str, str, str]]

    @classmethod
    def of(cls, combos: list["Combo"]) -> "Matrix":
        offered = {
            axis: sorted({getattr(c, AXIS_FIELDS[axis]) for c in combos}) for axis in AXIS_VARS
        }
        valid = {tuple(getattr(c, AXIS_FIELDS[axis]) for axis in AXIS_VARS) for c in combos}
        product = set(itertools.product(*(offered[axis] for axis in AXIS_VARS)))
        return cls(
            offered=offered,
            varying=[axis for axis in AXIS_VARS if len(offered[axis]) > 1],
            valid=valid,
            invalid=product - valid,
        )

    def key_of(self, combo: "Combo") -> tuple[str, str, str]:
        return tuple(getattr(combo, AXIS_FIELDS[axis]) for axis in AXIS_VARS)

    def cover(
        self, keys: set[tuple[str, str, str]], tolerate: set[tuple[str, str, str]]
    ) -> list[tuple[tuple[str, str], ...]]:
        """Describe a set of configurations with as few, as loose tests as possible.

        Prefers a one-axis test (`Variant is nvfp4`) over a two-axis one, and
        two over spelling out the triple, so a branch that really depends on the
        GPU alone reads that way. Configurations in `tolerate` may be swept in by
        a looser test: they are rejected earlier by the validity guard, so a test
        that also matches them can never fire for them.
        """
        product = set(itertools.product(*(self.offered[axis] for axis in AXIS_VARS)))
        remaining = set(keys)
        conditions: list[tuple[tuple[str, str], ...]] = []
        for size in (1, 2, 3):
            for subset in itertools.combinations(range(len(AXIS_VARS)), size):
                for values in itertools.product(*(self.offered[AXIS_VARS[i]] for i in subset)):
                    assignment = dict(zip(subset, values))
                    matching = {
                        candidate
                        for candidate in product
                        if all(candidate[i] == value for i, value in assignment.items())
                    }
                    if not (matching & remaining) or not matching <= (remaining | tolerate):
                        continue
                    conditions.append(
                        tuple(
                            (AXIS_VARS[i], assignment[i])
                            for i in sorted(assignment)
                            if AXIS_VARS[i] in self.varying
                        )
                    )
                    remaining -= matching
            if not remaining:
                break
        return conditions


def emit_matrix_chain(
    add,
    mapping: dict[tuple[str, str, str], Any],
    matrix: Matrix,
    render_line,
    complete: bool,
) -> None:
    """Emit one `if / else if` chain keyed by configuration.

    Groups that resolve to nothing are dropped. When `complete` (every valid
    configuration is in some group) the largest group becomes the `else` branch
    rather than spelling out its configurations, and a single group needs no
    conditional at all.
    """
    groups = [(value, keys) for value, keys in group_by_value(mapping) if value]
    if not groups:
        return
    covered = sum(len(keys) for _, keys in groups)
    fallback = None
    if complete and covered == len(matrix.valid):
        fallback = max(groups, key=lambda group: len(group[1]))
        groups = [group for group in groups if group is not fallback]

    emitted = False
    for value, keys in groups:
        conditions = matrix.cover(set(keys), matrix.invalid)
        if any(not condition for condition in conditions):
            # Holds for every configuration: no test to write.
            fallback = (value, keys)
            continue
        add(axis_condition(conditions, "if" if not emitted else "else if"))
        emitted = True
        for line in render_line(value):
            add(line)
    if fallback is not None:
        if emitted:
            add("{{- else }}")
        for line in render_line(fallback[0]):
            add(line)
    if emitted:
        add("{{- end }}")


def yaml_single_quote(value: str) -> str:
    return value.replace("'", "''")


def wrap(text: str, width: int = 74, indent: str = "      ") -> str:
    """Fold a display_name onto continuation lines for values.yaml."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return f"\n{indent}".join(lines)


# ── template.yaml ────────────────────────────────────────────────────────────


def render_template(
    recipe: dict,
    catalog: Catalog,
    combos: list[Combo],
    matrix: dict,
    source: str,
    multi_variant: bool,
    multi_strategy: bool,
    multi_hardware: bool,
) -> str:
    served_model = (recipe.get("model") or {}).get("model_id") or ""
    out: list[str] = []
    add = out.append

    add("# Copyright 2026 CIQ, Inc. All rights reserved.")
    add("#")
    add(f"# Generated from the vLLM recipe {source} by scripts/gen_models.py.")
    add("# Edit the recipe or the generator, not this file.")
    add("")
    add("{{- /*")
    add("  Hardware profile, serving strategy and checkpoint variant together select")
    add("  one configuration validated by the recipe. Every vLLM flag, environment")
    add("  variable, GPU count and container image below comes from that recipe.")
    add("*/}}")
    if multi_hardware:
        add("{{- $hw := .Hardware | trim | lower }}")
    else:
        add(f'{{{{- $hw := "{combos[0].hw_id}" }}}}')
    if multi_strategy:
        add("{{- $strategy := .Strategy | trim | lower }}")
    else:
        add(f'{{{{- $strategy := "{combos[0].strategy}" }}}}')
    if multi_variant:
        add("{{- $variant := .Variant | trim | lower }}")
    else:
        add(f'{{{{- $variant := "{combos[0].variant}" }}}}')
    add("")

    matrix_space = Matrix.of(combos)

    # Each knob must name something the recipe offers, and the three together
    # must be a crossing it validated.
    for axis in matrix_space.varying:
        allowed = " ".join(f'(eq {axis} "{value}")' for value in matrix_space.offered[axis])
        add(f"{{{{- if not (or {allowed}) }}}}")
        add(
            f'  {{{{- fail (printf "unsupported {AXIS_KNOBS[axis]} %q. This '
            f'application supports: {", ".join(matrix_space.offered[axis])}" {axis}) }}}}'
        )
        add("{{- end }}")
    # Crossings that are never valid, one guard per shape of crossing so a
    # precision missing from several GPUs is a single test.
    by_shape: OrderedDict[tuple[str, ...], list] = OrderedDict()
    for condition in matrix_space.cover(matrix_space.invalid, tolerate=set()):
        if condition:
            by_shape.setdefault(tuple(axis for axis, _ in condition), []).append(condition)
    for shape, conditions in by_shape.items():
        add(axis_condition(conditions, "if"))
        described = " with ".join(f"{AXIS_KNOBS[axis]} %q" for axis in shape)
        arguments = " ".join(shape)
        add(
            f'  {{{{- fail (printf "{described} is not a configuration this recipe '
            f'validated. See the supported matrix in the application description" '
            f"{arguments}) }}}}"
        )
        add("{{- end }}")
    add("")

    # Checkpoint, device vendor, GPU count and image. Declared before the
    # branches, because a variable declared inside one is scoped to it.
    add('{{- $model := "" }}')
    add('{{- $vendor := "" }}')
    add("{{- $gpus := 0 }}")
    add('{{- $image := "" }}')
    for mapping, render in (
        (
            {matrix_space.key_of(c): c.model_id for c in combos},
            lambda model_id: [f'{{{{- $model = "{model_id}" }}}}'],
        ),
        (
            {matrix_space.key_of(c): c.vendor for c in combos},
            lambda vendor: [f'{{{{- $vendor = "{vendor}" }}}}'],
        ),
        (
            {matrix_space.key_of(c): c.gpus for c in combos},
            lambda gpus: [f"{{{{- $gpus = {gpus} }}}}"],
        ),
        (
            {matrix_space.key_of(c): (c.image, c.vendor) for c in combos},
            lambda payload: [
                '{{- $image = default "docker://%s" (trim %s) }}'
                % (payload[0], ".VllmImageROCm" if payload[1] == "amd.com" else ".VllmImage")
            ],
        ),
    ):
        emit_matrix_chain(add, mapping, matrix_space, render, complete=True)
    add("")

    add("{{- $proxy := .EnableProxy }}")
    add("{{- $scope := .ServiceScope | trim | lower }}")
    add("{{- $api_key := .ServerApiKey | trim }}")
    add('{{- if and (eq $scope "public") (not $api_key) }}')
    add('  {{- fail "ServerApiKey is required when ServiceScope is public" }}')
    add("{{- end }}")
    add("")
    add("{{- $min_replicas := .MinReplicas }}")
    add("{{- $max_replicas := .MaxReplicas }}")
    add("{{- if lt $max_replicas 1 }}")
    add('  {{- fail "MaxReplicas must be at least 1" }}')
    add("{{- end }}")
    add("{{- if lt $max_replicas $min_replicas }}")
    add('  {{- fail "MaxReplicas must be greater than or equal to MinReplicas" }}')
    add("{{- end }}")
    add("{{- if and (not $proxy) (lt $min_replicas 1) }}")
    add(
        '  {{- fail "MinReplicas must be at least 1 when EnableProxy is false: '
        "without an in-workflow proxy nothing observes requests against an idle "
        'pool, so the first replica cannot be scaled up on demand" }}'
    )
    add("{{- end }}")
    add("")
    add("{{- $gpu_model := trim .GPUModel }}")
    add("{{- $vllm_port := randInt 10000 24000 }}")
    add("{{- $proxy_port := randInt 24001 32000 }}")
    add("")
    add('{{- $data_mount := "/data" }}')
    add("{{- $hf_cache := trim .HuggingfaceCache }}")
    add(
        '{{- if not (or (eq $hf_cache $data_mount) (hasPrefix (printf "%s/" $data_mount) '
        "$hf_cache)) }}"
    )
    add(
        "  {{- fail (printf \"HuggingfaceCache must be an absolute path under the "
        'mounted volume %s so the cache persists" $data_mount) }}'
    )
    add("{{- end }}")
    add("")
    add("{{- /*")
    add("  With the proxy in front, the vLLM API key never leaves the workflow, so one")
    add("  is generated when the caller supplied none. Without the proxy, callers talk")
    add("  to vLLM directly and can only present a key they already know.")
    add("*/}}")
    add("{{- $vllm_key := $api_key }}")
    add("{{- if and $proxy (not $vllm_key) }}")
    add('  {{- $vllm_key = randInt 0 10000000 | printf "%08d" | b64enc }}')
    add("{{- end }}")
    add("")
    add("{{- /*")
    add("  Replicas of an autoscaled service share one DNS record that tracks the")
    add("  currently ready replicas and stays valid while the pool sits at zero.")
    add("*/}}")
    add('{{- $pool_base := printf "http://vllm.autoscaler:%d/v1" $vllm_port }}')
    add("")
    add("version: v4")
    add("")
    add("volumes:")
    add("  data:")
    add("    reference: {{ trim .ModelVolume }}")
    add("")
    add("services:")
    add("  vllm:")
    add("    image:")
    add("      uri: {{ $image }}")
    add("    mounts:")
    add("      {{ $data_mount }}:")
    add("        volume: data")
    add("    network:")
    add("      ports:")
    add("        - name: openai-api")
    add("          port: {{ $vllm_port }}")
    add("          protocol: tcp")
    add("{{- if not $proxy }}")
    add("      endpoints:")
    add("        - name: openai")
    add("          port-name: openai-api")
    add("          protocol: http")
    add("          type: subdomain")
    add("          scope: {{ $scope }}")
    add("{{- end }}")
    add("    resource:")
    add("      cpu:")
    add("        cores: {{ .ServerCores }}")
    add("      memory:")
    add("        size: {{ trim .ServerMemory }}")
    add("      devices:")
    add("        {{ $vendor }}/gpu: {{ $gpus }}")
    add("{{- if $gpu_model }}")
    add("      annotations:")
    add('        {{ $vendor }}/gpu.model: "{{ $gpu_model }}"')
    add("{{- end }}")
    add("    env:")
    add("      - HF_HOME={{ $hf_cache }}")
    add("{{- if trim .HuggingFaceHubToken }}")
    add("      - HF_TOKEN={{ trim .HuggingFaceHubToken }}")
    add("{{- end }}")
    add("{{- if $vllm_key }}")
    add("      - VLLM_API_KEY={{ $vllm_key }}")
    add("{{- end }}")

    # Recipe environment, per configuration.
    env_mapping = {
        matrix_space.key_of(c): tuple(f"{k}={v}" for k, v in c.env) for c in combos
    }
    if any(env_mapping.values()):
        add("{{- /* Environment pinned by the recipe for this configuration. */}}")
        emit_matrix_chain(
            add,
            env_mapping,
            matrix_space,
            lambda lines: [f"      - '{yaml_single_quote(line)}'" for line in lines],
            complete=False,
        )

    add("    autoscaler:")
    add("      replicas:")
    add("        min: {{ $min_replicas }}")
    add("        max: {{ $max_replicas }}")
    add("      metrics:")
    add("        enabled: true")
    add("        path: /metrics")
    add("        port: {{ $vllm_port }}")
    add("        interval: {{ .MetricsIntervalSeconds }}")
    add("{{- if not $proxy }}")
    add("      scale-up:")
    add("        triggers:")
    add("          # Queued requests on any replica grow the pool toward MaxReplicas.")
    add(
        "          - metrics-query: 'max(vllm:num_requests_waiting) >= bool "
        "{{ .ScaleUpPendingRequests }}'"
    )
    add("            cooldown-period: {{ .ScaleUpCooldownSeconds }}")
    add("{{- end }}")
    add("      scale-down:")
    add("        # Retire a replica only once no replica is serving a request, so")
    add("        # generations in flight run to completion instead of being cut off.")
    add("        metrics-query: 'max(vllm:num_requests_running) == bool 0'")
    add("        cooldown-period: {{ .ScaleDownCooldownSeconds }}")
    add("{{- if not $proxy }}")
    add("    persist: true")
    add("{{- end }}")
    add("    script: |")
    add("      #!/bin/sh")
    add("      set -e")
    add('      mkdir -p "$HF_HOME"')
    add('      exec vllm serve "{{ $model }}" \\')
    add("        --host 0.0.0.0 \\")
    add("        --port {{ $vllm_port }} \\")

    def serve_lines(lines: tuple[str, ...]) -> list[str]:
        return [f"        {line} \\" for line in lines]

    emit_matrix_chain(
        add,
        {matrix_space.key_of(c): c.args for c in combos},
        matrix_space,
        serve_lines,
        complete=True,
    )

    for feature_key, per_combo in matrix.items():
        add(f"{{{{- if .{value_name(feature_key)} }}}}")
        emit_matrix_chain(
            add,
            {matrix_space.key_of(c): per_combo[c.key] for c in combos},
            matrix_space,
            serve_lines,
            complete=False,
        )
        add("{{- end }}")

    add("{{- if gt .MaxModelLen 0 }}")
    add("        --max-model-len {{ .MaxModelLen }} \\")
    add("{{- end }}")
    add("{{- if trim .ExtraVllmArgs }}")
    add("        {{ trim .ExtraVllmArgs }} \\")
    add("{{- end }}")
    add("        {{- /* Stable client-facing name, whatever variant is served. */}}")
    add(f"        --served-model-name {served_model}")
    add("    readiness-probe:")
    add("      http-get:")
    add("        path: /health")
    add("        port: {{ $vllm_port }}")
    add("        scheme: http")
    add("      initial-delay-seconds: 60")
    add("      period-seconds: 30")
    add("      failure-threshold: {{ .ReadinessFailureThreshold }}")
    add("      success-threshold: 1")
    add("")
    add("{{- if $proxy }}")
    add("")
    add("  litellm:")
    add("    # No depends-on: the proxy must answer while the pool sits at zero")
    add("    # replicas, because that request is what wakes the pool.")
    add("    image:")
    add("      uri: {{ trim .LiteLLMImage }}")
    add("    persist: true")
    add("    network:")
    add("      ports:")
    add("        - name: openai-api")
    add("          port: {{ $proxy_port }}")
    add("          protocol: tcp")
    add("      endpoints:")
    add("        - name: openai")
    add("          port-name: openai-api")
    add("          protocol: http")
    add("          type: subdomain")
    add("          scope: {{ $scope }}")
    add("    resource:")
    add("      cpu:")
    add("        cores: {{ .ProxyCores }}")
    add("      memory:")
    add("        size: {{ trim .ProxyMemory }}")
    add("    env:")
    add("      - VLLM_API_KEY={{ $vllm_key }}")
    add("{{- if $api_key }}")
    add("      - LITELLM_MASTER_KEY={{ $api_key }}")
    add("{{- end }}")
    add("    files:")
    add("      /etc/litellm/config.yaml: |")
    add("        model_list:")
    add(f"          - model_name: {served_model}")
    add("            litellm_params:")
    add(f"              model: openai/{served_model}")
    add("              api_base: {{ $pool_base }}")
    add("              api_key: os.environ/VLLM_API_KEY")
    add("        litellm_settings:")
    add('          callbacks: ["prometheus"]')
    add("          # The autoscaler scrapes /metrics without credentials.")
    add("          require_auth_for_metrics_endpoint: false")
    add("          num_retries: {{ .ProxyRetries }}")
    add("          request_timeout: {{ .ProxyRequestTimeoutSeconds }}")
    add("    autoscaler:")
    add("      # A cross-service scaling source: it owns no replicas and only")
    add("      # drives the vllm pool.")
    add("      metrics:")
    add("        enabled: true")
    add("        path: /metrics")
    add("        port: {{ $proxy_port }}")
    add("        interval: {{ .MetricsIntervalSeconds }}")
    add("      scale-up:")
    add("        triggers:")
    add("          # Any request arriving at the proxy wakes the first replica, the")
    add("          # only signal available while the pool is idle at zero.")
    add(
        "          - metrics-query: 'sum(rate(litellm_proxy_total_requests_metric_total"
        "[1m])) > bool 0'"
    )
    add("            cooldown-period: {{ .ActivationCooldownSeconds }}")
    add("            services: [vllm]")
    add("          # Once replicas are up, their own queue depth grows the pool.")
    add(
        "          - metrics-query: 'max(vllm:num_requests_waiting) >= bool "
        "{{ .ScaleUpPendingRequests }}'"
    )
    add("            cooldown-period: {{ .ScaleUpCooldownSeconds }}")
    add("            services: [vllm]")
    add("    script: |")
    add("      #!/bin/sh")
    add("      exec litellm \\")
    add("        --config /etc/litellm/config.yaml \\")
    add("        --host 0.0.0.0 \\")
    add("        --port {{ $proxy_port }}")
    add("    readiness-probe:")
    add("      http-get:")
    add("        path: /health/liveliness")
    add("        port: {{ $proxy_port }}")
    add("        scheme: http")
    add("      initial-delay-seconds: 15")
    add("      period-seconds: 15")
    add("      failure-threshold: 20")
    add("      success-threshold: 1")
    add("{{- end }}")
    return "\n".join(out) + "\n"


# ── values.yaml ──────────────────────────────────────────────────────────────


def render_values(
    recipe: dict,
    catalog: Catalog,
    combos: list[Combo],
    matrix: dict,
    source: str,
    defaults: dict,
) -> str:
    hw_ids = sorted({c.hw_id for c in combos})
    strategies = sorted({c.strategy for c in combos})
    variants = sorted({c.variant for c in combos})
    hw_default = defaults["hardware"]
    gpus = next(
        c.gpus
        for c in combos
        if c.hw_id == hw_default
        and c.strategy == defaults["strategy"]
        and c.variant == defaults["variant"]
    )
    context_length = (recipe.get("model") or {}).get("context_length")

    out: list[str] = []
    add = out.append
    add(f"# Generated from the vLLM recipe {source} by scripts/gen_models.py.")
    add("# Edit the recipe or the generator, not this file.")
    add("values:")

    def entry(name: str, display: str, *, category: str, body: list[str]) -> None:
        add(f"  - name: {name}")
        add("    display_name: >-")
        add(f"      {wrap(display)}")
        for line in body:
            add(f"    {line}")
        add(f"    display_category: {category}")

    if len(variants) > 1:
        described = []
        for key in variants:
            variant = (recipe.get("variants") or {}).get(key) or {}
            precision = variant.get("precision") or "?"
            described.append(f"{key} ({precision})")
        entry(
            "Variant",
            "Checkpoint variant to serve. Each pins its own precision, weights "
            f"and flags: {', '.join(described)}.",
            category="Model Configuration",
            body=[
                f'string_value: "{defaults["variant"]}"',
                "options_input:",
                f"  options: [{', '.join(variants)}]",
            ],
        )

    entry(
        "MaxModelLen",
        "Maximum context length, in tokens. 0 keeps the length the recipe "
        f"validated for the selected configuration. Model maximum: {context_length}."
        if context_length
        else "Maximum context length, in tokens. 0 keeps the recipe default.",
        category="Model Configuration",
        body=["uint_value: 0"],
    )
    entry(
        "HuggingFaceHubToken",
        "HuggingFace Hub token. Required for gated checkpoints.",
        category="Model Configuration",
        body=['string_value: ""'],
    )
    entry(
        "ExtraVllmArgs",
        "Extra flags appended to the vllm serve command. Appended last, so they "
        "override the recipe's own flags. For expert tuning only.",
        category="Model Configuration",
        body=['string_value: ""'],
    )

    for feature_key in matrix:
        feature = (recipe.get("features") or {}).get(feature_key) or {}
        description = (feature.get("description") or feature_key).strip()
        modes = feature.get("modes")
        if isinstance(modes, dict):
            description += (
                " The recipe's default method is used"
                f" ({', '.join(modes)} are defined upstream)."
            )
        entry(
            value_name(feature_key),
            description,
            category="Model Features",
            body=[f"bool_value: {str(defaults['features'][feature_key]).lower()}"],
        )

    if len(hw_ids) > 1:
        described = []
        for hw_id in hw_ids:
            hw = catalog.hardware_profiles[hw_id]
            verified = ((recipe.get("meta") or {}).get("hardware") or {}).get(hw_id)
            mark = ", verified" if verified == "verified" else ""
            requested = sorted({c.gpus for c in combos if c.hw_id == hw_id})
            gpus_text = "/".join(str(n) for n in requested)
            described.append(
                f"{hw_id} ({hw.get('display_name')}, {gpus_text} GPU(s) per replica{mark})"
            )
        entry(
            "Hardware",
            "GPU node profile to deploy on. Selects the GPU vendor, how many GPUs "
            "each replica requests, the container image and the recipe's tuning "
            f"for that hardware: {', '.join(described)}.",
            category="Resources",
            body=[
                f'string_value: "{hw_default}"',
                "options_input:",
                f"  options: [{', '.join(hw_ids)}]",
            ],
        )

    if len(strategies) > 1:
        described = []
        for name in strategies:
            strategy = catalog.strategies[name]
            described.append(f"{name} ({strategy.get('display_name')})")
        entry(
            "Strategy",
            "Parallelism strategy for each replica. All GPUs of the node are used "
            f"either way: {', '.join(described)}.",
            category="Resources",
            body=[
                f'string_value: "{defaults["strategy"]}"',
                "options_input:",
                f"  options: [{', '.join(strategies)}]",
            ],
        )

    entry(
        "GPUModel",
        "Exact GPU model to request for each replica (for example NVIDIA H200). "
        "Leave empty to accept any GPU of the selected vendor.",
        category="Resources",
        body=['string_value: ""'],
    )
    entry(
        "ServerCores",
        f"CPU cores per vLLM replica. Default sized for {gpus} GPU(s) per replica.",
        category="Resources",
        body=[f"uint_value: {defaults['cores']}"],
    )
    entry(
        "ServerMemory",
        "Host memory per vLLM replica. Weight loading and the KV cache manager "
        "need headroom beyond the GPUs.",
        category="Resources",
        body=[f"string_value: {defaults['memory']}"],
    )
    entry(
        "ProxyCores",
        "CPU cores for the LiteLLM proxy.",
        category="Resources",
        body=["uint_value: 2"],
    )
    entry(
        "ProxyMemory",
        "Memory for the LiteLLM proxy.",
        category="Resources",
        body=["string_value: 4GiB"],
    )

    entry(
        "MinReplicas",
        "Minimum number of vLLM replicas. Set to 0 to release all GPUs while the "
        "pool is idle; the first request through the proxy then pays a cold "
        "start. Must be at least 1 when EnableProxy is false.",
        category="Scaling",
        body=["uint_value: 1"],
    )
    entry(
        "MaxReplicas",
        f"Maximum number of vLLM replicas. Each replica holds {gpus} GPU(s), and "
        "capacity for this many replicas is pre-allocated when the workflow starts.",
        category="Scaling",
        body=[f"uint_value: {defaults['max_replicas']}"],
    )
    entry(
        "ScaleUpPendingRequests",
        "Queued requests on a replica that trigger adding another replica.",
        category="Scaling",
        body=["uint_value: 2"],
    )
    entry(
        "ScaleUpCooldownSeconds",
        "Seconds to wait between successive scale-up decisions.",
        category="Scaling",
        body=["uint_value: 60"],
    )
    entry(
        "ActivationCooldownSeconds",
        "Seconds to wait between activations of an idle pool. Only used when "
        "EnableProxy is true.",
        category="Scaling",
        body=["uint_value: 30"],
    )
    entry(
        "ScaleDownCooldownSeconds",
        "Seconds an idle pool must stay idle before a replica is retired. Acts as "
        "the drain window for requests in flight.",
        category="Scaling",
        body=["uint_value: 300"],
    )
    entry(
        "MetricsIntervalSeconds",
        "How often the autoscaler scrapes service metrics.",
        category="Scaling",
        body=["uint_value: 15"],
    )
    entry(
        "ReadinessFailureThreshold",
        "Failed readiness probes tolerated before a replica is considered dead. "
        "Probes run every 30 seconds after a 60 second delay, so this is the "
        f"weight download and load budget (default about {defaults['readiness'] // 2} "
        "minutes).",
        category="Scaling",
        body=[f"uint_value: {defaults['readiness']}"],
    )

    entry(
        "EnableProxy",
        "Run a LiteLLM proxy in the workflow to hold the endpoint and front the "
        "pool. When false, the pool itself holds the endpoint for discovery by an "
        "external LiteLLM instance.",
        category="Access",
        body=[f"bool_value: {str(defaults['proxy']).lower()}"],
    )
    entry(
        "ServiceScope",
        "Who can access the OpenAI-compatible endpoint.",
        category="Access",
        body=[
            'string_value: "group"',
            "options_input:",
            "  options: [user, group, organization, public]",
        ],
    )
    entry(
        "ServerApiKey",
        "API key callers present to the OpenAI-compatible endpoint. Required when "
        "ServiceScope is public. When empty and EnableProxy is true, an internal "
        "key is generated for proxy-to-pool traffic only.",
        category="Access",
        body=['string_value: ""'],
    )

    entry(
        "ProxyRetries",
        "Times the proxy retries a failed request against the pool before "
        "returning an error.",
        category="Proxy Behavior",
        body=["uint_value: 2"],
    )
    entry(
        "ProxyRequestTimeoutSeconds",
        "Seconds the proxy waits for a response from a replica. Must exceed the "
        "longest expected generation.",
        category="Proxy Behavior",
        body=["uint_value: 600"],
    )

    entry(
        "ModelVolume",
        "Volume holding the HuggingFace model cache, mounted at /data on every "
        "replica. The default is ephemeral; use a persistent volume so replicas "
        "added during scale-up do not re-download the weights.",
        category="Storage",
        body=["string_value: volume://user/ephemeral"],
    )
    entry(
        "HuggingfaceCache",
        "HuggingFace home directory where weights are cached. Must be a path "
        "under /data.",
        category="Storage",
        body=['string_value: "/data/.cache/huggingface"'],
    )

    nvidia_images = sorted({c.image for c in combos if c.vendor == "nvidia.com"})
    amd_images = sorted({c.image for c in combos if c.vendor == "amd.com"})
    entry(
        "VllmImage",
        "Container image override for NVIDIA hardware, including the docker:// "
        "scheme. Leave empty for the image this application ships: "
        f"{', '.join(nvidia_images) if nvidia_images else 'no NVIDIA configuration'}.",
        category="Versions",
        body=['string_value: ""'],
    )
    entry(
        "VllmImageROCm",
        "Container image override for AMD hardware, including the docker:// "
        "scheme. Leave empty for the image this application ships: "
        f"{', '.join(amd_images) if amd_images else 'no AMD configuration'}.",
        category="Versions",
        body=['string_value: ""'],
    )
    entry(
        "LiteLLMImage",
        "LiteLLM container image used for the in-workflow proxy.",
        category="Versions",
        body=[f"string_value: docker://{LITELLM_IMAGE}"],
    )
    return "\n".join(out) + "\n"


# ── metadata.md ──────────────────────────────────────────────────────────────


def render_metadata(
    recipe: dict,
    catalog: Catalog,
    combos: list[Combo],
    matrix: dict,
    source: str,
    org: str,
    repo: str,
    slug: str,
    defaults: dict,
) -> str:
    meta = recipe.get("meta") or {}
    model = recipe.get("model") or {}
    hw_ids = sorted({c.hw_id for c in combos})
    strategies = sorted({c.strategy for c in combos})
    variants = sorted({c.variant for c in combos})
    recipe_url = f"https://recipes.vllm.ai/{org}/{repo}"
    default_combo = next(
        c
        for c in combos
        if c.hw_id == defaults["hardware"]
        and c.strategy == defaults["strategy"]
        and c.variant == defaults["variant"]
    )

    tags = ["LLM", "inference", "vllm", "autoscaling"]
    for task in meta.get("tasks") or []:
        if task not in tags:
            tags.append(str(task))
    provider = str(meta.get("provider") or "").strip()
    if provider:
        tags.append(provider)

    out: list[str] = []
    add = out.append

    def add_para(text: str, bullet: str = "") -> None:
        """Append prose wrapped at 80 columns, indenting bullet continuations."""
        body = " ".join(text.split())
        first_indent = bullet
        rest_indent = " " * len(bullet)
        line = first_indent
        for word in body.split(" "):
            candidate = f"{line} {word}" if line.strip() else f"{line}{word}"
            if line.strip() and len(candidate) > 79:
                add(line)
                line = f"{rest_indent}{word}"
            else:
                line = candidate
        if line.strip():
            add(line)

    add("# Copyright 2026 CIQ, Inc. All rights reserved.")
    add("---")
    add(f'id: "ciq/ml_and_ai/{slug}"')
    add(f'name: "vLLM {repo}"')
    add('category: "ML_AND_AI"')
    add("tags:")
    for tag in tags:
        add(f"- {tag}")
    add("---")
    add("")
    add_para(
        f"Serves [`{model.get('model_id')}`]({recipe_url}) from an autoscaled pool "
        "of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) replicas behind a "
        "single OpenAI-compatible base URL. Deployment parameters come from the "
        f"[vLLM recipe for {meta.get('title')}]({recipe_url}): every vLLM flag, "
        "environment variable, container image, GPU count and parallel layout "
        "below is what that recipe validated for the selected hardware."
    )
    add("")
    add_para(str(meta.get("description") or ""))
    add("")
    add("## Model")
    add("")
    add(f"- **Checkpoint**: `{model.get('model_id')}`")
    add(f"- **Architecture**: {model.get('architecture')}, {model.get('parameter_count')} parameters")
    if model.get("active_parameters"):
        add(f"- **Active parameters**: {model.get('active_parameters')}")
    if model.get("context_length"):
        add(f"- **Context length**: {model.get('context_length')} tokens")
    add(f"- **Minimum vLLM version**: {model.get('min_vllm_version')}")
    add(f"- **Recipe difficulty**: {meta.get('difficulty')}")
    add("")
    add("## Supported hardware")
    add("")
    add("| Hardware | Node | GPUs per replica | Recipe status |")
    add("| --- | --- | --- | --- |")
    for hw_id in hw_ids:
        hw = catalog.hardware_profiles[hw_id]
        status = (meta.get("hardware") or {}).get(hw_id) or "untested upstream"
        requested = sorted({c.gpus for c in combos if c.hw_id == hw_id})
        add(
            f"| `{hw_id}` | {hw.get('gpu_count')}x {hw.get('display_name')}, "
            f"{hw.get('vram_gb')} GB | {'/'.join(str(n) for n in requested)} "
            f"| {status} |"
        )
    add("")
    add_para(
        "A replica requests exactly the GPUs its parallel size shards across, so "
        "one GPU is requested where the weights fit one GPU. Hardware the recipe "
        "marks `unsupported`, hardware that cannot hold the weights on one node, "
        "and profiles with no Fuzzball device key (TPU, CPU, Intel XPU) are not "
        "offered."
    )
    add("")
    if len(variants) > 1:
        add("## Variants")
        add("")
        add("| Variant | Precision | Minimum VRAM | Checkpoint |")
        add("| --- | --- | --- | --- |")
        for key in variants:
            variant = (recipe.get("variants") or {}).get(key) or {}
            add(
                f"| `{key}` | {variant.get('precision')} | "
                f"{variant.get('vram_minimum_gb')} GB | "
                f"`{variant.get('model_id') or model.get('model_id')}` |"
            )
        add("")
    if len(strategies) > 1:
        add("## Serving strategies")
        add("")
        for name in strategies:
            strategy = catalog.strategies[name]
            description = str(strategy.get("description") or "")
            add_para(
                f"**`{name}`** ({strategy.get('display_name')}): {description}",
                bullet="- ",
            )
        add("")
    if matrix:
        add("## Features")
        add("")
        for feature_key in matrix:
            feature = (recipe.get("features") or {}).get(feature_key) or {}
            state = "on" if defaults["features"][feature_key] else "off"
            description = str(feature.get("description") or "")
            add_para(
                f"**`{value_name(feature_key)}`** (default {state}): {description}",
                bullet="- ",
            )
        add("")
    add("## Usage")
    add("")
    add("```sh")
    add(f"fuzzball workflow catalog start {slug}")
    knobs = []
    if len({c.hw_id for c in combos}) > 1:
        knobs.append(f"Hardware={hw_ids[-1]}")
    if len(strategies) > 1:
        knobs.append(f"Strategy={strategies[-1]}")
    if len(variants) > 1:
        knobs.append(f"Variant={variants[-1]}")
    if knobs:
        add(f"fuzzball workflow catalog start {slug} --values {','.join(knobs)}")
    add(
        f"fuzzball workflow catalog start {slug} --values "
        "ModelVolume=volume://user/models,MaxReplicas=4"
    )
    add("```")
    add("")
    add_para(
        "Clients address the model as "
        f"`{model.get('model_id')}` regardless of the variant served, because the "
        "service pins `--served-model-name`. Gated checkpoints need "
        "`HuggingFaceHubToken`. Non-public endpoints need a bearer token from "
        "`fuzzball workflow endpoints generate-token`."
    )
    add("")
    add("## Default configuration")
    add("")
    add_para(
        f"`Hardware={default_combo.hw_id}`, `Strategy={default_combo.strategy}`, "
        f"`Variant={default_combo.variant}` requests {default_combo.gpus} GPU(s) "
        "per replica and renders:"
    )
    add("")
    add("```sh")
    add(f"vllm serve {default_combo.model_id} \\")
    for line in default_combo.args:
        add(f"  {line} \\")
    for feature_key, per_combo in matrix.items():
        if not defaults["features"][feature_key]:
            continue
        for line in per_combo.get(default_combo.key, ()):
            add(f"  {line} \\")
    add(f"  --served-model-name {model.get('model_id')}")
    add("```")
    add("")
    if default_combo.env:
        add("With environment:")
        add("")
        add("```sh")
        for key, value in default_combo.env:
            add(f"{key}={value}")
        add("```")
        add("")
    add(f"Image: `docker://{default_combo.image}`")
    add("")
    add("## Services")
    add("")
    add_para(
        "**vllm**: the replica pool. Every replica serves the same model on the "
        "same port and reports Prometheus metrics there. Replicas share one "
        "autoscaler DNS record that tracks only replicas past their readiness "
        "probe, so a client never sees a replica still loading weights.",
        bullet="- ",
    )
    add_para(
        "**litellm**: the proxy, present when `EnableProxy` is true. It holds the "
        "endpoint, exposes `/v1` OpenAI-compatible routes, and is the workflow's "
        "cross-service scaling source. It declares no `depends-on`, because it "
        "must answer requests while the pool holds zero replicas.",
        bullet="- ",
    )
    add("")
    add("## Notes and limitations")
    add("")
    add_para(
        "Only single-node serving strategies are offered. A Fuzzball service is "
        "one container on one node, so the recipe's multi-node strategies "
        "(`multi_node_*`, `pd_cluster`) are not generated.",
        bullet="- ",
    )
    add_para(
        "Use a persistent `ModelVolume`. On the default ephemeral volume every "
        "replica added during scale-up re-downloads the weights, which dominates "
        "cold-start time.",
        bullet="- ",
    )
    add_para(
        "`ReadinessFailureThreshold` is the weight download budget. Large "
        "checkpoints on a cold cache need it raised, not the initial delay.",
        bullet="- ",
    )
    add_para(
        "The autoscaler has no drain setting. The "
        "`max(vllm:num_requests_running) == bool 0` scale-down condition plus "
        "`ScaleDownCooldownSeconds` is the drain window; size it to cover the "
        "longest expected streaming generation.",
        bullet="- ",
    )
    dependencies = recipe.get("dependencies") or []
    if dependencies:
        add_para(
            "The recipe lists extra install steps that apply to its pip install "
            "path; the container image used here already carries them:",
            bullet="- ",
        )
        for dependency in dependencies:
            command = " ".join(str(dependency.get("command") or "").split())
            add_para(f"`{command}`", bullet="  - ")
    add_para(
        f"Deployment parameters track the recipe at {recipe_url}. Regenerate this "
        "application with `scripts/gen_models.py` after the recipe changes.",
        bullet="- ",
    )
    return "\n".join(out) + "\n"


# ── Driver ───────────────────────────────────────────────────────────────────


def compute_defaults(
    recipe: dict, catalog: Catalog, combos: list[Combo], matrix: dict
) -> dict:
    hardware = default_hardware(catalog, recipe, combos)
    strategy = default_strategy(recipe, combos, hardware)
    variant = default_variant(combos, hardware, strategy)
    gpus = next(
        c.gpus
        for c in combos
        if c.hw_id == hardware and c.strategy == strategy and c.variant == variant
    )
    vram = max(
        (v.get("vram_minimum_gb") or 0)
        for v in (recipe.get("variants") or {}).values()
        if isinstance(v, dict)
    )
    # Weight download and load dominate startup; probes run every 30s.
    readiness_minutes = 60 if vram < 500 else 180
    return {
        "hardware": hardware,
        "strategy": strategy,
        "variant": variant,
        "features": default_on_features(recipe, matrix, hardware),
        "cores": min(max(8 * gpus, 8), 64),
        # Host memory covers weight streaming and the engine processes, not a
        # second copy of the weights (safetensors are mmapped).
        "memory": f"{min(max(24 * gpus, 32), 512)}GiB",
        # A pool only earns a proxy when it can actually grow; a whole-node
        # replica is expensive enough that pre-allocating a second one is wrong
        # as a default.
        "max_replicas": 2 if gpus <= 2 else 1,
        "proxy": gpus <= 2,
        "readiness": readiness_minutes * 2,
    }


def generate(catalog: Catalog, source_key: str, recipe: dict) -> tuple[str, dict[str, str]] | str:
    """Render one application, or return a string explaining why it was skipped."""
    org, repo = source_key.split("/", 1)
    source = f"models/{source_key}.yaml"

    if "omni" in (recipe.get("meta") or {}).get("tasks", []) or recipe.get("omni"):
        return "omni recipe (vllm serve --omni; different serving shape)"
    if not single_node_strategies(catalog, recipe):
        return "no single-node serving strategy in the recipe"

    combos = build_combos(catalog, recipe)
    if not combos:
        return "no hardware profile holds the weights on one node"

    matrix = feature_matrix(recipe, catalog, combos)
    defaults = compute_defaults(recipe, catalog, combos, matrix)
    slug = app_slug(repo)
    files = {
        "template.yaml": render_template(
            recipe,
            catalog,
            combos,
            matrix,
            source,
            multi_variant=len({c.variant for c in combos}) > 1,
            multi_strategy=len({c.strategy for c in combos}) > 1,
            multi_hardware=len({c.hw_id for c in combos}) > 1,
        ),
        "values.yaml": render_values(recipe, catalog, combos, matrix, source, defaults),
        "metadata.md": render_metadata(
            recipe, catalog, combos, matrix, source, org, repo, slug, defaults
        ),
    }
    return slug, files


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--recipes-dir",
        required=True,
        type=Path,
        help="checkout of https://github.com/vllm-project/recipes",
    )
    parser.add_argument(
        "--out-dir",
        default=Path(__file__).resolve().parent.parent / "applications",
        type=Path,
        help="catalog applications directory (default: ../applications)",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        metavar="ORG/REPO",
        help="only generate these recipes (repeatable)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change, write nothing"
    )
    args = parser.parse_args(argv)

    if not (args.recipes_dir / "models").is_dir():
        parser.error(f"{args.recipes_dir} has no models/ directory")

    catalog = load_catalog(args.recipes_dir)
    wanted = set(args.model)
    written, unchanged, skipped = [], [], []

    for source_key, recipe in catalog.recipes.items():
        if wanted and source_key not in wanted:
            continue
        result = generate(catalog, source_key, recipe)
        if isinstance(result, str):
            skipped.append((source_key, result))
            continue
        slug, files = result
        app_dir = args.out_dir / slug
        changed = [
            name
            for name, content in files.items()
            if not (app_dir / name).exists() or (app_dir / name).read_text() != content
        ]
        if not changed:
            unchanged.append(slug)
            continue
        written.append((slug, changed))
        if args.dry_run:
            continue
        app_dir.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (app_dir / name).write_text(content)

    verb = "would write" if args.dry_run else "wrote"
    print(f"{verb} {len(written)} application(s), {len(unchanged)} already current")
    for slug, changed in written:
        print(f"  {slug}: {', '.join(sorted(changed))}")
    if skipped:
        reasons = Counter(reason for _, reason in skipped)
        print(f"\nskipped {len(skipped)} recipe(s):")
        for reason, count in reasons.most_common():
            print(f"  {count:3d}  {reason}")
        for source_key, reason in skipped:
            print(f"       {source_key}: {reason}", file=sys.stderr)
    if wanted:
        missing = wanted - set(catalog.recipes)
        for name in sorted(missing):
            print(f"no such recipe: {name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
