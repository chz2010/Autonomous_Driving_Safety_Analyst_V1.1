# Project-Generated Example Safety Case: Lane Maintaining Perception Item

Status: Project-generated worked example. This is not official ISO text. Use it as an engineering-style reference pattern for complete item-function analysis across ISO 26262, ISO 21448/SOTIF, and ISO 8800.

## 0. Public Safety-Case Practice Alignment

This synthetic example is strengthened using public safety-case practices from autonomous-driving literature and safety reports. It is not an approved safety case. It should be read as a structured example of how to argue absence of unreasonable risk for one lane-maintaining perception item.

| Public safety-case principle | How this example applies it |
|---|---|
| Explain the system under analysis | Defines the lane perception item boundary, functions, inputs, outputs, operating modes, ODD assumptions, and steering/planning safety role |
| Use a claim-argument-evidence logic | Links lane functions to hazards, HARA, safety goals, SOTIF triggering conditions, ISO 8800 AI risks, tests, and residual-risk judgments |
| Make acceptance criteria explicit | Requires lane confidence thresholds, steering disable criteria, freshness limits, model-regression gates, and ODD restriction rules |
| Use multiple evidence sources | Combines HARA, scenario validation, simulation, fault injection, lane-marking datasets, closed-loop steering tests, and field monitoring |
| Pressure-test the argument | Requires glare, rain, faded markings, construction zones, lane split/merge, regional markings, and ODD boundary cases |
| Maintain safety after release | Includes calibration controls, field drift monitoring, incident review, OTA gates, staged rollout, and rollback |

## 1. Item Definition

Assumed item: lane maintaining perception subsystem that detects lane boundaries and road geometry and provides lane model outputs to lane keeping assistance, automated steering, HMI, and fallback logic.

| Element | Example content |
|---|---|
| Item description | Lane-maintaining perception item that converts sensor and vehicle-context inputs into lane model, confidence, freshness, diagnostics, and valid/invalid outputs used by lane keeping assistance or automated steering |
| Item boundary | Camera/perception input processing, lane boundary detection, lane model estimation, confidence output, diagnostics, interface to steering/planning |
| Main functions | Lane boundary detection, lane classification, curvature estimation, lateral offset estimation, lane tracking, confidence/uncertainty output, sensor health reporting, calibration monitoring, timestamp/data freshness, interface output to steering/planning |
| Inputs | Camera images, optional map, ego motion, calibration, timestamp, sensor health |
| Outputs | Lane boundary, lane center, curvature, lateral offset, confidence, lane model freshness, diagnostics, valid/invalid interface flags |
| Operating modes | Normal lane perception, degraded/low-confidence mode, steering-assist disabled mode, service/calibration mode, post-update monitoring mode |
| ODD assumptions | Defined lane-marking types, speed range, road classes, weather/lighting boundaries, driver supervision assumption if L2 |
| Safety role | Prevent unintended lane departure and prevent unsafe steering based on wrong lane model |

## 2. Functional Decomposition

| Function | Output | ISO 26262 malfunction example | SOTIF insufficiency example | ISO 8800 AI/data/model concern | HARA carried forward? |
|---|---|---|---|---|---|
| Lane boundary detection | Left/right lane boundary | False or missing lane boundary due to software fault | Faded markings, glare, snow, temporary construction markings | Dataset lacks rare lane markings and regional variation | Yes |
| Lane classification | Solid/dashed/road edge/construction lane type | Wrong lane type output | Road edge or tar line mistaken for lane | Label inconsistency for lane classes | Yes |
| Curvature estimation | Lane curvature / path model | Wrong curvature due to processing fault | Sharp curve or crest outside assumed visibility | Training data underrepresents high-curvature roads | Yes |
| Lateral offset estimation | Vehicle position in lane | Offset biased by calibration fault | Wide/narrow lane ambiguity | Model biased by lane width distribution | Yes |
| Lane tracking | Temporal lane continuity | Stale or swapped lane track | Lane split/merge causes temporary ambiguity | Temporal instability under distribution shift | Yes |
| Confidence output | Lane confidence / uncertainty | Confidence stuck high | Confidence not reduced for faded/ambiguous markings | Poor calibration of confidence on OOD road scenes | Yes |
| Sensor health reporting | Camera/perception health | Camera degradation not reported | Dirty lens below diagnostic threshold still reduces capability | Field degradation data missing | Yes |
| Calibration monitoring | Camera alignment state | Misalignment not detected | Small misalignment creates systematic lane offset | Validation lacks post-service calibration variation | Yes |
| Timestamp/data freshness | Freshness flag | Stale image/lane model used | Processing delay in high-load scenes | Model not assessed for temporal latency impact | Yes |
| Interface output to steering/planning | Lane model message | Invalid lane model sent as valid | Steering module overtrusts low-confidence lane output | End-to-end KPI lacks unsafe steering cases | Yes |

