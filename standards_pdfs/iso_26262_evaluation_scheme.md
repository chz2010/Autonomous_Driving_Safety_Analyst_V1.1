# ISO 26262 Evaluation Scheme for Road Vehicle Functional Safety

This document is an original project-specific evaluation scheme based on ISO 26262 functional-safety concepts. It is not a copy of ISO text. Use it as a structured checklist for evaluating E/E safety-related items in road vehicles.

## Purpose

ISO 26262 evaluation asks whether hazards caused by malfunctioning behavior of electrical/electronic systems have been identified, classified, controlled, verified, validated, and managed across the safety lifecycle.

This scheme complements:

- ISO 21448 / SOTIF, which evaluates unreasonable risk from intended-function limitations without malfunction;
- ISO 8800, which evaluates AI-specific risks such as data coverage, robustness, uncertainty, and model lifecycle;
- NCAP/IIHS assessment evidence, which can support external safety-performance expectations but does not replace ISO 26262 lifecycle evidence.

## Evaluation Flow

| Step | Evaluation question | Required evidence | Engineering output |
| --- | --- | --- | --- |
| 1. Item definition | What item/function is being developed and what are its boundaries? | Item definition, interfaces, assumptions, ODD/use cases, dependencies | Item definition and boundary diagram |
| 2. Safety lifecycle planning | Which ISO 26262 activities, roles, and confirmation measures are required? | Safety plan, DIA if applicable, responsibility matrix, lifecycle tailoring | Functional safety management plan |
| 3. Impact analysis | Is this a new item, modification, reuse, or integration of existing elements? | Change description, affected work products, reuse assumptions | Impact analysis and lifecycle tailoring |
| 4. HARA | Which hazardous events arise from malfunctioning behavior? | Operational situations, malfunction list, hazardous events, S/E/C rationale | HARA table and ASIL determination |
| 5. Safety goals | What top-level safety goals prevent unreasonable risk? | HARA result, ASIL, safe state assumptions | Safety goals with ASIL |
| 6. Functional safety concept | What vehicle-level safety behavior satisfies the safety goals? | Functional safety requirements, fault reactions, degraded modes | Functional safety concept |
| 7. Technical safety concept | How are safety requirements allocated to system architecture? | Technical safety requirements, system architecture, interfaces | Technical safety concept and allocation |
| 8. System development | Does the system architecture satisfy safety requirements? | System design, integration plan, verification, validation | System safety evidence |
| 9. Hardware development | Are random hardware failures controlled? | FMEDA, FMEA, FTA, SPFM/LFM, PMHF, diagnostic coverage | Hardware safety evidence |
| 10. Software development | Are software safety requirements implemented and verified? | Software architecture, unit tests, integration tests, freedom from interference | Software safety evidence |
| 11. Safety analyses | Are dependent failures, common-cause failures, and cascading failures addressed? | DFA, FMEA, FTA, interface analysis, freedom-from-interference evidence | Safety-analysis report |
| 12. Verification and validation | Are requirements verified and safety goals validated at vehicle level? | Test reports, reviews, fault injection, HIL/SIL/vehicle tests | V&V evidence |
| 13. Confirmation measures | Has the safety case been independently reviewed/audited as needed? | Confirmation reviews, functional safety audit, assessment evidence | Confirmation measure records |
| 14. Production and operation | Is safety maintained after release? | Production control, service instructions, diagnostics, field monitoring | Production/operation safety evidence |
| 15. Safety case | Is there a coherent argument that residual risk is acceptable? | Evidence traceability, unresolved issues, assumptions, release decision | Safety case / release argument |

## Item Definition Checklist

| Item definition area | What to define | Why it matters |
| --- | --- | --- |
| Function | What the item does and what safety function it supports | Prevents unclear safety responsibility |
| Boundaries | Included/excluded elements, sensors, ECUs, actuators, HMI | Prevents missing interfaces |
| Inputs | Sensor data, vehicle state, maps, driver input, external commands | Identifies input failures and assumptions |
| Outputs | Warnings, object list, braking command, steering command, fallback request | Identifies hazardous output behavior |
| Interfaces | Upstream/downstream ECUs, communication buses, timing assumptions | Supports interface safety requirements |
| Operating modes | normal, degraded, fallback, maintenance, update | Supports safe-state definition |
| Assumptions | driver availability, ODD, other systems, diagnostics, timing | Prevents hidden safety assumptions |

## HARA Evaluation Table

Do not jump directly to ASIL. For each hazardous event, provide S/E/C reasoning.

| Field | Required content |
| --- | --- |
| Malfunctioning behavior | What incorrect, missing, delayed, or unintended behavior occurs |
| Operational situation | Road type, traffic, weather, speed, object/pedestrian speed, driver fallback |
| Hazardous event | Combination of malfunction and operational situation |
| Possible harm | Who can be harmed and how |
| Severity | S0-S3 with injury rationale and speed assumptions |
| Exposure | E0-E4 with operational frequency rationale |
| Controllability | C0-C3 with driver/other-road-user avoidance rationale |
| ASIL/QM | Derived only after S/E/C reasoning |
| Safety goal | Vehicle-level goal to prevent or mitigate the hazardous event |

