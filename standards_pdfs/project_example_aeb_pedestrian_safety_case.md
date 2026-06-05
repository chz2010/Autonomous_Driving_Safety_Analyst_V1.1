# Project-Generated Example Safety Case: AEB Pedestrian Perception Item

Status: Project-generated worked example. This is not official ISO text. Use it as a pattern for engineering-style RAG answers, with official standards retrieved separately.

## 0. Public Safety-Case Practice Alignment

This synthetic example is strengthened using public safety-case practices from autonomous-driving literature and safety reports. It is not an approved safety case. It should be read as a structured example of how to argue absence of unreasonable risk for one AEB pedestrian/cyclist perception item.

| Public safety-case principle | How this example applies it |
|---|---|
| Explain the system under analysis | Defines the AEB perception item boundary, functions, inputs, outputs, operating modes, ODD assumptions, and braking safety role |
| Use a claim-argument-evidence logic | Links VRU perception functions to hazards, HARA, safety goals, SOTIF triggering conditions, ISO 8800 AI risks, tests, and residual-risk judgments |
| Make acceptance criteria explicit | Requires VRU safety KPIs, TTC margins, confidence behavior, valid/invalid interface logic, release gates, and blocked-release rules |
| Use multiple evidence sources | Combines HARA, scenario validation, simulation, fault injection, closed-loop AEB testing, dataset evidence, field monitoring, and near-miss review |
| Pressure-test the argument | Requires occluded children, cyclists behind vehicles, dark clothing, glare, rain, unusual poses, short TTC, and ODD boundary cases |
| Maintain safety after release | Includes field monitoring, near-miss mining, drift detection, OTA gates, staged rollout, rollback, and scenario catalogue updates |

## 1. Item Definition

Assumed item: AEB pedestrian perception and decision-support item that identifies pedestrians/cyclists, estimates collision risk, and provides valid object and confidence information to AEB control.

| Element | Example content |
|---|---|
| Item description | AEB pedestrian/cyclist perception and decision-support item that identifies vulnerable road users, estimates collision relevance, provides confidence/freshness information, and supplies valid object data to AEB control |
| Item boundary | Perception model, object tracking, collision relevance estimation, confidence output, diagnostics, AEB interface |
| Main functions | Pedestrian/cyclist detection, classification, distance estimation, relative velocity estimation, collision relevance estimation, tracking, confidence/uncertainty output, sensor health monitoring, calibration monitoring, timestamp/data freshness, interface output to AEB |
| Inputs | Camera/radar/LiDAR features or fused object inputs, ego speed, yaw rate, timestamp, calibration, sensor health |
| Outputs | Pedestrian/cyclist object, class, distance, relative velocity, time-to-collision, confidence, valid/invalid flag |
| Operating modes | Normal AEB perception, degraded/low-confidence mode, warning-only or restricted mode, disabled/fallback mode, service/calibration mode, post-update monitoring mode |
| ODD assumptions | Defined speed range, road classes, weather/lighting limits, sensor availability, AEB activation boundary |
| Safety role | Supports emergency braking or warning when a vulnerable road user is in the predicted path |

## 2. Functional Decomposition

| Function | Output | ISO 26262 malfunction example | SOTIF insufficiency example | ISO 8800 AI/data/model concern | HARA carried forward? |
|---|---|---|---|---|---|
| Pedestrian/cyclist detection | Object existence | VRU object not output due to software/interface fault | Child behind parked car detected too late | Dataset lacks occluded children/cyclists at night | Yes |
| Classification | VRU class | Pedestrian classified as sign/post | Unusual pose, wheelchair user, stroller, e-scooter | Label taxonomy and minority-class gaps | Yes |
| Distance estimation | Range to VRU | Range overestimated | Low light or sensor noise reduces range reliability | Sparse/blurred cases underrepresented | Yes |
| Relative velocity estimation | Closing speed | Wrong velocity from timestamp/tracking fault | Crossing pedestrian velocity unstable | Sequence data lacks sudden crossing cases | Yes |
| Collision relevance | In-path / out-of-path relevance | Relevant VRU marked non-relevant | Ambiguous pedestrian intent near curb | Model weak on intent and lateral motion | Yes |
| Tracking | Track continuity | Track lost or swapped | Occlusion by bus/vehicle | Temporal model weak after occlusion | Yes |
| Confidence output | Confidence/uncertainty | Confidence stuck high | Confidence high under glare/rain/night | Overconfidence on OOD scenes | Yes |
| Sensor health monitoring | Degradation status | Camera/radar/LiDAR degradation not reported | Dirty lens below diagnostic threshold | Field degradation not represented | Yes |
| Calibration monitoring | Alignment status | Sensor misalignment not detected | Small offset shifts pedestrian location | Validation lacks service/misalignment cases | Yes |
| Timestamp/data freshness | Freshness flag | Stale frame/object used | Processing latency under dense traffic | Latency not included in safety KPI | Yes |
| Interface output to AEB | AEB object message | Invalid object message accepted | AEB overtrusts low-confidence perception | End-to-end release KPI misses late braking | Yes |