## 3. HARA Screening Example

Baseline assumptions: lane keeping assistance active; highway 100 km/h and urban 50 km/h cases used where relevant; driver supervision may exist but short time-to-lane-departure limits controllability; ratings are project estimates.

| Function | Malfunction / insufficiency | Hazardous event | Operational situation | S rationale | E rationale | C rationale | ASIL/QM | Next action |
|---|---|---|---|---|---|---|---|---|
| Lane boundary detection | False lane boundary | Vehicle steers toward road edge or adjacent lane | Highway, 100 km/h | S3 possible high-speed collision | E3 highway lane keeping is frequent | C2-C3 depending steering authority and driver reaction time | ASIL C-D | Safety goal for valid lane boundary or degraded steering |
| Lane classification | Road edge classified as lane | Vehicle follows non-lane boundary | Rural/urban road with worn markings | S2-S3 depending road edge and speed | E2-E3 depending ODD | C2 if driver can override, C3 if torque is strong/late | ASIL B-C | Lane-type plausibility and map/fusion cross-check |
| Curvature estimation | Curvature underestimated | Vehicle departs lane in curve | Highway curve, 100 km/h | S3 due to run-off-road or side collision | E2 curves are regular but not continuous | C2-C3 depending TTC/lateral acceleration | ASIL C-D | Curvature limits and steering authority limiter |
| Lateral offset estimation | Offset biased | Vehicle drifts close to lane boundary | Highway or urban lane | S2-S3 depending adjacent traffic | E3 common during lane keeping | C2 if driver notices, C3 if subtle and automated | ASIL B-C | Calibration monitoring and offset plausibility |
| Lane tracking | Stale lane model | Steering based on old lane geometry | Lane split/merge or construction | S3 possible wrong path | E2 in complex roads/construction | C2-C3 due to ambiguity and short reaction time | ASIL C-D | Freshness timeout and track reset logic |
| Confidence output | Overconfident ambiguous lane | System remains active beyond capability | Glare/rain/faded markings | S3 if steering continues incorrectly | E2-E3 depending weather/road marking exposure | C2-C3 depending driver overtrust | ASIL C-D plus SOTIF/ISO 8800 concern | Confidence calibration and ODD restriction |
| Sensor health reporting | Dirty camera not detected | Lane model degraded but still used | Rain/dirt/spray | S2-S3 depending speed | E2-E3 depending weather/maintenance | C2-C3 if driver overtrusts function | ASIL B-D | Health diagnostics and feature disable criteria |
| Calibration monitoring | Camera pitch/yaw offset not detected | Lane position shifted | After service or minor impact | S2-S3 depending speed/traffic | E1-E2 lower frequency but credible | C2-C3 because output appears plausible | ASIL B-C | Calibration plausibility and service procedure |
| Timestamp/data freshness | Stale lane output | Late steering correction | ECU high load, fast lane change | S2-S3 depending speed | E2 under high-load/complex scenes | C2-C3 depending delay | ASIL B-D | Timestamp check and stale output invalidation |
| Interface output to steering/planning | Invalid lane model accepted | Steering request based on unsafe data | Any active lane-keeping scenario | S3 if steering causes departure | E3 continuous interface use | C2-C3 depending override and torque | ASIL C-D | Interface safety mechanism and invalid signal handling |

## ISO 26262 Part Coverage Headings

### ISO 26262 Part 4 Coverage: System Development

This example covers Part 4 through lane-maintaining system architecture, technical safety requirements, allocation to perception, steering/planning interface, HMI/fallback behavior, integration testing, and vehicle-level validation.

### ISO 26262 Part 5 Coverage: Hardware Development

This example covers Part 5 through camera/sensor hardware assumptions, power/timing/communication fault considerations, diagnostic coverage, hardware fault injection, and hardware evidence needed to support lane perception safety requirements.

### ISO 26262 Part 6 Coverage: Software Development

This example covers Part 6 through lane perception software safety requirements, lane-model freshness checks, plausibility checks, watchdogs, confidence handling, degraded-mode logic, and unit/integration verification.

### ISO 26262 Part 7 Coverage: Production, Operation, Service, and Decommissioning

