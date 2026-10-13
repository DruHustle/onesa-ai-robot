#!/bin/sh
set -e
. /opt/ros/jazzy/setup.sh
mkdir -p /tmp/robot-ros/src
cp -R /source/onesa_sim_interfaces /tmp/robot-ros/src/
cd /tmp/robot-ros
# The official ros-base image contains colcon and ROS interface build tools.
colcon build --packages-select onesa_sim_interfaces
. install/setup.sh
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=117
ros2 interface show onesa_sim_interfaces/msg/SimulationTelemetry
ros2 interface show onesa_sim_interfaces/msg/SimulationProposal
python3 /source/test-messaging.py