## Functional Safety Concept

| Condition or fault | Required safe behavior | Example safety requirement |
| --- | --- | --- |
| Sensor unavailable | Do not rely on missing data; degrade function | The system shall detect unavailable sensor input and transition to degraded mode within the fault tolerant time interval |
| Implausible perception output | Cross-check with independent source or invalidate output | The system shall reject object outputs inconsistent with radar/camera/map plausibility checks |
| Stale timestamp | Invalidate old data and prevent late actuation | The system shall detect stale perception data before it can trigger unsafe planning |
| ECU overload | Maintain safety-critical timing or fallback | The system shall monitor execution timing and trigger safe fallback if deadlines are missed |
| Communication fault | Detect corrupted or missing messages | The system shall use counters/CRC/timeouts for safety-relevant messages |

## Technical Safety Concept

| Mechanism | Failure mode addressed | Evidence expected |
| --- | --- | --- |
| Power and voltage monitoring | sensor/ECU undervoltage or reset | diagnostic test and fault-injection result |
| Temperature monitoring | sensor degradation or shutdown | thermal test and diagnostic threshold rationale |
| Communication CRC/counter | corrupted, repeated, or missing data | bus fault-injection and timeout test |
| Timestamp monitoring | stale or delayed perception data | latency budget and stale-data test |
| Plausibility checks | impossible object position/velocity/class | interface test and scenario test |
| Sensor-fusion comparison | single-sensor false negative or false positive | fusion disagreement test |
| Watchdog | software hang or timing overrun | watchdog fault-injection result |
| Degraded mode | loss of full performance | safe-state transition and HMI validation |

## Hardware Evaluation

For hardware elements, evaluate:

- safety requirements allocated to hardware;
- random hardware failure modes;
- diagnostic coverage;
- SPFM, LFM, and PMHF where applicable;
- FMEDA assumptions and failure-rate source quality;
- dependent failures and common-cause failures;
- environmental limits such as temperature, vibration, supply voltage, and aging;
- production test coverage and field diagnostic coverage.

## Software Evaluation

For software elements, evaluate:

- software safety requirements and ASIL allocation;
- software architecture and freedom from interference;
- timing, memory, communication, and resource constraints;
- defensive handling of invalid inputs;
- unit tests, integration tests, static analysis, reviews;
- fault injection and robustness tests;
- configuration management and change control;
- regression testing for updates.

## Verification and Validation

| Verification target | Example test | Expected safe behavior | Evidence |
| --- | --- | --- | --- |
| Sensor fault | unplugged sensor, corrupted point cloud, frozen output | fault detected, unsafe output invalidated, degraded mode entered | fault-injection report |
| Timing fault | stale timestamp, delayed message, ECU overload | old data rejected, fallback or warning triggered | timing analysis and test |
| Interface fault | CRC error, message counter error, missing message | communication fault detected within allowed time | bus fault-injection report |
| System integration | conflicting camera/radar/LiDAR outputs | planner behaves conservatively or requests fallback | integration test report |
| Vehicle validation | AEB/fallback behavior in representative scenario | safety goal is met at vehicle level | vehicle test report |

## Production and Operation

Safety shall be maintained beyond development by controlling:

- end-of-line tests;
- calibration and alignment;
- production parameter locking;
- software and hardware configuration traceability;
- service and repair procedures;
- diagnostic trouble codes;
- field monitoring;
- incident and near-miss investigation;
- update and rollback processes;
- safety impact analysis for changes.

## Example Mini Evaluation: LiDAR Perception Item

Item: LiDAR perception subsystem provides object position, distance, velocity, classification, and confidence to fusion/planning for AEB and automated-driving functions.

Example malfunction: LiDAR object output is frozen or timestamped incorrectly, so a pedestrian position is stale.

Operational situation: Urban road at 50 km/h, pedestrian crossing at approximately 1.5 m/s, partial occlusion by parked vehicle, wet road.

HARA reasoning:

- Severity: likely S3 because a pedestrian collision at 50 km/h can cause life-threatening or fatal injury.
- Exposure: likely E3/E4 depending on the target ODD. If urban crossings are frequent in the ODD, E4 is plausible; if limited to rare conditions, E3 may be more appropriate.
- Controllability: likely C3 if the driver is not expected to supervise continuously or if available reaction time is short; C2 may be argued only if driver fallback is credible and timely.
- ASIL: likely high, potentially ASIL D for S3/E4/C3, subject to final HARA table.

Candidate safety goal: Prevent missing or stale LiDAR object information from causing late or absent braking for vulnerable road users.

Functional safety concept: Detect stale/frozen/implausible LiDAR output, invalidate unsafe perception data, cross-check with other sensors, reduce speed or enter degraded mode, warn the driver, and trigger fallback when safe perception cannot be maintained.

Technical safety concept: timestamp monitoring, watchdog, communication CRC/counter, point-cloud plausibility checks, calibration monitoring, sensor-fusion disagreement handling, diagnostic coverage for emitter/receiver/power/temperature faults, and validated safe-state transition.

Safety case expectation: link HARA, safety goals, requirements, architecture, hardware/software evidence, safety analyses, verification, validation, production controls, and residual risk into one traceable argument.