This example covers Part 7 through end-of-line camera calibration, service recalibration after repair, diagnostic trouble codes, field monitoring, update restrictions, and disabling criteria when lane perception capability is degraded.

### ISO 26262 Part 8 Coverage: Supporting Processes

This example covers Part 8 through configuration management, change management, requirements traceability, verification planning, documentation, tool confidence, and safety case evidence management.

### ISO 26262 Part 9 Coverage: ASIL-Oriented and Safety-Oriented Analyses

This example covers Part 9 through ASIL decomposition, dependent failure analysis, common-cause and cascading-failure analysis, freedom from interference between perception and steering functions, FMEA, FTA, and DFA.

## 4. SOTIF Function Analysis Pattern

### SOTIF Coverage: Intended Functionality, ODD, Triggering Conditions, and Residual Risk

This example covers SOTIF by analyzing lane-maintaining functions that can be unsafe without an E/E malfunction, including faded markings, construction lanes, lane merges/splits, glare, rain/snow, missing markings, unusual lane colors, shadows, road-edge confusion, driver overtrust, and operation outside ODD.

| Function | Intended-function insufficiency | Triggering condition | ODD / validation action | Risk reduction |
|---|---|---|---|---|
| Lane boundary detection | Lane boundary not reliably perceived although no fault exists | Faded markings, glare, snow, shadows | Scenario catalogue for markings, weather, road surface, construction | Confidence reduction, disable steering assist, driver warning |
| Lane classification | Non-lane marking mistaken for lane | Road edge, tar line, temporary yellow line | Validate regional markings and construction zones | Conservative lane-type handling |
| Lane tracking | Track discontinuity in merge/split | Lane split, ramp, construction | Known/unknown unsafe scenario discovery | Reduce steering authority or request driver takeover |
| Confidence output | Confidence fails to represent uncertainty | Ambiguous markings or ODD boundary | Confidence calibration against scenario catalogue | ODD restriction and fallback |

## 5. ISO 8800 AI Assurance Pattern

### ISO 8800 Coverage: AI Safety, Data, Model Robustness, Release, and Monitoring

This example covers ISO 8800 by analyzing AI/data/model risks for lane perception, including lane-label consistency, rare lane geometries, construction zones, night/rain/glare, regional road-marking variation, temporal stability, confidence calibration, model release gates, OTA regression, drift monitoring, and unsafe overconfidence.

#### ISO 8800 Clause 8 Coverage: Assurance Arguments for AI Systems

This example supports an AI safety assurance argument by linking lane-maintaining perception functions, hazardous behavior, AI/data/model weaknesses, verification evidence, release gates, and residual risk into one traceable safety case.

#### ISO 8800 Clause 9 Coverage: AI Safety Requirements

This example derives AI-related safety requirements for lane perception, such as safe confidence behavior, temporal stability requirements, conservative output under unclear lane evidence, dataset coverage requirements, and blocked-release criteria for safety KPI regression.

#### ISO 8800 Clause 10 Coverage: Architectural and Development Measures for AI Systems

This example covers architectural and development measures such as camera/radar/map cross-checks, lane-confidence thresholds, temporal smoothing, OOD detection for unfamiliar road markings, degraded-mode logic, model version control, and release criteria for AI-enabled lane perception.

#### ISO 8800 Clause 11 Coverage: Data and Dataset Assurance

This example covers data requirements, dataset design, dataset implementation, label quality, dataset maintenance, and dataset safety evidence for lane markings, road edges, construction zones, lane splits/merges, night/rain/glare, and regional road-marking variation.

#### ISO 8800 Clause 12 Coverage: AI Component Testing

This example covers AI component testing through robustness tests, OOD tests, temporal consistency tests, rare lane-geometry tests, confidence calibration tests, and regression tests for new perception model releases.

#### ISO 8800 Clause 13 Coverage: Safety Analysis of the AI System

This example covers AI system safety analysis by connecting model failure modes, dataset gaps, uncertainty behavior, distribution shift, temporal instability, and unsafe downstream steering/planning effects.

#### ISO 8800 Clause 14 Coverage: Operation and Continuous Assurance

This example covers operational AI assurance through field monitoring, drift detection, incident and near-miss feedback, dataset updates, OTA release gates, staged rollout, and rollback criteria.

#### ISO 8800 Clause 15.6 Coverage: Data-Driven AI Model Training and Evaluation

This example covers data-driven AI model training and evaluation by requiring controlled training datasets, independent validation data, safety-relevant KPIs, robustness checks, uncertainty calibration, regression tests, and documented model-selection rationale before release.

