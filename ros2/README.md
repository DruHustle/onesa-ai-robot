# ROS 2 simulation contract boundary

These message definitions prepare an interface package; no ROS node or actuator
transport is implemented or claimed. The intended qualification target is ROS 2
Jazzy on an approved Linux host. Build with `colcon build --packages-select
onesa_sim_interfaces`, source the workspace, and use `ros2 interface show
onesa_sim_interfaces/msg/SimulationTelemetry` before an integration is accepted.
The manifest's contact/licensing entries need owner approval before distribution.

`SimulationProposal` is untrusted input. A future authenticated adapter must convert
it to the versioned HTTP Proposal schema and pass the same independent safety gate,
operator approval, stale-message checks, session and watchdog boundaries. ROS messages
must never authorize action directly. Keep ROS graph access restricted (SROS 2
permissions where implemented); an exposed DDS graph is not a trusted control plane.
No ROS messaging test has passed on a real target in this audit. Physical emergency
stop, device limits and hardware-specific policy validation are separate owner gates.
