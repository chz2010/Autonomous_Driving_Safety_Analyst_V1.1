In# Project-Generated Example Safety Case: LiDAR Perception Item

Status: Project-generated worked example. This is not official ISO text and is not a substitute for the ISO 26262, ISO 21448/SOTIF, or ISO 8800 standards. Use it as an engineering-style reference pattern for RAG answers.

## 0. Public Safety-Case Practice Alignment

This synthetic example is strengthened using public safety-case practices from autonomous-driving literature and safety reports. It is not an approved safety case. It should be read as a structured example of how to argue absence of unreasonable risk for one perception item.

| Public safety-case principle | How this example applies it |
|---|---|
| Explain the system under analysis | Defines the LiDAR item boundary, inputs, outputs, operating modes, ODD assumptions, and downstream safety role |
| Use a claim-argument-evidence logic | Links LiDAR functions to hazards, safety goals, ISO 26262/SOTIF/ISO 8800 activities, tests, evidence, and residual-risk judgments |
| Make acceptance criteria explicit | Requires safety KPIs, diagnostic response targets, invalid-output behavior, release gates, and blocked-release rules |
| Use multiple evidence sources | Combines analysis, simulation, fault injection, scenario testing, closed-loop vehicle behavior, production controls, and field monitoring |
| Pressure-test the argument | Requires worst-case and edge-case scenarios, ODD boundary tests, model-regression tests, and near-miss feedback loops |
| Maintain safety after release | Includes operation, continuous assurance, drift monitoring, incident review, OTA gates, staged rollout, and rollback |

## 1. Item Definition

Assumed item: LiDAR perception subsystem providing object and free-space information to fusion, planning, AEB, ACC, and automated-driving functions.

| Element | Example content |
|---|---|
| Item description | LiDAR-based perception item that converts point-cloud and vehicle-context inputs into safety-relevant object, free-space, tracking, confidence, and health outputs for downstream driving functions |
| Item boundary | LiDAR sensor, perception preprocessing, object extraction, tracking, confidence estimation, health monitoring, output interface to fusion/planning |
| Main functions | Object detection, object classification, distance estimation, relative velocity estimation, free-space estimation, tracking, confidence/uncertainty output, sensor health monitoring, calibration monitoring, timestamp/data freshness, interface output |
| Inputs | Point cloud, timestamp, ego motion, calibration parameters, sensor health status, optional camera/radar/map context |
| Outputs | Object list, object class, object distance, relative velocity, free-space grid, track ID, confidence/uncertainty, health/degradation flags |
| Operating modes | Normal perception, degraded perception, invalid-output/fallback mode, service/calibration mode, post-update monitoring mode |
| ODD assumptions | Urban and highway operation, defined speed range, defined weather/visibility limits, defined sensor mounting and calibration state |
| Safety role | Supports collision avoidance, trajectory planning, AEB object confirmation, minimum-risk behavior, and ODD boundary decisions |

## 2. Functional Decomposition

| Function | Output | ISO 26262 malfunction example | SOTIF insufficiency example | ISO 8800 AI/data/model concern | HARA carried forward? |
|---|---|---|---|---|---|
| Object detection | Object existence | Object not output although point cloud contains obstacle | Pedestrian partly occluded or low reflectivity gives late detection | Dataset lacks rainy-night occluded pedestrians | Yes |
| Classification | Object class | Pedestrian classified as static object due to software defect | Unusual pose or wheelchair user outside assumed appearance | Label inconsistency for VRU classes | Yes |
| Distance estimation | Object range | Range underestimated/overestimated due to calibration or computation fault | Rain/spray reduces range reliability | Model or postprocessor poorly calibrated for sparse point clouds | Yes |
| Relative velocity estimation | Closing speed | Wrong velocity due to timestamp or tracking fault | Low point density causes unstable velocity estimate | Insufficient validation of cut-in and crossing objects | Yes |
| Free-space estimation | Drivable area / occupancy | Occupied region reported as free | Reflective surfaces or road spray create free-space ambiguity | Training/validation lacks unusual road-edge and reflective cases | Yes |
| Tracking | Track continuity | Frozen or swapped track ID | Dense occlusion causes track loss without component fault | Temporal model weak on partial occlusion and reappearance | Yes |
| Confidence output | Confidence or uncertainty | Confidence stuck high due to software fault | Confidence does not decrease in rain or low visibility | Overconfidence on out-of-distribution scenes | Yes |
| Sensor health monitoring | Degradation status | Blocked/degraded sensor not detected | Gradual dirt or spray reduces capability before diagnostic threshold | Monitoring data does not capture field degradation patterns | Yes |
| Calibration monitoring | Alignment status | Calibration offset not detected | Small mounting shift causes systematic position error | Validation lacks post-service calibration variation | Yes |
| Timestamp/data freshness | Freshness flag | Stale point cloud accepted as current | Processing latency grows in dense scenes | Model not validated for latency-sensitive sequences | Yes |
| Interface output | Message to fusion/planning | Wrong object list or invalid flag transmitted | Downstream module overtrusts uncertain LiDAR output | Release gate lacks end-to-end perception-to-planning safety KPI | Yes |