## 3. HARA Screening Example

Baseline assumptions: AEB active; urban driving 30-50 km/h for VRU scenarios and higher speed cases where relevant; driver reaction may be too late for short TTC; ratings are engineering estimates requiring project confirmation.

| Function | Malfunction / insufficiency | Hazardous event | Operational situation | S rationale | E rationale | C rationale | ASIL/QM | Next action |
|---|---|---|---|---|---|---|---|---|
| Pedestrian/cyclist detection | Missed VRU | Vehicle does not brake for pedestrian/cyclist | Urban crossing, 50 km/h | S3 because VRU collision can be fatal | E3 urban VRU exposure is common | C3 when TTC is short and driver expects AEB | ASIL D candidate | Safety goal for VRU detection or fail-safe warning/braking |
| Classification | VRU misclassified as non-threat | AEB suppresses braking | School zone or urban crossing | S3 for VRU injury/fatality | E2-E3 depending ODD | C2-C3 depending visibility/TTC | ASIL C-D | Conservative unknown-object handling |
| Distance estimation | Range overestimated | Braking starts too late | Pedestrian crossing ahead | S3 due to insufficient stopping distance | E3 in urban ODD | C3 when driver has little time | ASIL D candidate | Range plausibility and stopping-distance margin |
| Relative velocity estimation | Closing speed underestimated | Insufficient deceleration | Cyclist crossing or lead VRU | S2-S3 depending speed | E2-E3 depending scenario | C2-C3 depending TTC | ASIL B-D | Velocity consistency and TTC validation |
| Collision relevance | In-path VRU marked out-of-path | No AEB despite collision course | Pedestrian near curb entering path | S3 | E2-E3 | C3 for sudden entry | ASIL D candidate | Path prediction and conservative relevance logic |
| Tracking | Track lost after occlusion | Delayed re-detection/braking | Child behind parked car | S3 | E2 common enough in urban ODD | C3 due to sudden appearance | ASIL D candidate | Occlusion-aware tracking and braking preparedness |
| Confidence output | Unsafe high confidence | AEB trusts wrong perception | Night/rain/glare | S3 if wrong decision suppresses braking | E2-E3 depending ODD | C2-C3 due to driver overtrust | ASIL C-D plus ISO 8800 | Confidence calibration and ODD restriction |
| Sensor health monitoring | Degraded sensor not reported | AEB remains active but blind/degraded | Dirt, spray, sensor fault | S3 | E2-E3 | C2-C3 depending warning/fallback | ASIL C-D | Diagnostic and feature-disable criteria |
| Calibration monitoring | Sensor offset not detected | Object location shifted out of path | After service/impact | S3 if VRU is missed | E1-E2 | C3 if output appears plausible | ASIL C-D | Calibration plausibility and service checks |
| Timestamp/data freshness | Stale object used | AEB brakes too late or unnecessarily | Dense traffic, compute overload | S2-S3 | E2 | C2-C3 depending braking event | ASIL B-D | Freshness timeout and invalidation |
| Interface output to AEB | Invalid object message accepted | No braking or false braking | Any AEB-active scenario | S2-S3 depending event | E3 if interface is continuous | C2-C3 depending speed/following traffic | ASIL B-D | Interface checks, valid flags, CRC/counter |

## ISO 26262 Part Coverage Headings

### ISO 26262 Part 4 Coverage: System Development

This example covers Part 4 through AEB perception system architecture, technical safety requirements, allocation to perception, fusion, braking interface, HMI/fallback behavior, integration testing, and vehicle-level AEB validation.

### ISO 26262 Part 5 Coverage: Hardware Development

This example covers Part 5 through camera/radar/LiDAR hardware assumptions, power/timing/communication fault considerations, diagnostic coverage, hardware fault injection, and hardware evidence supporting AEB perception safety requirements.

### ISO 26262 Part 6 Coverage: Software Development

This example covers Part 6 through perception and AEB interface software safety requirements, object freshness checks, plausibility checks, watchdogs, confidence handling, invalid-output suppression, degraded-mode logic, and unit/integration verification.