| AI-related function | Data / model risk | Release evidence |
|---|---|---|
| Lane boundary detection | Dataset missing faded, wet, snow-covered, regional, or construction markings | Dataset coverage matrix and lane-marking scenario tests |
| Lane classification | Labels inconsistent across solid/dashed/temporary/road-edge classes | Label QA and class taxonomy checks |
| Lane tracking | Temporal instability after occlusion or lane split | Sequence validation and temporal consistency KPI |
| Confidence output | Unsafe overconfidence on unfamiliar markings | Calibration curves, OOD tests, release gate for confidence safety KPI |
| OTA model update | Regression in rare lane geometry or lighting | Safety regression suite and staged rollout evidence |

## 6. Verification and Operation Pattern

| Area | Example evidence | Rationale |
|---|---|---|
| ISO 26262 tests | Inject false lane, stale model, calibration offset, invalid interface flag | Confirms faults are detected or vehicle enters degraded behavior |
| SOTIF tests | Faded markings, glare, rain, construction zones, lane merges/splits | Confirms limitations are handled without unsafe steering |
| ISO 8800 tests | Regional lane markings, rare geometries, OOD road scenes, confidence calibration | Confirms AI model behavior is safe across intended ODD |
| Production/operation | EOL camera calibration, service recalibration, DTCs, OTA rollback, field monitoring | Maintains evidence after production and updates |

## 7. Evaluated Sample Answer: Lane Maintaining Perception Safety Case

This section is a completed example answer, not only an instruction template. It shows how to evaluate a lane maintaining perception item with function-by-function depth.

### 7.1 Engineering Judgment

The lane maintaining perception item is safety-relevant because a wrong lane model can directly influence steering. The key engineering risk is not only a total camera or perception failure. The more dangerous case is a plausible but wrong lane boundary, curvature, lateral offset, or confidence value that keeps the lane keeping function active when it should degrade or hand back control.

For this item, a complete analysis must evaluate each lane perception function that contributes to steering, HMI, fallback, or ODD decisions. It is not sufficient to analyze only lane boundary detection.

### 7.2 Function-Level Evaluation

| Function | Main safety concern | Evaluation judgment | Required engineering evidence |
|---|---|---|---|
| Lane boundary detection | False/missing lane boundary | Safety-critical; can cause unintended lane departure | Lane detection KPI by road type, marking type, weather, lighting |
| Lane classification | Road edge or temporary marking treated as valid lane | Safety-critical when classification affects steering permission | Class taxonomy, label QA, construction-zone validation |
| Curvature estimation | Curve underestimated or overestimated | Safety-critical at high speed and in tight curves | Curvature error budget, curve scenario validation |
| Lateral offset estimation | Vehicle position biased within lane | Safety-critical if steering correction is wrong or delayed | Calibration evidence, lateral offset accuracy tests |
| Lane tracking | Stale or unstable lane track | Safety-critical in merge/split/construction zones | Temporal consistency KPI, stale-track invalidation |
| Confidence output | Overconfident ambiguous lane model | Strong SOTIF/ISO 8800 concern | Confidence calibration, ODD boundary tests |
| Sensor health reporting | Dirty/degraded camera not reported | Safety-critical if lane keeping remains active | DTC strategy, dirt/spray/glare degradation tests |
| Calibration monitoring | Misalignment not detected | Safety-critical due to systematic lane-position shift | Service calibration checks, misalignment fault injection |
| Timestamp/data freshness | Old lane model used | Safety-critical during lane changes and curves | Freshness timeout, latency budget, high-load tests |
| Interface output to steering/planning | Invalid lane model accepted | Safety-critical cross-item interface failure | Valid flags, CRC/counter, steering integration tests |

### 7.3 ISO 26262 Evaluation

ISO 26262 applies to malfunctions that can make the lane model wrong, stale, invalid, or misleading. For lane maintaining, HARA should evaluate each function because different functions create different hazardous events: lane departure, unintended steering, failure to warn, or failure to disengage.

