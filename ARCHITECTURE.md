# Project Universe - GPU Astrophysics Simulator
## Architecture & Implementation Guide

### Overview
This is a physically accurate astrophysics simulator targeting GPU acceleration via OpenCL on AMD RX 570.

The architecture implements:
- **ECS (Entity Component System)**: Scalable entity management
- **N-Body Gravitational Physics**: GPU-accelerated force calculations
- **SPH (Smoothed Particle Hydrodynamics)**: Realistic collision dynamics
- **Realistic Collision Physics**: Inelastic merging with material conservation

---

## STEP 1: N-Body Compute Shader ✓ COMPLETE

### Implementation
- **File**: `gpu/kernels/nbody.cl`
- **Language**: OpenCL C (portable across GPUs)
- **Optimization**: Workgroup shared memory for VRAM bandwidth reduction
- **Kernels**:
  - `nbody_compute_forces()`: Main gravitational force calculation
  - `integrate_velocity()`: Velocity updates via semi-implicit Euler
  - `integrate_position()`: Position updates
  - `rk4_stage1()`: Runge-Kutta 4th order integration foundation

### Key Features
- Tile-based force computation (128 threads per workgroup)
- Local memory (LDS) caching for 16 KB shared data
- Softening parameter to prevent singularities
- Parallelized over all bodies (one thread per body)

### GPU Dispatch
- **File**: `gpu/compute_dispatcher.py`
- Manages OpenCL context, kernel compilation, buffer management
- Profiling capability for GPU vs CPU overhead isolation
- AMD GPU device auto-detection

---

## STEP 2: Memory Alignment ✓ COMPLETE

### std430 Layout Verification
- **File**: `gpu/buffers/memory_alignment.py`
- **Alignment Rules**:
  - Scalars (float32, int32): 4 bytes
  - vec3 (3 × float32): 12 bytes (NOT 16!)
  - vec4 (4 × float32): 16 bytes
  - Structs: Padded to 16-byte boundaries

### Data Structures (std430 aligned)
**PhysicsBody**: 64 bytes
```
pos[3]     : 12 bytes (vec3)
mass       : 4 bytes (float)
vel[3]     : 12 bytes (vec3)
radius     : 4 bytes (float)
acc[3]     : 12 bytes (vec3)
padding    : 4 bytes (float)
```

**SPHParticle**: 80 bytes (extended for hydrodynamics)

### Alignment Verification Tools
- `verify_alignment()`: Validates struct sizes
- `AMDGPUMemoryAnalyzer`: AMD RX 570 optimization analysis
- Cache line efficiency calculations
- LDS (Local Data Share) utilization metrics

---

## STEP 3: Stress Testing & Profiling ✓ COMPLETE

### Test Suite
- **File**: `tests/stress_test.py`
- **Scale**: 50,000 entities with configurable iterations
- **Profiling Metrics**:
  - GPU compute time (from kernel profiling)
  - CPU dispatch overhead (separate measurement)
  - Wall clock time
  - GFLOPS estimation

### Benchmark Methodology
1. Realistic body distribution (Sun + orbiting bodies)
2. Warm-up run to stabilize GPU frequency
3. Multiple iterations with statistical analysis
4. Detailed timing breakdown per computation stage

### Running Stress Tests
```bash
python tests/stress_test.py
# Outputs: benchmark_results.json with detailed metrics
```

---

## STEP 4: API Fallback Protocol ⏳ READY

If PyOpenCL compilation fails on your system:

### Option A: PyOpenCL with pre-built wheels
```bash
pip install pyopencl --only-binary :all:
```

### Option B: Taichi Framework (GPU-agnostic)
```bash
pip install taichi
# Automatic GPU detection and kernel compilation
```

### Option C: CUDA (NVIDIA only)
```bash
pip install cupy  # Similar API to NumPy, CUDA-backed
```