### ISO 26262 Part 7 Coverage: Production, Operation, Service, and Decommissioning

This example covers Part 7 through end-of-line sensor calibration, service recalibration, diagnostic trouble codes, field monitoring, update restrictions, and disabling criteria when AEB perception capability is degraded.

### ISO 26262 Part 8 Coverage: Supporting Processes

This example covers Part 8 through configuration management, change management, requirements traceability, verification planning, documentation, tool confidence, release evidence management, and safety case maintenance.

### ISO 26262 Part 9 Coverage: ASIL-Oriented and Safety-Oriented Analyses

This example covers Part 9 through ASIL decomposition, dependent failure analysis, common-cause and cascading-failure analysis, freedom from interference between perception and braking functions, FMEA, FTA, and DFA.

## 4. SOTIF Function Analysis Pattern

### SOTIF Coverage: Intended Functionality, ODD, Triggering Conditions, and Residual Risk

This example covers SOTIF by analyzing AEB pedestrian/cyclist functions that can be unsafe without an E/E malfunction, including occlusion, dark clothing, rain, glare, small children, wheelchairs, strollers, cargo bikes, sudden crossings, driver overtrust, and operation outside the validated ODD.

| Function | Intended-function insufficiency | Triggering condition | Risk reduction |
|---|---|---|---|
| Pedestrian/cyclist detection | Late detection without component fault | Occlusion, dark clothing, rain, glare, small child | Reduce speed under uncertainty, expand scenario validation |
| Classification | Unusual VRU not recognized | Wheelchair, stroller, cargo bike, e-scooter | Unknown-object conservative treatment |
| Collision relevance | Pedestrian intent misread | Near curb, jaywalking, group pedestrians | Conservative path prediction and TTC margin |
| Confidence output | Confidence not reduced in degraded scene | Night, wet road, sensor blockage | Confidence threshold and fallback warning |

## 5. ISO 8800 AI Assurance Pattern

### ISO 8800 Coverage: AI Safety, Data, Model Robustness, Release, and Monitoring

This example covers ISO 8800 by analyzing AI/data/model risks for AEB pedestrian perception, including dataset coverage for VRUs, label quality, rare poses, occlusion, low visibility, robustness, uncertainty calibration, OOD/distribution shift, release gates, OTA regression, drift monitoring, and field feedback from near misses.

#### ISO 8800 Clause 8 Coverage: Assurance Arguments for AI Systems

This example supports an AI safety assurance argument by linking AEB perception functions, hazardous missed/false detections, AI/data/model weaknesses, evidence, release gates, and residual risk into a traceable safety case.

#### ISO 8800 Clause 9 Coverage: AI Safety Requirements

This example derives AI-related safety requirements for AEB perception, such as safe uncertainty behavior, conservative output under degraded perception, dataset coverage requirements for vulnerable road users, and release-blocking safety KPIs.

#### ISO 8800 Clause 10 Coverage: Architectural and Development Measures for AI Systems

This example covers architectural and development measures such as sensor fusion cross-checks, confidence thresholds, OOD handling, degraded-mode logic, perception-to-AEB interface validity checks, model version control, and release criteria for AI-enabled AEB perception.

#### ISO 8800 Clause 11 Coverage: Data and Dataset Assurance

This example covers data requirements, dataset design, dataset implementation, label quality, dataset maintenance, and dataset safety evidence for pedestrians, cyclists, children, unusual poses, occlusion, low visibility, glare, rain, and regional traffic behavior.

#### ISO 8800 Clause 12 Coverage: AI Component Testing

This example covers AI component testing through robustness tests, OOD tests, rare VRU scenario tests, confidence calibration tests, false-negative stress tests, and model-regression tests.

#### ISO 8800 Clause 13 Coverage: Safety Analysis of the AI System

This example covers AI system safety analysis by connecting model failure modes, dataset gaps, uncertainty behavior, distribution shift, and unsafe downstream AEB/planning effects.

#### ISO 8800 Clause 14 Coverage: Operation and Continuous Assurance

This example covers operational AI assurance through field monitoring, drift detection, incident and near-miss feedback, dataset updates, OTA release gates, staged rollout, and rollback criteria.

#### ISO 8800 Clause 15.6 Coverage: Data-Driven AI Model Training and Evaluation

This example covers data-driven AI model training and evaluation by requiring controlled training datasets, independent validation data, safety-relevant KPIs, robustness checks, uncertainty calibration, regression tests, and documented model-selection rationale before release.

