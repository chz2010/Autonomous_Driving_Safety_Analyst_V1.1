"""
Generate a text safety profile from nuScenes metadata.

This script intentionally uses only the JSON metadata in v1.0-trainval. It does
not require the large camera/LiDAR/radar sample files.

Output:
    standards_pdfs/nuscenes_dataset_profile.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_NUSCENES_DIR = PROJECT_DIR / "datasets" / "nuscenes" / "v1.0-trainval"
DEFAULT_OUTPUT_PATH = PROJECT_DIR / "standards_pdfs" / "nuscenes_dataset_profile.md"


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def iter_json_array(path: Path, chunk_size: int = 1024 * 1024) -> Iterator[dict[str, Any]]:
    """Stream a large JSON array without loading the whole file into memory."""
    decoder = json.JSONDecoder()
    buffer = ""
    started = False

    with path.open(encoding="utf-8") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk and not buffer.strip():
                break
            buffer += chunk

            while True:
                buffer = buffer.lstrip()
                if not started:
                    if not buffer:
                        break
                    if buffer[0] != "[":
                        raise ValueError(f"Expected JSON array in {path}")
                    buffer = buffer[1:]
                    started = True
                    continue

                buffer = buffer.lstrip()
                if buffer.startswith("]"):
                    return
                if buffer.startswith(","):
                    buffer = buffer[1:].lstrip()

                try:
                    obj, index = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    if not chunk:
                        raise
                    break

                yield obj
                buffer = buffer[index:]

            if not chunk:
                break


def top(counter: Counter, n: int = 12) -> list[tuple[str, int]]:
    return counter.most_common(n)


def percent(part: int, whole: int) -> str:
    if whole <= 0:
        return "0.0%"
    return f"{part / whole * 100:.1f}%"


def render_count_table(title: str, rows: list[tuple[str, int]], total: int) -> str:
    lines = [f"## {title}", "", "| Item | Count | Share |", "| --- | ---: | ---: |"]
    for label, count in rows:
        lines.append(f"| {label} | {count:,} | {percent(count, total)} |")
    return "\n".join(lines)


def generate_profile(nuscenes_dir: Path, output_path: Path, include_sample_data: bool) -> None:
    category_rows = load_json(nuscenes_dir / "category.json")
    sensor_rows = load_json(nuscenes_dir / "sensor.json")
    visibility_rows = load_json(nuscenes_dir / "visibility.json")
    scene_rows = load_json(nuscenes_dir / "scene.json")
    sample_rows = load_json(nuscenes_dir / "sample.json")
    log_rows = load_json(nuscenes_dir / "log.json")
    instance_rows = load_json(nuscenes_dir / "instance.json")

    category_by_token = {row["token"]: row["name"] for row in category_rows}
    visibility_by_token = {
        row["token"]: f"{row.get('level', row['token'])}: {row['description']}"
        for row in visibility_rows
    }
    instance_category = {
        row["token"]: category_by_token.get(row["category_token"], "unknown")
        for row in instance_rows
    }

    category_counts: Counter[str] = Counter()
    visibility_counts: Counter[str] = Counter()
    attribute_counts: Counter[str] = Counter()
    annotation_count = 0

    attribute_rows = load_json(nuscenes_dir / "attribute.json")
    attribute_by_token = {row["token"]: row["name"] for row in attribute_rows}

    for annotation in iter_json_array(nuscenes_dir / "sample_annotation.json"):
        annotation_count += 1
        category_counts[instance_category.get(annotation["instance_token"], "unknown")] += 1
        visibility_counts[visibility_by_token.get(annotation.get("visibility_token", ""), "unknown")] += 1
        for token in annotation.get("attribute_tokens", []):
            attribute_counts[attribute_by_token.get(token, "unknown")] += 1

    sensor_lines = [
        f"- {row['channel']} ({row['modality']})"
        for row in sorted(sensor_rows, key=lambda item: item["channel"])
    ]

    sample_data_section = ""
    if include_sample_data:
        calibrated_rows = load_json(nuscenes_dir / "calibrated_sensor.json")
        sensor_by_token = {row["token"]: row for row in sensor_rows}
        calibrated_to_sensor = {
            row["token"]: sensor_by_token.get(row["sensor_token"], {})
            for row in calibrated_rows
        }
        sample_data_counts: Counter[str] = Counter()
        key_frame_count = 0
        sample_data_count = 0
        for sample_data in iter_json_array(nuscenes_dir / "sample_data.json"):
            sample_data_count += 1
            sensor = calibrated_to_sensor.get(sample_data["calibrated_sensor_token"], {})
            label = f"{sensor.get('channel', 'unknown')} ({sensor.get('modality', 'unknown')})"
            sample_data_counts[label] += 1
            if sample_data.get("is_key_frame"):
                key_frame_count += 1

        sample_data_section = "\n\n".join(
            [
                "## Sensor Sample Metadata",
                "",
                f"- Total sample_data records: {sample_data_count:,}",
                f"- Key-frame records: {key_frame_count:,}",
                render_count_table("Sample Data by Sensor Channel", top(sample_data_counts, 20), sample_data_count),
            ]
        )

    location_counts = Counter(row.get("location", "unknown") for row in log_rows)
    scene_descriptions = [row.get("description", "") for row in scene_rows if row.get("description")]
    scenario_keywords = Counter()
    for description in scene_descriptions:
        text = description.lower()
        for keyword in [
            "pedestrian",
            "bicycle",
            "truck",
            "bus",
            "construction",
            "intersection",
            "parking",
            "night",
            "rain",
            "turn",
            "lane",
            "traffic",
        ]:
            if keyword in text:
                scenario_keywords[keyword] += 1

    total_scene_samples = sum(int(row.get("nbr_samples", 0)) for row in scene_rows)

    content = f"""# nuScenes Dataset Safety Profile