## 3. HARA Screening Example

Assumptions for this example: automated-driving support is active; baseline scenario uses urban 50 km/h and highway 100 km/h where applicable; driver fallback may be limited for short time-to-collision events; ratings are engineering estimates and require project confirmation.

| Function | Malfunction / insufficiency | Hazardous event | Operational situation | S rationale | E rationale | C rationale | ASIL/QM | Next action |
|---|---|---|---|---|---|---|---|---|
| Object detection | Missed pedestrian or vehicle | No braking or avoidance for obstacle | Urban crossing, 50 km/h | S3 because collision with VRU can be life-threatening | E3 because urban crossings are common in intended ODD | C3 if detection is late and driver/system has little time | ASIL D candidate | Safety goal for detecting safety-relevant objects or safe fallback |
| Classification | VRU classified as non-relevant object | Planner selects unsafe path or delay | Urban mixed traffic | S3 for possible VRU collision | E3 in VRU-rich ODD | C2-C3 depending on TTC and driver fallback | ASIL C-D | Class plausibility, fusion cross-check, conservative unknown-object behavior |
| Distance estimation | Range overestimated | AEB/planning reacts too late | Highway cut-in or urban obstacle | S3 at high speed or VRU conflict | E2-E3 depending on scenario | C2-C3 depending on remaining stopping distance | ASIL C-D | Range plausibility, calibration monitoring, timing budget |
| Relative velocity estimation | Closing speed underestimated | Inadequate deceleration | Highway lead vehicle braking | S3 for rear-end crash at speed | E3 for highway following | C2 if driver may intervene, C3 at short TTC | ASIL C-D | Velocity cross-check, track consistency tests |
| Free-space estimation | Occupied area marked free | Vehicle plans into obstacle or road edge | Construction zone or unstructured road | S2-S3 depending obstacle and speed | E2 in construction or complex roads | C2-C3 depending automation authority | ASIL B-D | Conservative free-space uncertainty handling |
| Tracking | Track lost or swapped | Wrong object trajectory prediction | Dense traffic or occlusion | S2-S3 depending target | E3 in dense urban traffic | C2-C3 depending warning/fallback time | ASIL B-D | Track continuity and re-identification requirements |
| Confidence output | Unsafe high confidence | Downstream modules overtrust wrong perception | Rain/fog/night or ODD boundary | S3 if unsafe output controls braking/steering | E2-E3 depending ODD exposure | C2-C3 because driver may not see uncertainty | ASIL C-D plus ISO 8800 concern | Confidence calibration and uncertainty escalation |
| Sensor health monitoring | Degradation not reported | Perception used beyond valid capability | Dirt, spray, receiver degradation | S3 if safety function remains active | E2-E3 depending weather/maintenance | C2-C3 depending fallback and HMI | ASIL C-D | Diagnostic coverage and degraded-mode safety requirement |
| Calibration monitoring | Misalignment not detected | Object appears in wrong position | After service or impact | S2-S3 depending object and speed | E1-E2 for service/impact cases | C2-C3 if output is plausible but wrong | ASIL B-C | Calibration plausibility and service recalibration process |
| Timestamp/data freshness | Stale data accepted | Vehicle reacts to old scene | Dense scene, ECU overload | S3 if object moved since stale frame | E2 in high-load operation | C3 for short-TTC events | ASIL D candidate | Timestamp checks, timeout, stale-data invalidation |
| Interface output | Unsafe object message to planning | Incorrect braking/steering decision | Any ADAS/AD active scenario | S2-S3 depending maneuver | E3 if interface is used continuously | C2-C3 depending automation and driver fallback | ASIL B-D | Interface safety requirements, CRC/counter, invalid signal handling |