| AI-related area | Example risk | Required evidence |
|---|---|---|
| Dataset coverage | Few rainy-night occluded pedestrians/cyclists | ODD/class/scenario coverage matrix |
| Label quality | Missing labels for partially occluded VRUs | Label QA, defect rate, correction process |
| Robustness | Model fails on blur, glare, low contrast | Stress and perturbation tests |
| Uncertainty | Overconfident false negative | Calibration and OOD validation |
| Release gate | OTA update regresses child/cyclist detection | Safety KPI regression suite and blocked release rule |
| Monitoring | Near misses reveal unseen scenarios | Field monitoring and scenario feedback loop |

## 6. Verification and Operation Pattern

| Area | Example evidence | Rationale |
|---|---|---|
| ISO 26262 tests | Sensor fault, stale timestamp, corrupted object, interface invalid flag | Ensures E/E faults do not silently suppress AEB |
| SOTIF tests | Occluded child, cyclist behind bus, dark clothing at night, glare | Ensures intended function handles triggering conditions safely |
| ISO 8800 tests | Rare VRU poses, regional variation, OOD objects, confidence calibration | Ensures AI evidence supports release |
| Production/operation | EOL calibration, DTCs, OTA release gates, near-miss review | Maintains safety argument in field use |

## 7. Evaluated Sample Answer: AEB Pedestrian Perception Safety Case

This section is a completed example answer, not only an instruction template. It shows how to evaluate an AEB pedestrian/cyclist perception item with engineering rationale.

### 7.1 Engineering Judgment

The AEB pedestrian perception item is safety-critical because a missed or late vulnerable-road-user detection can directly suppress emergency braking. The most severe cases are short time-to-collision scenarios where the driver is unlikely to recover after the perception system fails to identify a pedestrian or cyclist.

The safety case must evaluate all functions that contribute to AEB activation, not just detection. Classification, distance, relative velocity, collision relevance, tracking, confidence, timestamp freshness, calibration, and the AEB interface can each cause unsafe braking behavior.

### 7.2 Function-Level Evaluation

| Function | Main safety concern | Evaluation judgment | Required engineering evidence |
|---|---|---|---|
| Pedestrian/cyclist detection | VRU missed or detected too late | Safety-critical; main AEB hazard path | Detection KPI by VRU type, occlusion, lighting, range, TTC |
| Classification | VRU treated as non-threat | Safety-critical if class gates braking | VRU confusion matrix, unknown-object policy, label QA |
| Distance estimation | Range overestimated | Safety-critical because braking starts too late | Range error budget, stopping-distance margin, calibration tests |
| Relative velocity estimation | Closing speed underestimated | Safety-critical for TTC and deceleration demand | Velocity consistency, timestamp checks, crossing-object validation |
| Collision relevance | In-path VRU marked out-of-path | Safety-critical because braking is suppressed | Path prediction tests, lateral motion scenarios, conservative relevance logic |
| Tracking | Track lost after occlusion | Safety-critical in urban child/cyclist scenarios | Occlusion re-detection tests, track continuity KPI |
| Confidence output | Overconfident false negative | Strong SOTIF/ISO 8800 concern | Calibration, OOD tests, low-confidence braking/warning logic |
| Sensor health monitoring | Degraded sensor not reported | Safety-critical if AEB remains available but blind | Dirt/spray/blockage tests, DTCs, feature-disable criteria |
| Calibration monitoring | Misalignment shifts VRU position | Safety-critical if object appears outside path | Misalignment tests, service recalibration evidence |
| Timestamp/data freshness | Stale object used | Safety-critical in short-TTC scenes | Freshness timeout, latency budget, high-load tests |
| Interface output to AEB | Invalid object message accepted | Safety-critical interface failure | Valid flags, CRC/counter, AEB integration tests |

### 7.3 ISO 26262 Evaluation

ISO 26262 applies to E/E malfunctions that can cause AEB to brake too late, not brake, or brake unnecessarily. The HARA should evaluate each perception function because each one can create a different hazardous event.

| ISO 26262 lifecycle area | Evaluation for this AEB item |
|---|---|
| Part 3 concept phase | HARA must cover missed VRU, misclassified VRU, wrong distance, wrong velocity, wrong collision relevance, stale data, and invalid AEB interface output. |
| Part 4 system development | System requirements must define valid AEB object output, confidence behavior, fault response, warning, fallback, and braking suppression rules. |
| Part 5 hardware development | Sensor hardware, power, timing, synchronization, and communication faults require hardware safety analysis and diagnostic evidence. |
| Part 6 software development | Software safety requirements must cover TTC calculation, freshness checks, plausibility, watchdogs, confidence handling, and interface validity. |
| Part 7 production/operation | End-of-line calibration, service recalibration, DTCs, sensor cleaning/degradation strategy, and field monitoring are required. |
| Part 8 supporting processes | Traceability, change management, release evidence, model/software configuration, and tool confidence must control every AEB perception update. |
| Part 9 safety analyses | Dependent failure analysis must consider shared perception assumptions, fusion overtrust, common-cause sensor degradation, and braking interface failures. |

