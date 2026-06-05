# ISO 8800 Evaluation Scheme for AI Safety in Road Vehicles

This document is an original project-specific evaluation scheme based on ISO 8800 safety-and-AI concepts. It is not a copy of ISO text. Use it as a structured checklist for evaluating AI/ML components used in autonomous-driving or ADAS safety-related functions.

## Purpose

ISO 8800-style evaluation asks whether an AI-enabled road-vehicle function is acceptably safe across its intended lifecycle. The evaluation should cover the AI function, data, model behavior, robustness, validation, release control, monitoring, and change management. It complements ISO 26262 and SOTIF:

- ISO 26262 focuses on E/E malfunctioning behavior and functional safety lifecycle evidence.
- ISO 21448 / SOTIF focuses on intended-function limitations and triggering conditions.
- ISO 8800 focuses on AI-specific safety concerns such as data coverage, model behavior, robustness, uncertainty, and AI lifecycle controls.

## Evaluation Flow

| Step | Evaluation question | Required evidence | Engineering output |
| --- | --- | --- | --- |
| 1. Define AI function | What AI task is performed and which vehicle function depends on it? | AI item definition, input/output interface, safety role, ODD assumptions | AI function definition and safety relevance |
| 2. Define AI safety requirements | What unsafe AI behavior must be prevented or controlled? | Safety goals, functional/technical safety requirements, SOTIF limitations | AI safety requirements and acceptance criteria |
| 3. Define data requirements | What data is needed to support the target ODD and safety function? | ODD, scenario catalogue, class list, sensor modalities, edge-case list | Data requirements specification |
| 4. Evaluate dataset coverage | Does the dataset cover road users, environments, weather, lighting, occlusion, geography, and rare scenarios? | Dataset profile, class counts, visibility, attributes, scenario labels | Dataset coverage assessment |
| 5. Evaluate label quality | Are annotations accurate, complete, consistent, and traceable? | Labeling guideline, QA results, inter-annotator review, error samples | Label-quality report |
| 6. Control dataset splits | Are train/validation/test sets independent and representative? | Split strategy, leakage checks, scenario distribution comparison | Data split justification |
| 7. Evaluate model performance | Does the AI meet safety-relevant KPIs, not only average accuracy? | Per-class metrics, scenario metrics, false-negative analysis, latency | Model performance report |
| 8. Evaluate robustness | Does the model remain safe under noise, occlusion, rare objects, weather, and distribution shift? | Stress tests, OOD tests, perturbation tests, scenario tests | Robustness evidence |
| 9. Evaluate uncertainty | Does the model recognize when it is uncertain or outside its competence? | Confidence calibration, uncertainty thresholds, OOD detector, fallback trigger | Uncertainty and confidence evidence |
| 10. Evaluate integration | Does downstream planning/control handle AI output safely? | Interface tests, confidence handling, fusion disagreement tests, timing analysis | Integration safety evidence |
| 11. Define release gate | What blocks an unsafe AI/model release? | Safety KPI thresholds, regression tests, coverage criteria, approval workflow | AI release checklist |
| 12. Monitor in operation | How are drift, regressions, and unknown unsafe cases detected after release? | Field monitoring, incident review, telemetry, update process | Monitoring and feedback process |
| 13. Manage AI changes | How are retraining, OTA updates, and dataset changes controlled? | Versioning, change impact analysis, regression evidence, rollback plan | AI change-management record |
| 14. Judge residual AI risk | What AI-specific risk remains and why is it acceptable? | Evidence summary, limitations, open issues, mitigation status | Residual AI risk judgment |

## Dataset Coverage Evaluation

Use this table for perception datasets such as camera, LiDAR, radar, or sensor-fusion data.

