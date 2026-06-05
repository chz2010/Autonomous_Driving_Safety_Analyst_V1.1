# SOTIF Evaluation Scheme for Autonomous Driving Functions

This document is an original project-specific evaluation scheme based on ISO 21448 / SOTIF concepts. It is not a copy of ISO text. Use it as a structured checklist for evaluating whether an autonomous-driving or ADAS function can create unreasonable risk even when the E/E system is not malfunctioning.

## Purpose

SOTIF evaluation asks whether the intended function can behave unsafely because of functional insufficiencies, performance limitations, foreseeable misuse, or triggering conditions. It complements ISO 26262, which focuses on hazards caused by E/E malfunctioning behavior.

## Evaluation Flow

| Step | Evaluation question | Required evidence | Engineering output |
| --- | --- | --- | --- |
| 1. Define intended functionality | What is the function supposed to do, and what is outside its responsibility? | Item definition, feature description, user manual assumptions, interfaces | Intended functionality statement and assumptions |
| 2. Define ODD | Where and when is the function allowed to operate? | Road types, speed range, weather, lighting, traffic, geography, infrastructure, driver fallback | ODD table with allowed, degraded, and prohibited conditions |
| 3. Identify performance limitations | Where can the function work as designed but still perform insufficiently? | Sensor range, perception confidence, model limits, map limits, fusion limits, latency, planning assumptions | Limitation list with safety impact |
| 4. Identify triggering conditions | What real-world conditions can expose the limitation? | Scenario catalogue, simulation, track tests, field data, incident data | Triggering-condition table |
| 5. Identify hazardous events | What unsafe vehicle behavior can occur when the triggering condition happens? | Hazard analysis, scenario analysis, vehicle behavior analysis | Hazardous-event list |
| 6. Classify scenario status | Is the scenario known safe, known unsafe, unknown safe, or unknown unsafe? | Test coverage, scenario discovery, field monitoring, simulation coverage | Scenario status and residual uncertainty |
| 7. Evaluate foreseeable misuse | How might the user reasonably misuse or overtrust the system? | HMI review, driver monitoring, misuse analysis, operational feedback | Misuse scenarios and mitigations |
| 8. Define risk reduction measures | How is unreasonable risk reduced? | Design changes, ODD restrictions, fallback logic, warnings, degraded mode, validation evidence | Risk-reduction plan |
| 9. Verify and validate | Was the limitation sufficiently tested across the ODD? | Scenario tests, simulation, proving ground, road tests, regression tests, safety KPIs | V&V evidence and acceptance criteria |
| 10. Monitor in operation | How are unknown unsafe scenarios discovered after release? | Field monitoring, incident review, near-miss reports, OTA update controls | Monitoring and feedback process |

## Triggering Condition Evaluation Table

Use this table when evaluating perception, prediction, planning, and control limitations.

| Triggering condition | Why it matters | Possible unsafe effect | Detection or monitoring | Mitigation | Validation evidence |
| --- | --- | --- | --- | --- | --- |
| Heavy rain, fog, spray | Reduces sensor quality and object visibility | Late or missed detection | Visibility estimate, sensor confidence, point-cloud quality, camera contrast | Reduce speed, increase following distance, restrict ODD, fallback | Rain/fog scenario tests and confidence calibration |
| Low light or glare | Reduces camera and perception performance | Misclassification or missed road user | Image quality metrics, perception confidence, exposure checks | Degrade function, require additional sensor confirmation | Night/glare validation set and road tests |
| Occlusion by parked vehicle or traffic | Reduces available sensing time | Pedestrian or cyclist detected too late | Occlusion reasoning, prediction uncertainty, map/context cues | Slow down, conservative planning near crossings | Urban crossing scenarios with occluded VRUs |
| Low-reflectivity or unusual object | Weak sensor return or unfamiliar appearance | Missed object or wrong class | Uncertainty score, sensor-fusion consistency | Treat unknown objects conservatively | Rare object scenario tests |
| Construction zone or temporary layout | ODD may differ from map/training data | Wrong path or unsafe maneuver | Map mismatch, lane confidence, object density | Reduce automation level, driver takeover, minimum-risk maneuver | Construction-zone scenario catalogue |
| Driver overtrust or misuse | User expects more capability than designed | Late intervention or no fallback | Driver monitoring, HMI state, hands/eyes detection | Clear HMI, escalation, disengagement, safe stop | Misuse validation and HMI tests |