Generated from `datasets/nuscenes/v1.0-trainval` metadata.

## Dataset Summary

| Field | Value |
| --- | --- |
| Dataset | nuScenes train/validation metadata |
| Primary safety use | Autonomous-driving perception, object detection, tracking, sensor fusion, AEB-relevant scenario coverage |
| Scenes | {len(scene_rows):,} |
| Samples | {len(sample_rows):,} |
| Scene sample references | {total_scene_samples:,} |
| Annotated objects | {annotation_count:,} |
| Categories | {len(category_rows):,} |
| Sensors | {len(sensor_rows):,} |
| Locations | {", ".join(f"{name} ({count})" for name, count in location_counts.items())} |

## Sensor Modalities

{chr(10).join(sensor_lines)}

{render_count_table("Top Object Categories", top(category_counts, 20), annotation_count)}

{render_count_table("Visibility Distribution", top(visibility_counts, 10), annotation_count)}

{render_count_table("Top Object Attributes", top(attribute_counts, 15), sum(attribute_counts.values()))}

{render_count_table("Scenario Keywords from Scene Descriptions", top(scenario_keywords, 20), len(scene_rows))}
{sample_data_section}

## Autonomous-Driving Safety Relevance

nuScenes is relevant to perception and AEB because it contains annotated road users
and objects across camera, LiDAR, and radar sensor modalities. It can support
reasoning about object detection, tracking, sensor fusion, visibility, occlusion,
and scenario coverage. It is especially useful as evidence for whether a perception
validation strategy includes vulnerable road users, vehicles, and varied urban
driving situations.

## ISO 26262 Relevance

ISO 26262 is relevant when perception failures are caused by E/E malfunctions,
such as corrupted sensor data, stale timestamps, communication failures, ECU
overload, calibration faults, or diagnostic coverage gaps. This dataset can help
define representative perception scenarios for verification, but it does not by
itself prove hardware diagnostic coverage, PMHF, SPFM/LFM, or safe-state behavior.

## ISO 21448 / SOTIF Relevance

SOTIF is relevant because a perception stack can be unsafe even when no component
has malfunctioned. Dataset coverage should be checked for triggering conditions
such as low visibility, partial occlusion, unusual object poses, construction
zones, rare road users, and scenarios near the limits of the operational design
domain. The visibility metadata and scene descriptions can support SOTIF scenario
catalogue development, but raw coverage should be reviewed against the target ODD.

## ISO 8800 Relevance

ISO 8800 is relevant if AI/ML models are trained, validated, or released using
this dataset. Safety arguments should address data quality, class balance,
annotation quality, train/validation/test separation, rare-scenario coverage,
uncertainty handling, robustness, model versioning, and regression testing. A
dataset profile like this is useful evidence for AI safety planning, but it is
not sufficient by itself: the project still needs performance metrics, failure
analysis, confidence calibration, and release criteria.

## AEB and Perception Validation Usefulness

For AEB, useful evidence includes pedestrians, cyclists, vehicles, visibility
levels, occlusion-like scenarios, and sensor-fusion disagreement cases. The dataset
can support offline perception validation, but vehicle-level AEB validation still
requires closed-loop tests with braking response, timing, speed, road friction,
and minimum safe distance acceptance criteria.

## Likely Safety Gaps to Check

- Whether night, rain, fog, glare, and spray are sufficiently represented for the
  intended ODD.
- Whether vulnerable road users have enough examples under occlusion and low
  visibility.
- Whether rare object classes and unusual poses are underrepresented.
- Whether the annotation quality is sufficient for safety validation, especially
  for pedestrians, cyclists, and partially visible objects.
- Whether validation data is independent from training data and representative of
  deployment regions.
- Whether model confidence and uncertainty are evaluated, not only detection
  accuracy.

## Recommended Use in This Project

Use this dataset profile as a safety document for questions about dataset coverage,
AI perception validation, ISO 8800 data management, SOTIF scenario coverage, and
AEB/perception limitations. Do not treat it as proof that an autonomous-driving
system is safe; treat it as one input to a broader safety case.
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a nuScenes safety profile")
    parser.add_argument("--nuscenes-dir", type=Path, default=DEFAULT_NUSCENES_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--include-sample-data",
        action="store_true",
        help="Also stream sample_data.json for sensor sample counts. Slower.",
    )
    args = parser.parse_args()

    generate_profile(args.nuscenes_dir, args.output, args.include_sample_data)


if __name__ == "__main__":
    main()