### 7.4 SOTIF Evaluation

SOTIF applies when the AEB perception system performs according to design but is insufficient in real scenarios. The most important triggering conditions are occlusion, poor lighting, dark clothing, glare, rain, unusual VRU poses, small children, wheelchairs, strollers, e-scooters, sudden crossings, and driver overtrust.

| Triggering condition | Unsafe mechanism | Required risk reduction |
|---|---|---|
| Child behind parked vehicle | Late detection with short TTC | Occlusion-aware behavior, speed reduction near parked vehicles, scenario validation |
| Cyclist behind bus | Track lost or late reappearance | Conservative prediction and re-detection tests |
| Dark clothing at night | Low contrast and late classification | Dataset expansion, confidence reduction, sensor fusion |
| Rain/glare/wet road | Detection confidence unstable | ODD restriction, degraded-mode warning, robustness tests |
| Unusual VRU type or pose | Misclassification or missed detection | Unknown-object treatment, expanded scenario catalogue |

### 7.5 ISO 8800 Evaluation

ISO 8800 applies to the AI/data/model safety argument for VRU detection and AEB decision support. The model must be justified using safety-relevant evidence, not only average precision.

| ISO 8800 clause coverage | Concrete ticked evidence in this example |
|---|---|
| Clause 8 assurance argument | VRU hazards, AI weaknesses, evidence, release gates, and residual risk are connected |
| Clause 9 AI safety requirements | Requirements for VRU data coverage, uncertainty, safety KPIs, and conservative output |
| Clause 10 architectural/development measures | Sensor fusion, OOD handling, confidence thresholds, degraded-mode logic, interface checks |
| Clause 11 data/dataset assurance | Coverage for children, cyclists, occlusion, night, rain, glare, rare poses, regions |
| Clause 12 AI component testing | Rare VRU, OOD, false-negative, robustness, confidence, and regression tests |
| Clause 13 AI system safety analysis | Dataset/model gaps linked to late braking, no braking, or false braking |
| Clause 14 operation/continuous assurance | Field monitoring, near-miss mining, drift detection, OTA gates, rollback |
| Clause 15.6 model training/evaluation | Controlled training, independent validation, safety KPIs, model-selection rationale |

### 7.6 Final Evaluation

The AEB pedestrian perception item is acceptable for development only if the safety case shows that missed/late VRU detection, wrong range/TTC, stale data, and unsafe confidence behavior are controlled before they suppress braking. The minimum evidence should include VRU scenario coverage, short-TTC validation, occlusion cases, low-light/rain/glare tests, confidence calibration, valid/invalid interface handling, and blocked-release rules for safety regressions.

The residual risk remains high if the model is evaluated mainly on average detection metrics, lacks near-miss/short-TTC cases, has no calibrated uncertainty, or cannot prove that OTA updates do not regress rare but safety-critical VRU scenarios.

### 7.7 Evidence Credibility and Release Decision

| Evidence area | Weak evidence | Stronger evidence expected for release |
|---|---|---|
| Functional safety | AEB object output tested only in nominal cases | Fault injection showing stale objects, invalid flags, wrong TTC, sensor faults, calibration offsets, and interface errors are detected or handled safely |
| SOTIF | Pedestrian tests only in clear daylight | Scenario validation for occluded children, cyclists behind buses, dark clothing, glare, rain, low contrast, unusual poses, and short-TTC cases |
| ISO 8800 AI assurance | Average precision or recall only | Safety KPI suite by VRU type, age/size proxy, pose, occlusion, weather, lighting, range, TTC, uncertainty, and model-release regression |
| Vehicle behavior | Perception-only tests | Closed-loop AEB evidence showing braking/warning/fallback behavior remains safe when perception is uncertain, late, stale, or degraded |
| Post-release monitoring | No near-miss feedback | Field monitoring for missed/late VRU detections, false braking, new VRU types, drift, near misses, and blocked OTA rollout on regression |

Release judgment: do not release an AEB perception update if it improves average detection but regresses occluded VRUs, short-TTC braking, low-light/rain performance, confidence calibration, or invalid-output handling.