| Coverage dimension | What to check | Safety concern if weak | Evidence |
| --- | --- | --- | --- |
| Object classes | Pedestrians, cyclists, vehicles, motorcycles, animals, debris, emergency vehicles, construction objects | False negatives for underrepresented road users | Class counts and per-class metrics |
| Visibility | Clear, partial occlusion, heavy occlusion, low visibility | Late or missed detection | Visibility distribution and scenario tests |
| Weather | clear, rain, fog, spray, snow, wet road | Distribution shift and degraded sensor performance | Weather labels, scenario catalogue |
| Lighting | day, night, glare, tunnel, low contrast | Camera and perception performance limits | Time-of-day labels and night metrics |
| Geography | deployment regions, road markings, signage, driving culture | Poor generalization to target ODD | Location distribution |
| Dynamic behavior | crossing, cut-in, braking, lane change, stopped objects | Prediction/planning errors | Scenario labels and trajectory analysis |
| Rare scenarios | unusual pose, unusual object shape, construction, emergency vehicles | Unknown unsafe scenarios | Rare-scenario coverage report |
| Sensor modalities | camera, LiDAR, radar, map, ego motion | Fusion assumptions and missing modality risks | Sensor metadata and synchronization checks |

## AI Model Evaluation Matrix

| Evaluation area | Concrete test | Expected safe behavior | Acceptance criterion | Evidence artifact |
| --- | --- | --- | --- | --- |
| False-negative risk | Pedestrian/cyclist detection under occlusion | No safety-relevant road user missed without uncertainty escalation | Scenario false-negative rate below safety threshold; fallback triggered when uncertain | Per-scenario metric report |
| False-positive risk | Ghost object or reflective surface | Planner does not create dangerous braking/steering behavior | False positives handled conservatively without unacceptable secondary risk | Track/simulation report |
| Confidence calibration | High confidence wrong detections | Model does not output unsafe overconfidence | Calibration error below threshold; uncertainty triggers fallback | Calibration plot and threshold report |
| OOD detection | Novel objects or unseen environments | System recognizes outside-competence condition | OOD detector recall meets release threshold | OOD test report |
| Robustness | Rain, fog, noise, sensor artifacts | Output degrades safely, not silently | Performance degradation bounded; safe fallback engaged | Robustness test report |
| Regression | New model or OTA update | No safety KPI worsens below release gate | All safety regression tests pass | Release gate checklist |
| Latency | High compute load | Perception output remains timely or invalidated | End-to-end latency below safety budget | Timing analysis |
| Integration | Fusion disagreement | Downstream planner handles uncertainty safely | Disagreement causes conservative planning or fallback | Integration test evidence |

## Release Gate Checklist

An AI model should not be released if any of the following are true:

- safety-relevant classes have insufficient coverage or poor performance;
- vulnerable road-user false negatives exceed the agreed threshold;
- validation data is not representative of the target ODD;
- train/test leakage or split bias is unresolved;
- uncertainty is poorly calibrated or unsafe overconfidence is observed;
- model regression appears in rare scenarios, weather, night, occlusion, or target regions;
- OOD detection is insufficient for known deployment limits;
- integration tests show unsafe planner or AEB response to AI output;
- field-monitoring and rollback processes are not ready;
- residual AI risk is not justified by evidence.

## Operation Monitoring

After release, monitor:

- field false negatives and false positives;
- near misses and disengagements;
- confidence distribution drift;
- ODD violation frequency;
- weather/night/region-specific performance;
- rare object and vulnerable road-user incidents;
- model version and dataset version in each event;
- OTA regression indicators;
- user complaints and service reports.

Field evidence should feed back into dataset updates, scenario catalogue updates, model retraining, regression tests, release gates, and residual risk evaluation.

## Example Mini Evaluation: AEB Pedestrian Perception Model

Function: AI perception model detects pedestrians and provides object position, velocity, class, and confidence to the AEB/planning stack.

Dataset concern: A dataset may contain many pedestrians overall but still be weak for night, rain, partial occlusion, dark clothing, children, construction zones, or uncommon pedestrian poses. Average detection performance is therefore insufficient evidence for safety.

Safety concern: A false negative for a pedestrian at an urban crossing can delay AEB. At 50 km/h, even a short detection delay can materially reduce available stopping distance.

ISO 8800-style evaluation:

- define data requirements for the target ODD, including night, rain, occlusion, and vulnerable road-user diversity;
- measure per-scenario false-negative rates, not only global precision/recall;
- check confidence calibration so low-confidence or OOD cases trigger conservative behavior;
- verify that new model releases do not regress on vulnerable-road-user scenarios;
- monitor field performance and feed near misses into the dataset and scenario catalogue.

Recommended engineering decision: Do not release the model if night/rain/occluded pedestrian performance is below the safety threshold, if confidence is overestimated in those scenarios, or if AEB integration tests show late braking.

