"""
SPH Collision Dynamics Dispatcher
Manages spatial hashing, density/pressure calculations, and collision forces
Integrates with N-Body GPU compute dispatcher for unified physics loop
"""

import pyopencl as cl
import numpy as np
import time
from typing import Dict, List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SPHDispatcher")


class SpatialHashGrid:
    """
    Spatial hash grid for efficient O(n) neighbor search.
    Maps 3D positions to grid cells for collision detection.
    """
    
    def __init__(self, cell_size: float = 10.0):
        """
        Initialize spatial hash grid.
        
        Args:
            cell_size: Size of each grid cell in world units
        """
        self.cell_size = np.float32(cell_size)
        self.grid_size = 2048  # Max cells (power of 2 for hashing)
        self.particles_per_cell = 64  # Max particles per cell
    
    def compute_hash(self, pos: np.ndarray) -> np.uint32:
        """Compute grid hash for 3D position."""
        x, y, z = pos
        grid_x = int(np.floor(x / self.cell_size))
        grid_y = int(np.floor(y / self.cell_size))
        grid_z = int(np.floor(z / self.cell_size))
        
        hash_val = (grid_x * 73856093) ^ (grid_y * 19349663) ^ (grid_z * 83492791)
        return np.uint32(hash_val & 0x7FFFFFFF)  # Keep positive
    
    def build_grid(self, positions: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build spatial hash grid from particle positions.
        
        Args:
            positions: (N, 3) array of particle positions
        
        Returns:
            (grid_indices, grid_counts) - cell start indices and particle counts
        """
        num_particles = len(positions)
        
        # Initialize grid
        grid_indices = np.zeros(self.grid_size, dtype=np.uint32)
        grid_counts = np.zeros(self.grid_size, dtype=np.uint32)
        
        # Count particles per cell
        for i in range(num_particles):
            cell_hash = self.compute_hash(positions[i])
            grid_counts[cell_hash] += 1
        
        # Compute cumulative offsets
        offset = 0
        for i in range(self.grid_size):
            grid_indices[i] = offset
            offset += grid_counts[i]
            grid_counts[i] = 0  # Reset for second pass
        
        # Recompute counts during placement
        for i in range(num_particles):
            cell_hash = self.compute_hash(positions[i])
            grid_counts[cell_hash] += 1
        
        return grid_indices, grid_counts


class SPHCollisionDispatcher:
    """
    GPU dispatcher for SPH collision dynamics.
    Manages kernels for density, pressure, forces, and fragmentation.
    """
    
    def __init__(self, gpu_context: cl.Context, gpu_queue: cl.CommandQueue, verbose: bool = True):
        """
        Initialize SPH dispatcher.
        
        Args:
            gpu_context: OpenCL context from compute dispatcher
            gpu_queue: OpenCL command queue
            verbose: Enable logging
        """
        self.context = gpu_context
        self.queue = gpu_queue
        self.verbose = verbose
        self.program = None
        self.kernels = {}
        self.spatial_grid = SpatialHashGrid(cell_size=20.0)
        
        # Physics parameters
        self.rest_density = np.float32(1000.0)  # kg/m³
        self.gas_constant = np.float32(2000.0)
        self.gamma = np.float32(7.0)  # Stiffness
        self.viscosity = np.float32(0.02)
        self.drag_coefficient = np.float32(0.47)
        self.atmosphere_density = np.float32(1.225)
        self.ablation_temperature = np.float32(1500.0)
        self.fragmentation_threshold = np.float32(1e6)  # Joules
        
        self._log("SPH Collision Dispatcher initialized")
    
    def _log(self, msg: str):
        """Conditional logging."""
        if self.verbose:
            logger.info(msg)
    
    def compile_sph_kernels(self, kernel_path: str):
        """
        Compile SPH collision kernels from source file.
        
        Args:
            kernel_path: Path to sph_collision.cl
        """
        try:
            with open(kernel_path, 'r') as f:
                kernel_source = f.read()
            
            self.program = cl.Program(self.context, kernel_source)
            self.program.build(options="-cl-fast-relaxed-math -cl-mad-enable")
            
            # Extract kernel functions
            self.kernels['density'] = self.program.sph_density_calculation
            self.kernels['pressure'] = self.program.sph_pressure_calculation
            self.kernels['collision_forces'] = self.program.sph_collision_forces
            self.kernels['fragmentation'] = self.program.sph_fragmentation_check
            self.kernels['atmospheric_drag'] = self.program.sph_atmospheric_drag
            self.kernels['integrate'] = self.program.sph_integrate_step
            
            self._log(f"✓ SPH kernels compiled successfully ({len(self.kernels)} kernels)")
            
        except cl.cffi_cl.LogicError as e:
            logger.error(f"SPH kernel compilation error: {e}")
            raise
    
    def compute_sph_step(self,
                        particles: np.ndarray,
                        dt: float = 0.016,
                        workgroup_size: int = 128) -> Dict[str, float]:
        """
        Execute single SPH collision dynamics step.
        
        Args:
            particles: SPHParticle array (structured numpy array)
            dt: Time step
            workgroup_size: OpenCL workgroup size
        
        Returns:
            Timing dictionary with kernel execution times
        """
        if self.program is None:
            raise RuntimeError("SPH kernels not compiled. Call compile_sph_kernels() first.")
        
        num_particles = len(particles)
        timings = {}
        
        # Extract positions for spatial hashing
        positions = np.array([particles['pos'][i] for i in range(num_particles)])
        
        # Build spatial hash grid (CPU-side for now, can be GPU-side later)
        grid_indices, grid_counts = self.spatial_grid.build_grid(positions)
        
        # Create GPU buffers
        particles_buf = cl.Buffer(self.context, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=particles)
        grid_indices_buf = cl.Buffer(self.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=grid_indices)
        grid_counts_buf = cl.Buffer(self.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=grid_counts)
        
        forces = np.zeros((num_particles, 3), dtype=np.float32)
        forces_buf = cl.Buffer(self.context, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=forces)
        
        fragment_markers = np.zeros(num_particles, dtype=np.uint32)
        fragment_markers_buf = cl.Buffer(self.context, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=fragment_markers)
        
        ejecta_velocities = np.zeros((num_particles, 3), dtype=np.float32)
        ejecta_velocities_buf = cl.Buffer(self.context, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=ejecta_velocities)
        
        mass_loss = np.zeros(num_particles, dtype=np.float32)
        mass_loss_buf = cl.Buffer(self.context, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=mass_loss)
        
        # Align global size to workgroup size
        global_size = ((num_particles + workgroup_size - 1) // workgroup_size) * workgroup_size
        
        # 1. Density Calculation
        wall_start = time.perf_counter()
        event = self.kernels['density'](
            self.queue, (global_size,), (workgroup_size,),
            particles_buf, grid_indices_buf, grid_counts_buf,
            np.uint32(num_particles),
            self.spatial_grid.cell_size,
            np.float32(1.0)  # mass_scale
        )
        event.wait()
        timings['density'] = (event.profile.end - event.profile.start) / 1e6
        
        # 2. Pressure Calculation
        wall_start = time.perf_counter()
        event = self.kernels['pressure'](
            self.queue, (global_size,), (workgroup_size,),
            particles_buf, np.uint32(num_particles),
            self.rest_density, self.gas_constant, self.gamma
        )
        event.wait()
        timings['pressure'] = (event.profile.end - event.profile.start) / 1e6
        
        # 3. Collision Forces
        wall_start = time.perf_counter()
        event = self.kernels['collision_forces'](
            self.queue, (global_size,), (workgroup_size,),
            particles_buf, forces_buf, grid_indices_buf, grid_counts_buf,
            np.uint32(num_particles),
            self.spatial_grid.cell_size,
            self.viscosity,
            np.float32(dt)
        )
        event.wait()
        timings['collision_forces'] = (event.profile.end - event.profile.start) / 1e6
        
        # 4. Fragmentation Check
        wall_start = time.perf_counter()
        event = self.kernels['fragmentation'](
            self.queue, (global_size,), (workgroup_size,),
            particles_buf, fragment_markers_buf, ejecta_velocities_buf,
            np.uint32(num_particles),
            self.fragmentation_threshold,
            np.float32(1e8)  # material_strength
        )
        event.wait()
        timings['fragmentation'] = (event.profile.end - event.profile.start) / 1e6
        
        # 5. Atmospheric Drag
        wall_start = time.perf_counter()
        event = self.kernels['atmospheric_drag'](
            self.queue, (global_size,), (workgroup_size,),
            particles_buf, mass_loss_buf,
            np.uint32(num_particles),
            self.atmosphere_density,
            self.drag_coefficient,
            self.ablation_temperature,
            np.float32(dt)
        )
        event.wait()
        timings['atmospheric_drag'] = (event.profile.end - event.profile.start) / 1e6
        
        # 6. Integration Step
        wall_start = time.perf_counter()
        event = self.kernels['integrate'](
            self.queue, (global_size,), (workgroup_size,),
            particles_buf, forces_buf,
            np.float32(dt),
            np.uint32(num_particles)
        )
        event.wait()
        timings['integrate'] = (event.profile.end - event.profile.start) / 1e6
        
        # Read back results
        cl.enqueue_copy(self.queue, particles, particles_buf)
        cl.enqueue_copy(self.queue, fragment_markers, fragment_markers_buf)
        self.queue.finish()
        
        # Cleanup
        particles_buf.release()
        grid_indices_buf.release()
        grid_counts_buf.release()
        forces_buf.release()
        fragment_markers_buf.release()
        ejecta_velocities_buf.release()
        mass_loss_buf.release()
        
        timings['total_gpu_ms'] = sum(timings.values())
        timings['num_fragmented'] = int(np.sum(fragment_markers))
        
        return timings, particles, fragment_markers


class SPHIntegration:
    """
    Integration layer combining N-Body and SPH physics.
    """
    
    def __init__(self, nbody_dispatcher, sph_dispatcher):
        """
        Initialize combined physics engine.
        
        Args:
            nbody_dispatcher: GPUComputeDispatcher for N-Body
            sph_dispatcher: SPHCollisionDispatcher for collisions
        """
        self.nbody = nbody_dispatcher
        self.sph = sph_dispatcher
    
    def unified_physics_step(self,
                           bodies: np.ndarray,
                           particles: np.ndarray,
                           dt: float = 0.016) -> Dict:
        """
        Execute unified N-Body + SPH step.
        
        Returns:
            Combined timing information
        """
        results = {
            "nbody_timings": None,
            "sph_timings": None,
            "total_time_ms": 0.0
        }
        
        step_start = time.perf_counter()
        
        # N-Body gravitational computation
        results["nbody_timings"] = self.nbody.profile_nbody_step(len(bodies), dt)
        
        # SPH collision dynamics
        results["sph_timings"], particles, fragments = self.sph.compute_sph_step(particles, dt)
        
        results["total_time_ms"] = (time.perf_counter() - step_start) * 1000
        results["fragmented_particles"] = fragments
        
        return results


if __name__ == "__main__":
    logger.info("SPH Collision Dispatcher module ready")
