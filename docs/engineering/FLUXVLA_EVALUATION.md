# FluxVLA engineering evaluation

Classification: INTERNAL engineering reference. Assessed 26 October 2026.
Decision: defer runtime adoption; retain the complete CPU deterministic inspection.
No FluxVLA environment, weights or datasets were installed, and no model inference,
benchmark or physical robot was run. A configured model is not advertised in the UI.

## Evidence and fit

LimX's [product presentation](https://www.limxdynamics.com/en) and
[COSA](https://www.limxdynamics.com/en/news/BK000055) motivate task-oriented supervision and
separation between cognition and local execution. Onesa reuses these ideas, its own
identity and original SVG artwork; it copies no robot footage, proprietary code or
hardware claims. Its deterministic planner is not COSA or learned AI.

The [official FluxVLA product page](https://www.limxdynamics.com/en/products/fluxvla)
links the [official repository](https://github.com/FluxVLA/FluxVLA) and
[documentation](https://fluxvla.limxdynamics.com/). Source reviewed at
`5b8a500e739e46054509d94831872cd9a7eccd32`. Examples and dependencies change; a
later evaluation must record a new complete source/config/artifact inventory.

| Boundary | Assessment |
| --- | --- |
| Code license | The pinned repository LICENSE is Apache 2.0. Preserve notices and audit dependencies separately; this does not license all weights, training data or third-party simulators. |
| Candidate weights | The [SmolVLA base model card](https://huggingface.co/lerobot/smolvla_base) declares Apache 2.0. The [SmolVLM2-500M backbone card](https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct) independently declares Apache 2.0. Pin exact weight/tokenizer revisions, hashes and accompanying notices before download/adoption. Other policies, including GR00T and Pi0.5, need their own model-license review. |
| Dataset | The officially linked [FluxVLAData dataset card](https://huggingface.co/datasets/limxdynamics/FluxVLAData) declares Apache 2.0. It aggregates different simulation and real-robot subsets. Check selected subset origin, notices and rights separately; no blanket approval of upstream videos, collected factory data or all LIBERO/RoboCasa content is inferred. No Onesa operator/customer data is a training dataset. |
| Models/configuration | The pinned `configs/smolvla/smolvla_libero_spatial_finetune.py` selects SmolVLA, the SmolVLM backbone, 32-dimensional padded state/actions, seven original action dimensions, a 50-action chunk and ten flow steps. These are benchmark conventions, not the P-101 simulator's one-joint controller contract. The repository also includes other model families; they are not all qualified by this review. |
| Compute and OS | The current installer uses Python 3.10, CUDA PyTorch profiles cu124/cu128 and architecture-specific FlashAttention wheels. The remote serving guide explicitly requires GPU/CUDA server infrastructure. Current Onesa targets are macOS ARM64/M3 and the existing ARM64 Oracle CPU host; no qualified CUDA endpoint is available. The LeRobot SmolVLA card has a CPU example in a different runtime; it does not prove FluxVLA's full simulator/runner path on macOS. |
| ROS and robot adapters | Real runners require a system ROS installation; upstream installation instructions show Noetic. UR, Aloha and Franka examples are device-specific. Onesa's ROS 2 Jazzy message scaffold has no controller bridge, calibrated kinematics, collision model or certified stop behavior. It cannot load these real-robot configs as a compatible substitute. |
| Remote inference | Pinned `docs/remote_inference_serving.md` uses ZMQ request/reply with msgpack or protobuf, optional image compression and SSH tunnelling. The sample UR config has a 30-second timeout, ten-action chunk and 30-Hz publish rate. Those values do not satisfy Onesa's local authority/watchdog contract. Never route returned action chunks directly to an executor. |
| Dependencies | Simulation requirements mix pinned source revisions with unconstrained packages. Real requirements include ROS Python utilities, ZMQ and protobuf; serving docs request a newer protobuf floor than the real dependency file's upper bound. Keep a separate environment and resolve a hash-locked compatible set, security scan, license inventory and maintainer update process. Do not merge this stack into Robot's FastAPI requirements. |

## Reproducible isolated evaluation path — not executed

1. Provision no new resources. Obtain an already authorized, isolated CUDA evaluation
   target or qualify a supported CPU/MPS port first. Record OS/architecture, GPU,
   driver/toolkit, available RAM/VRAM/disk and software versions. No production
   credentials, factory network, ROS controller, device mounts or cloud metadata.
2. Check out the exact source above into a disposable directory outside this repo.
   Review `scripts/install_env.sh`, `requirements-sim.txt`, `requirements-real.txt`,
   the selected model config and the benchmark runner. Create a separate Python3.10
   environment. For a LIBERO-only evaluation, use the upstream sim-only installer
   with `--skip-robocasa --skip-robocasa-assets`; review automatic downloads first.
   Resolve and retain a hash-locked dependency/wheel inventory. Never run an
   unaudited installer with owner release credentials.
3. Pin the selected SmolVLA checkpoint, backbone/tokenizer and a rights-reviewed
   LIBERO spatial subset to exact revisions/hashes. Use safetensors where supported;
   do not deserialize untrusted pickle checkpoints. Put artifacts in restricted
   evaluation storage, not Git. Record license/notice provenance for every artifact.
4. Copy the pinned spatial configuration into the disposable evaluation directory.
   Point only to the approved local artifacts and denormalization statistics.
   Use the upstream `scripts/inference.py --config <reviewed-simulation-config>
   --ckpt-path <approved-checkpoint>` interface after verifying its runner is the
   LIBERO simulator, not UR/Aloha/Franka. Fix seeds and episode list. Capture exact
   command/config hashes, task success, invalid/nonfinite outputs, latency p50/p95,
   cold start, peak RAM/VRAM, timeouts and reproducibility over at least three runs.
   No training, asset download or real-robot entrypoint is implicit in this recipe.
5. An optional remote experiment may bind the reviewed serving entrypoint to
   `127.0.0.1` and use an authenticated SSH tunnel. Supply only synthetic frames and
   state. One in-flight request, at most ten requests per explicit evaluation run,
   a one-second proposal deadline and a 60-second process budget are initial Onesa
   evaluation ceilings, not measured feasibility. Reject late, oversized, nonfinite,
   wrongly shaped, version-mismatched or unsupported results; never retry an
   uncertain command. Measure memory first and stop rather than expanding resources.
6. A future narrow adapter may translate a validated model proposal into supported
   versioned skills. It must create a new bounded plan requiring existing exact-plan
   operator approval and independent gating. Camera perception accuracy, collision
   safety, physical control and any production deployment need separate acceptance.

Expected resource impact is substantial relative to the current static SVG/CPU
service: CUDA libraries, simulator assets, weights, tokenizers and several GB of
working memory/storage depending on the selected artifacts. No minimum VRAM,
throughput, cost saving or physical success rate has been measured by Onesa. Obtain
actual artifact sizes and enforce target-specific caps before evaluation; a
backbone's advertised memory is not a whole-policy deployment requirement.

The next engineering milestone is a reproducible isolated model/benchmark result
and a reviewed bounded proposal adapter. Until then `model_inference` remains
`not_configured`, and deterministic inspection remains fully usable without it.
