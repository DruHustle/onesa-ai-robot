cmake_minimum_required(VERSION 3.8)
project(onesa_sim_interfaces)
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/SimulationTelemetry.msg" "msg/SimulationProposal.msg"
  DEPENDENCIES builtin_interfaces)
ament_export_dependencies(rosidl_default_runtime)
ament_package()
