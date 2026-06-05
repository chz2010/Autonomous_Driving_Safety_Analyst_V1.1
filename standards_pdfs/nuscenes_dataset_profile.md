# nuScenes Dataset Safety Profile

Generated from `datasets/nuscenes/v1.0-trainval` metadata.

## Dataset Summary

| Field | Value |
| --- | --- |
| Dataset | nuScenes train/validation metadata |
| Primary safety use | Autonomous-driving perception, object detection, tracking, sensor fusion, AEB-relevant scenario coverage |
| Scenes | 850 |
| Samples | 34,149 |
| Scene sample references | 34,149 |
| Annotated objects | 1,166,187 |
| Categories | 23 |
| Sensors | 12 |
| Locations | singapore-onenorth (23), boston-seaport (30), singapore-queenstown (10), singapore-hollandvillage (5) |

## Sensor Modalities

- CAM_BACK (camera)
- CAM_BACK_LEFT (camera)
- CAM_BACK_RIGHT (camera)
- CAM_FRONT (camera)
- CAM_FRONT_LEFT (camera)
- CAM_FRONT_RIGHT (camera)
- LIDAR_TOP (lidar)
- RADAR_BACK_LEFT (radar)
- RADAR_BACK_RIGHT (radar)
- RADAR_FRONT (radar)
- RADAR_FRONT_LEFT (radar)
- RADAR_FRONT_RIGHT (radar)

## Top Object Categories

| Item | Count | Share |
| --- | ---: | ---: |
| vehicle.car | 493,322 | 42.3% |
| human.pedestrian.adult | 208,240 | 17.9% |
| movable_object.barrier | 152,087 | 13.0% |
| movable_object.trafficcone | 97,959 | 8.4% |
| vehicle.truck | 88,519 | 7.6% |
| vehicle.trailer | 24,860 | 2.1% |
| movable_object.pushable_pullable | 24,605 | 2.1% |
| vehicle.construction | 14,671 | 1.3% |
| vehicle.bus.rigid | 14,501 | 1.2% |
| vehicle.motorcycle | 12,617 | 1.1% |
| vehicle.bicycle | 11,859 | 1.0% |
| human.pedestrian.construction_worker | 9,161 | 0.8% |
| movable_object.debris | 3,016 | 0.3% |
| static_object.bicycle_rack | 2,713 | 0.2% |
| human.pedestrian.child | 2,066 | 0.2% |
| vehicle.bus.bendy | 1,820 | 0.2% |
| human.pedestrian.stroller | 1,072 | 0.1% |
| animal | 787 | 0.1% |
| human.pedestrian.police_officer | 727 | 0.1% |
| vehicle.emergency.police | 638 | 0.1% |

## Visibility Distribution

| Item | Count | Share |
| --- | ---: | ---: |
| v80-100: visibility of whole object is between 80 and 100% | 544,720 | 46.7% |
| v0-40: visibility of whole object is between 0 and 40% | 335,059 | 28.7% |
| v60-80: visibility of whole object is between 60 and 80% | 155,814 | 13.4% |
| v40-60: visibility of whole object is between 40 and 60% | 130,594 | 11.2% |

## Top Object Attributes

| Item | Count | Share |
| --- | ---: | ---: |
| vehicle.parked | 420,226 | 47.9% |
| pedestrian.moving | 157,444 | 17.9% |
| vehicle.moving | 149,203 | 17.0% |
| vehicle.stopped | 65,975 | 7.5% |
| pedestrian.standing | 46,530 | 5.3% |
| cycle.without_rider | 17,345 | 2.0% |
| pedestrian.sitting_lying_down | 13,939 | 1.6% |
| cycle.with_rider | 7,331 | 0.8% |

## Scenario Keywords from Scene Descriptions

| Item | Count | Share |
| --- | ---: | ---: |
| intersection | 290 | 34.1% |
| turn | 242 | 28.5% |
| truck | 208 | 24.5% |
| bus | 205 | 24.1% |
| parking | 199 | 23.4% |
| rain | 165 | 19.4% |
| bicycle | 162 | 19.1% |
| construction | 148 | 17.4% |
| night | 99 | 11.6% |
| traffic | 66 | 7.8% |
| lane | 35 | 4.1% |
| pedestrian | 33 | 3.9% |
## Sensor Sample Metadata



- Total sample_data records: 2,631,083

- Key-frame records: 409,788

## Sample Data by Sensor Channel

| Item | Count | Share |
| --- | ---: | ---: |
| LIDAR_TOP (lidar) | 331,886 | 12.6% |
| RADAR_FRONT_LEFT (radar) | 225,282 | 8.6% |
| RADAR_FRONT_RIGHT (radar) | 224,584 | 8.5% |
| RADAR_BACK_RIGHT (radar) | 223,214 | 8.5% |
| RADAR_FRONT (radar) | 222,711 | 8.5% |
| RADAR_BACK_LEFT (radar) | 219,616 | 8.3% |
| CAM_FRONT_LEFT (camera) | 198,423 | 7.5% |
| CAM_BACK_RIGHT (camera) | 198,415 | 7.5% |
| CAM_FRONT (camera) | 198,315 | 7.5% |
| CAM_FRONT_RIGHT (camera) | 198,030 | 7.5% |
| CAM_BACK (camera) | 195,602 | 7.4% |
| CAM_BACK_LEFT (camera) | 195,005 | 7.4% |

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