## 4. Safety Goals and Concepts

| Safety goal | Related functions | Example safe behavior |
|---|---|---|
| SG-LIDAR-01: Prevent missing safety-relevant objects due to LiDAR perception malfunction | Object detection, tracking, interface output | If confidence or freshness is insufficient, invalidate output and trigger degraded behavior |
| SG-LIDAR-02: Prevent incorrect object position, distance, or velocity from causing unsafe planning | Distance, velocity, calibration, timestamp | Cross-check range and velocity, reject stale or implausible outputs |
| SG-LIDAR-03: Prevent unsafe overtrust in degraded perception | Confidence, sensor health, free-space | Reduce speed, restrict ODD, request fallback, or use sensor fusion when uncertainty is high |

## 5. ISO 26262 Lifecycle Pattern

| ISO 26262 part | Item-specific activities | Evidence / work product | Rationale |
|---|---|---|---|
| Part 2 | Safety plan, DIA with sensor/perception supplier, confirmation reviews | Safety plan, confirmation review records | Ensures responsibilities and independence are clear before safety evidence is accepted |
| Part 3 | Item definition, HARA, safety goals, FSC | Item definition, HARA table, safety goals | Converts vehicle-level hazards into safety goals for LiDAR outputs and degradation behavior |
| Part 4 | System safety requirements and TSC allocated to LiDAR, fusion, planning, HMI | System architecture, TSRs, integration tests | Ensures wrong or stale perception is detected before unsafe vehicle behavior |
| Part 5 | Hardware analysis for emitter/receiver/power/timing/communication | FMEDA, PMHF/SPFM/LFM where applicable, fault injection | Addresses random hardware failures that can corrupt or remove perception output |
| Part 6 | Software safety requirements for freshness, plausibility, watchdog, diagnostics | SW architecture, unit/integration tests | Addresses systematic software faults and timing/freshness failures |
| Part 7 | Production and service calibration, health checks, field monitoring | EOL records, DTC strategy, service procedure | Keeps sensor alignment and diagnostics valid during operation |
| Part 8 | Configuration, change, tool confidence, traceability, safety case | Trace matrix, tool assessment, change impact | Controls changes to perception software/model and evidence |
| Part 9 | ASIL decomposition, dependent failure analysis, FMEA/FTA/DFA | Safety analyses | Prevents common-cause or cascading failures across perception, fusion, and planning |

### ISO 26262 Part 4 Coverage: System Development

This example covers Part 4 through system-level technical safety requirements, allocation of LiDAR perception safety requirements to the sensor, perception ECU, fusion/planning interface, HMI/fallback behavior, and vehicle-level integration/validation evidence.

### ISO 26262 Part 5 Coverage: Hardware Development

This example covers Part 5 through hardware-oriented analysis of LiDAR emitter, receiver, power supply, timing source, communication path, diagnostic coverage, random hardware failure metrics where applicable, and fault-injection evidence.

### ISO 26262 Part 6 Coverage: Software Development

This example covers Part 6 through software safety requirements for freshness checks, plausibility checks, watchdogs, diagnostic handling, invalid output suppression, degraded-mode logic, and unit/integration verification.

### ISO 26262 Part 7 Coverage: Production, Operation, Service, and Decommissioning

This example covers Part 7 through end-of-line calibration, service recalibration, diagnostic trouble codes, sensor health monitoring in operation, and field feedback for degraded perception.

### ISO 26262 Part 8 Coverage: Supporting Processes

This example covers Part 8 through requirements traceability, configuration management, change management, tool confidence considerations, evidence management, and safety case maintenance.

### ISO 26262 Part 9 Coverage: ASIL-Oriented and Safety-Oriented Analyses

This example covers Part 9 through ASIL decomposition considerations, dependent failure analysis, common-cause and cascading-failure analysis, FMEA, FTA, DFA, and freedom-from-interference arguments.

## 6. SOTIF Function Analysis Pattern

### SOTIF Coverage: Intended Functionality, ODD, Triggering Conditions, and Residual Risk

This example covers SOTIF by analyzing LiDAR functions that can be unsafe without an E/E malfunction, including performance limitations, triggering conditions, ODD boundaries, known/unknown unsafe scenarios, validation evidence, and risk reduction measures.