| ISO 26262 lifecycle area | Evaluation for this lane maintaining item |
|---|---|
| Part 3 concept phase | HARA must cover false lane boundary, wrong lane type, wrong curvature, biased offset, stale lane model, overconfident output, missed sensor degradation, and invalid interface output. |
| Part 4 system development | System requirements must specify valid/invalid lane model behavior, steering authority limits, fallback, HMI warning, and ODD restrictions. |
| Part 5 hardware development | Camera hardware, power, timing, communication, and mounting failures require diagnostic assumptions and fault-injection evidence. |
| Part 6 software development | Software safety requirements must cover lane-model plausibility, freshness, confidence handling, watchdogs, invalid-output suppression, and interface checks. |
| Part 7 production/operation | End-of-line camera calibration, service recalibration, DTCs, field monitoring, and update restrictions are required because lane performance depends strongly on mounting and calibration. |
| Part 8 supporting processes | Requirements traceability, configuration control, tool confidence, model/software versioning, and change impact analysis are required for every perception update. |
| Part 9 safety analyses | Dependent failure analysis must consider shared assumptions between camera perception, map input, steering controller, HMI, and driver supervision. |

### 7.4 SOTIF Evaluation

SOTIF applies when lane perception is insufficient without a component fault. Typical triggering conditions include faded markings, glare, wet roads, snow-covered lanes, construction markings, lane merges/splits, unusual regional markings, shadows, and road edges that look like lane boundaries.

| Triggering condition | Unsafe mechanism | Required risk reduction |
|---|---|---|
| Faded or missing markings | Lane boundary is uncertain or missed | Reduce confidence, warn driver, reduce or disable steering assist |
| Construction zone | Temporary markings conflict with old lane logic | Scenario catalogue, map/fusion cross-check, conservative lane selection |
| Glare or wet road reflection | False lane boundary or poor contrast | Confidence degradation and ODD restriction |
| Lane merge/split | Track ambiguity and wrong path selection | Temporal validation, track reset, driver takeover request |
| Regional marking variation | Model misinterprets unfamiliar lane style | Dataset expansion, OOD detection, release gate by region |

### 7.5 ISO 8800 Evaluation

ISO 8800 applies to the AI/data/model part of lane perception. The evidence must prove that the model is not only accurate on average, but safe for rare and safety-relevant lane cases.

| ISO 8800 clause coverage | Concrete ticked evidence in this example |
|---|---|
| Clause 8 assurance argument | Lane functions, hazards, AI weaknesses, test evidence, and residual risk are linked |
| Clause 9 AI safety requirements | Requirements for confidence, temporal stability, ODD handling, and release-blocking safety KPIs |
| Clause 10 architectural/development measures | Map/fusion cross-checks, lane-confidence thresholds, OOD handling, degraded-mode logic |
| Clause 11 data/dataset assurance | Coverage for markings, regions, lighting, weather, construction, curves, lane splits/merges |
| Clause 12 AI component testing | Robustness tests, rare lane geometry tests, OOD tests, confidence calibration |
| Clause 13 AI system safety analysis | Dataset gaps and model errors linked to unsafe steering and lane departure |
| Clause 14 operation/continuous assurance | Field drift, near-miss feedback, OTA gates, staged rollout, rollback |
| Clause 15.6 model training/evaluation | Controlled training, independent validation, temporal sequence tests, model-selection rationale |

### 7.6 Final Evaluation

The lane maintaining perception item is acceptable for development only if the safety case shows that wrong or uncertain lane outputs do not silently create steering commands. The minimum engineering expectation is valid/invalid lane output handling, confidence-to-action logic, freshness checks, calibration monitoring, ODD restrictions, and a release gate that blocks model updates which regress safety-critical lane scenarios.

The residual risk remains high if the system remains active under ambiguous lane markings, lacks calibrated confidence, lacks construction-zone validation, or cannot detect stale/misaligned lane model outputs.

### 7.7 Evidence Credibility and Release Decision

| Evidence area | Weak evidence | Stronger evidence expected for release |
|---|---|---|
| Functional safety | Only lane-detection accuracy reports | Fault injection showing stale lane models, invalid flags, calibration offsets, timing faults, and interface errors are detected or handled safely |
| SOTIF | Tests only on clear highway lanes | Scenario validation for faded markings, glare, rain, snow, construction zones, road edges, lane split/merge, and regional marking variation |
| ISO 8800 AI assurance | Mean lane accuracy or IoU only | Safety KPI suite for lane class, curvature, offset, temporal stability, confidence calibration, OOD detection, and model-release regression |
| Vehicle behavior | Perception tests without steering response | Closed-loop evidence showing steering assist reduces authority, disables, or warns when lane model confidence/freshness is insufficient |
| Post-release monitoring | No drift or incident feedback | Field monitoring for new road-marking styles, construction patterns, weather-related degradation, near misses, and OTA rollback triggers |

Release judgment: do not release a lane perception update if it improves normal-road accuracy but regresses construction-zone behavior, confidence calibration, temporal stability, stale-output handling, or steering disable behavior.