## SOTIF Scenario Status

| Scenario status | Meaning | Required action |
| --- | --- | --- |
| Known safe | Tested and acceptable within defined assumptions | Maintain evidence and regression coverage |
| Known unsafe | Unsafe behavior has been identified | Mitigate, restrict ODD, redesign, or block release |
| Unknown safe | Not fully explored but no unsafe behavior known | Expand scenario coverage and justify residual uncertainty |
| Unknown unsafe | Unsafe behavior exists but is not yet discovered | Use scenario mining, field monitoring, simulation, and conservative release gates |

## SOTIF Evaluation for Perception Functions

For perception-heavy functions such as LiDAR/camera/radar object detection, evaluate:

- sensor performance envelope: range, resolution, field of view, latency, calibration, contamination, weather sensitivity;
- object coverage: pedestrians, cyclists, motorcycles, unusual vehicles, animals, debris, strollers, construction objects;
- scenario coverage: intersections, crossings, cut-ins, occlusion, night, rain, fog, road spray, construction zones, dense traffic;
- output quality: object existence, class, position, distance, velocity, confidence, uncertainty;
- downstream effect: AEB trigger timing, planning conservatism, fallback request, HMI warning, minimum-risk maneuver.

## SOTIF Evaluation for Planning and Decision Functions

For planning, prediction, reinforcement learning, or Markov-decision-process-based decision logic, evaluate:

- whether the state representation captures safety-relevant context;
- whether the reward/cost function penalizes unsafe behavior enough;
- whether rare but severe scenarios are represented;
- whether uncertainty in prediction changes the decision policy;
- whether the planner has conservative fallback behavior when confidence is low;
- whether simulation scenarios include edge cases, not only nominal traffic.

## SOTIF Risk Reduction Measures

| Risk reduction measure | Example | Evidence |
| --- | --- | --- |
| ODD restriction | Disable automated driving in heavy fog or unvalidated road types | ODD decision logic, road tests, user manual |
| Degraded mode | Reduce speed and increase headway when perception confidence drops | Scenario tests, timing analysis |
| Fallback or minimum-risk maneuver | Transition to driver takeover or safe stop | HMI tests, fallback timing, vehicle validation |
| Sensor-fusion confirmation | Cross-check LiDAR with camera/radar/map | Fusion consistency tests |
| Conservative planning | Treat uncertain object as potentially safety relevant | Simulation, track tests, false-negative analysis |
| Scenario expansion | Add rare/edge scenarios to validation set | Updated scenario catalogue and regression tests |
| Field monitoring | Capture near misses and unknown unsafe scenarios | Incident process, telemetry, update workflow |

## Acceptance Criteria

A SOTIF argument is stronger when it can show:

- the intended function and ODD are explicit;
- known performance limitations have been identified;
- triggering conditions have been systematically searched;
- known unsafe scenarios have risk-reduction measures;
- validation covers both nominal and edge-case scenarios;
- residual risk is justified and monitored;
- user misuse and overtrust are addressed;
- release is blocked when safety KPIs or scenario coverage are insufficient.

## Example Mini Evaluation: LiDAR Pedestrian Detection

Scenario: The vehicle approaches an urban crossing at 50 km/h at night in heavy rain. A pedestrian in dark clothing walks from behind a parked vehicle at approximately 1.5 m/s. LiDAR point-cloud quality is degraded by rain and road spray, while camera contrast is low.

SOTIF interpretation: The LiDAR and perception software might not be malfunctioning. The unsafe behavior can still arise because the intended functionality has insufficient performance under the triggering conditions of rain, low light, dark clothing, and occlusion.

Possible unsafe effect: The pedestrian is detected too late, AEB is triggered late, or the planner does not reduce speed early enough. The available sensing time and stopping distance become insufficient.

Risk reduction: The system should detect degraded perception confidence, reduce speed near crossings, increase planning conservatism, use camera/radar fusion where available, request fallback or disable the function when the ODD is exceeded, and validate the scenario in simulation, proving-ground tests, and road tests.

Evidence needed: Scenario catalogue entry, confidence/uncertainty calibration, validation results under rain/night/occlusion, AEB timing acceptance criteria, HMI/fallback timing, and field monitoring for near misses.