| Function | Intended-function insufficiency | Triggering condition | Risk reduction |
|---|---|---|---|
| Object detection | Late/no detection without component fault | Rain, spray, occlusion, dark clothing, low reflectivity | ODD limits, confidence degradation, sensor fusion, speed reduction |
| Classification | Misclassification of unusual road user | Wheelchair user, child, stroller, unusual pose | Unknown-object conservative handling and scenario expansion |
| Free-space estimation | Free-space ambiguity | Reflective surface, construction zone, road edge ambiguity | Conservative occupancy and validation in triggering conditions |
| Confidence output | Confidence does not reflect degraded capability | Fog, sensor blockage, unfamiliar scene | Confidence calibration, uncertainty threshold, fallback request |

## 7. ISO 8800 AI Assurance Pattern

### ISO 8800 Coverage: AI Safety, Data, Model Robustness, Release, and Monitoring

This example covers ISO 8800 by analyzing AI/data/model assurance concerns, including data requirements, dataset coverage, label quality, robustness, uncertainty calibration, OOD/distribution shift, release gates, monitoring, drift, and regression control.

#### ISO 8800 Clause 8 Coverage: Assurance Arguments for AI Systems

This example supports an AI safety assurance argument by linking LiDAR perception functions, hazards, AI/data/model risks, evidence, release gates, and residual risk into a traceable safety case.

#### ISO 8800 Clause 9 Coverage: AI Safety Requirements

This example derives AI-related safety requirements from LiDAR perception risks, such as safe uncertainty behavior, conservative output under degraded perception, dataset coverage requirements, and release-blocking safety KPIs.

#### ISO 8800 Clause 10 Coverage: Architectural and Development Measures for AI Systems

This example covers architectural and development measures such as sensor fusion cross-checks, confidence thresholds, OOD handling, degraded-mode logic, model version control, and release criteria for AI-enabled perception.

#### ISO 8800 Clause 11 Coverage: Data and Dataset Assurance

This example covers data requirements, dataset coverage, label quality, dataset design, dataset implementation, dataset maintenance, and dataset safety evidence for LiDAR perception scenarios.

#### ISO 8800 Clause 12 Coverage: AI Component Testing

This example covers AI component testing through robustness tests, OOD tests, noisy/sparse point-cloud tests, rare VRU scenarios, confidence calibration tests, and model-regression tests.

#### ISO 8800 Clause 13 Coverage: Safety Analysis of the AI System

This example covers AI system safety analysis by connecting model failure modes, dataset gaps, uncertainty behavior, distribution shift, and unsafe downstream planning/braking effects.

#### ISO 8800 Clause 14 Coverage: Operation and Continuous Assurance

This example covers operational AI assurance through field monitoring, drift detection, incident and near-miss feedback, dataset updates, OTA release gates, and rollback criteria.

#### ISO 8800 Clause 15.6 Coverage: Data-Driven AI Model Training and Evaluation

This example covers data-driven AI model training and evaluation by requiring controlled training datasets, independent validation data, safety-relevant KPIs, robustness checks, uncertainty calibration, regression tests, and documented model-selection rationale before release.

| AI-related area | Example risk | Evidence expected before release |
|---|---|---|
| Data requirements | Dataset lacks ODD-relevant VRU and weather cases | Dataset coverage matrix by ODD, class, visibility, occlusion |
| Label quality | Occluded pedestrians or cyclists inconsistently labeled | Label QA report, inter-annotator checks, defect correction records |
| Robustness | Model overfits normal daylight scenes | Stress tests for rain, night, sparse point cloud, sensor noise |
| Uncertainty | Unsafe high confidence under distribution shift | Calibration curves, OOD tests, confidence threshold evidence |
| Release gate | New model improves average accuracy but regresses safety cases | Safety KPI regression suite and blocked-release criteria |
| Monitoring | Field drift or new scenario type appears after release | Drift monitoring, incident triage, data feedback loop |

## 8. Verification and Validation Pattern