### Migration Path
All compute logic is isolated in `gpu/kernels/nbody.cl` and `gpu/compute_dispatcher.py`.
Swapping backends requires:
1. Recompile kernel (OpenCL → Taichi/CUDA syntax)
2. Update dispatcher buffer management
3. Core physics math remains unchanged

---

## STEP 5: SPH Collision Dynamics ⏳ NEXT

### Planned Implementation
- **Spatial Hash Grid**: O(n) neighbor search vs O(n²)
- **SPH Kernel**: Smoothing length-based force calculations
- **Material Fragmentation**: Energy transfer, spalling, ejecta tracking
- **Atmospheric Drag**: Thermal ablation, visual vapor trails

### Related Files (Foundation)
- `data/physics_types.py`: SPHParticle struct
- `gpu/kernels/nbody.cl`: Will extend with SPH kernels
- `simulation.py`: Updated collision handler (already implements merging)

---

## Project Structure
```
project_universe/
├── gpu/
│   ├── kernels/
│   │   └── nbody.cl              # OpenCL compute kernels
│   ├── buffers/
│   │   └── memory_alignment.py    # std430 verification
│   ├── compute_dispatcher.py      # GPU context & dispatch
│   └── __init__.py
├── data/
│   ├── physics_types.py           # std430 struct definitions
│   └── __init__.py
├── physics/
│   └── __init__.py                # Physics modules (future)
├── tests/
│   ├── stress_test.py             # 50K entity benchmark
│   └── __init__.py
├── body.py                        # Legacy entity definition
├── simulation.py                  # Main physics loop
├── main.py                        # Pygame UI
├── requirements.txt               # Dependencies
├── setup.sh                       # Installation script
└── README.md                      # This file
```

---

## Hardware Requirements
- **GPU**: AMD RX 570 or similar (OpenCL 1.2+)
- **RAM**: 8+ GB system RAM
- **VRAM**: 2 GB minimum (500K entities fit in 8GB)
- **CPU**: Modern multi-core processor

### AMD RX 570 Specifications
- Compute Units: 32
- Stream Processors: 2048
- Memory Interface: 256-bit
- Memory Bandwidth: 256 GB/s
- VRAM: 4-8 GB GDDR5

---

## Performance Expectations

### Theoretical Peak
- AMD RX 570: ~5 TFLOPS single-precision
- Typical N-Body kernel: 20 FLOPs per pair interaction

### Realistic Performance (50K bodies)
- GPU Time: ~15-25 ms per iteration
- CPU Dispatch: ~1-2 ms overhead
- FPS at 60 Hz target: ~40-50 bodies per frame (limited by rendering, not compute)

---

## Next Steps

After STEP 5 completion:

1. **MODULE 1**: Planetary oblateness (J2 perturbations), Hill Sphere, Roche Limit, Tidal Locking, Lagrange Points
2. **MODULE 2**: SPH collisions, material fragmentation, debris tracking
3. **MODULE 3**: Thermodynamics, Quadtree surface mapping, greenhouse effect
4. **MODULE 4**: Habitable zone, panspermia, stellar collapse, gravitational lensing
5. **MODULE 5**: UI tools - trajectory prediction, laser emitter, magnifier

---

## References & Tools

### GPU Compute
- [OpenCL 1.2 Specification](https://www.khronos.org/opencl/)
- [PyOpenCL Documentation](https://documen.tician.de/pyopencl/)
- [AMD GPU Optimization Guide](https://gpuopen.com/)

### Physics
- N-Body Algorithms: Verlet, RK4 integration
- SPH Methods: Standard kernel functions, density estimation
- Collision Detection: Spatial hashing, AABB trees

### Tools
- AMD GPU Profiler: ROCm Profiler
- OpenCL Debugger: Debugger support via ROCm
- Performance Analysis: PyOpenCL profiling events

---

## Contact & Support
For issues or optimizations specific to AMD RX 570, refer to:
- ROCm documentation
- OpenCL best practices guide
- GPU memory bandwidth analysis tools

---

**Status**: STEPS 1-3 Complete | STEP 4 Fallback Ready | STEP 5 Queued ✓
