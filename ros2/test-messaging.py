"""Loopback synthetic ROS interface test. No actuator or external DDS transport."""

import time

import rclpy
from onesa_sim_interfaces.msg import SimulationTelemetry

rclpy.init()
node = rclpy.create_node("onesa_simulation_contract_check")
observed = []
subscription = node.create_subscription(
    SimulationTelemetry, "/onesa/test/telemetry", observed.append, 10
)
publisher = node.create_publisher(SimulationTelemetry, "/onesa/test/telemetry", 10)
message = SimulationTelemetry(
    mode="simulation", physical_actuation=False, stopped=True, position_radians=0.0
)
try:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not observed:
        publisher.publish(message)
        rclpy.spin_once(node, timeout_sec=0.1)
    assert observed, "No local discovery/message receipt"
    assert observed[0].mode == "simulation" and not observed[0].physical_actuation
    assert observed[0].stopped and observed[0].position_radians == 0.0
finally:
    node.destroy_node()
    rclpy.shutdown()