| Test category | Concrete test | Expected safe behavior | Evidence |
|---|---|---|---|
| ISO 26262 malfunction | Stale point cloud, CRC error, frozen track, calibration offset | Output invalidated or degraded mode triggered within timing target | Fault injection report |
| SOTIF performance | Rain, fog, occlusion, low-reflectivity pedestrian | Confidence decreases, speed/ODD restricted, fallback requested | Scenario validation report |
| ISO 8800 AI | Rare VRU pose, noisy point cloud, OOD object, model update | No unsafe overconfidence; release blocked if safety KPI regresses | AI safety validation report |
| Vehicle-level | AEB/planning response to perception uncertainty | Conservative braking/planning or minimum-risk behavior | Closed-loop simulation and proving-ground evidence |

## 9. Evaluated Sample Answer: LiDAR Perception Safety Case

This section is a completed example answer, not only an instruction template. It shows the expected engineering depth, rationale, and final safety judgment for a LiDAR perception item.

### 9.1 Engineering Judgment

The LiDAR perception item cannot be argued safe by object-detection accuracy alone. The safety case must show that every safety-relevant output is either correct enough for downstream use, explicitly uncertain, or invalidated before it can create unsafe vehicle behavior.

The strongest safety concern is not only a total LiDAR failure. The more difficult case is a plausible but wrong output: an object detected at the wrong distance, an occupied area marked as free, a stale point cloud treated as current, or an overconfident output under rain, spray, occlusion, or sparse point-cloud conditions. These cases are dangerous because downstream fusion, planning, AEB, or automated-driving logic may trust the perception result.

### 9.2 Function-Level Evaluation

| Function | Main safety concern | Evaluation judgment | Required engineering evidence |
|---|---|---|---|
| Object detection | Missed safety-relevant obstacle or VRU | Safety-critical; carry into HARA and SOTIF scenario validation | Detection KPI by object class, ODD, visibility, occlusion, and range |
| Classification | VRU or obstacle classified as non-relevant | Safety-critical when class affects braking/planning priority | Confusion matrix for VRUs, unknown-object policy, label QA |
| Distance estimation | Range overestimated, braking/planning too late | Safety-critical; must be tied to stopping-distance margin | Range error budget, calibration evidence, fault injection |
| Relative velocity estimation | Closing speed underestimated | Safety-critical for AEB/ACC and collision prediction | Velocity error tests, timestamp validation, track consistency |
| Free-space estimation | Occupied space marked free | Safety-critical for planning and minimum-risk behavior | Free-space scenario tests, construction/road-edge validation |
| Tracking | Track lost, swapped, or frozen | Safety-critical in occlusion and dense scenes | Temporal continuity tests, stale-track invalidation |
| Confidence output | Unsafe overconfidence | Critical ISO 8800 and SOTIF concern | Calibration curves, OOD tests, confidence-to-action thresholds |
| Sensor health monitoring | Degradation not detected | Safety-critical if degraded perception remains active | Diagnostic coverage, blockage/dirt/spray tests, DTC strategy |
| Calibration monitoring | Misalignment not detected | Safety-critical if object position is shifted | Calibration plausibility, service recalibration, misalignment tests |
| Timestamp/data freshness | Stale point cloud accepted | Safety-critical for dynamic scenes | Timeout requirements, freshness checks, latency budget |
| Interface output | Invalid perception accepted downstream | Safety-critical cross-item interface risk | CRC/counter, valid flags, fusion/planning integration tests |

### 9.3 ISO 26262 Evaluation

ISO 26262 applies to E/E malfunctions in the LiDAR sensor, perception ECU, communication path, timing path, software, calibration handling, diagnostics, and output interface. The item should not be treated as one single function. Each function that can create an unsafe vehicle behavior needs a malfunction analysis and HARA screening.

| ISO 26262 lifecycle area | Evaluation for this LiDAR item |
|---|---|
| Part 3 concept phase | HARA must evaluate missed object, wrong range, wrong velocity, false free-space, stale data, overconfident output, and invalid interface output. QM rows may stop after justification, but ASIL rows continue into safety goals. |
| Part 4 system development | Technical safety requirements must define when LiDAR output is valid, invalid, degraded, or uncertain, and how fusion/planning shall react. |
| Part 5 hardware development | LiDAR emitter, receiver, power, timing, and communication faults require hardware safety analysis, diagnostic coverage evidence, and fault-injection confirmation. |
| Part 6 software development | Software safety requirements must cover freshness, plausibility, watchdogs, track validity, confidence handling, invalid-output suppression, and interface consistency. |
| Part 7 production/operation | End-of-line calibration, service recalibration, DTCs, blockage/degradation detection, and field monitoring are required because LiDAR safety depends strongly on alignment and sensor condition. |
| Part 8 supporting processes | Model/software versioning, traceability, change impact analysis, tool confidence, and release evidence are needed before updates are accepted. |
| Part 9 safety analyses | Dependent failure analysis is needed because perception, fusion, planning, and braking may share assumptions and can fail together through overtrust in the same wrong object model. |

### 9.4 SOTIF Evaluation

SOTIF applies when the LiDAR and E/E system work as designed but the intended function is insufficient. Examples include rain/spray reducing point-cloud quality, dark clothing or low-reflectivity objects, occlusion, unusual road users, reflective surfaces, and operation near the ODD boundary.

| Triggering condition | Unsafe mechanism | Required risk reduction |
|---|---|---|
| Heavy rain or spray | Sparse/noisy point cloud, late detection | Reduce confidence, restrict speed/ODD, require fusion confirmation |
| Partial occlusion | Object appears too late for comfortable braking | Occlusion-aware prediction, conservative planning, scenario validation |
| Low-reflectivity VRU | Weak returns and unstable classification | Dataset/scenario expansion, unknown-object handling |
| Reflective surface or road edge | Free-space ambiguity or ghost object | Conservative free-space logic, plausibility checks |
| Sensor dirt below diagnostic threshold | Capability degraded before hard fault is detected | Health monitoring thresholds, cleaning/service strategy |

### 9.5 ISO 8800 Evaluation

ISO 8800 applies because AI or data-driven perception behavior can be unsafe even without a classical software fault. The safety case must show that data, model training, validation, release, and field monitoring support the safety role of the LiDAR item.

| ISO 8800 clause coverage | Concrete ticked evidence in this example |
|---|---|
| Clause 8 assurance argument | Function-to-risk-to-evidence traceability and residual-risk statement |
| Clause 9 AI safety requirements | Requirements for uncertainty, conservative output, dataset coverage, safety KPIs |
| Clause 10 architectural/development measures | Fusion cross-checks, OOD handling, degraded-mode logic, release controls |
| Clause 11 data/dataset assurance | ODD/class/weather/occlusion coverage, label QA, dataset maintenance |
| Clause 12 AI component testing | Robustness, OOD, rare VRU, noisy point-cloud, and regression tests |
| Clause 13 AI system safety analysis | Dataset gaps and model failure modes linked to unsafe braking/planning effects |
| Clause 14 operation/continuous assurance | Field monitoring, drift detection, near-miss feedback, OTA gates, rollback |
| Clause 15.6 model training/evaluation | Controlled training, independent validation, safety KPIs, model-selection rationale |

### 9.6 Final Evaluation

The LiDAR perception item is acceptable for development only if the safety case demonstrates three things: E/E malfunctions are detected or controlled under ISO 26262; intended-function limitations are identified and reduced under SOTIF; and AI/data/model behavior is assured through dataset, model, release, and field-monitoring evidence under ISO 8800.

The residual risk remains high if the system has no credible uncertainty output, no stale-data invalidation, no field drift monitoring, or no blocked-release criteria for safety-critical perception regressions.

### 9.7 Evidence Credibility and Release Decision

| Evidence area | Weak evidence | Stronger evidence expected for release |
|---|---|---|
| Functional safety | Desk analysis only | Fault injection showing stale data, CRC errors, frozen tracks, calibration offsets, and interface faults are detected or invalidated in time |
| SOTIF | A few nominal demonstrations | Scenario-based validation across rain, spray, occlusion, low reflectivity, dense traffic, road edges, and ODD boundary cases |
| ISO 8800 AI assurance | Average model accuracy only | Safety KPI suite by ODD, object class, visibility, range, occlusion, uncertainty, and model-release regression |
| Vehicle behavior | Perception-only metrics | Closed-loop evidence showing planning/AEB/fallback behaves safely when LiDAR is wrong, uncertain, stale, or unavailable |
| Post-release monitoring | No feedback loop | Field monitoring for drift, near misses, degraded sensor states, new scenario discovery, and blocked OTA rollout on regression |

Release judgment: do not release a LiDAR perception update if it improves average detection but regresses any safety-critical scenario such as short-TTC VRU detection, stale-data invalidation, confidence calibration, or degraded-sensor behavior.
