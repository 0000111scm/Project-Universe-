"""
GPU Compute Dispatcher using PyOpenCL
Manages N-Body kernel execution on AMD RX 570 GPU
Handles buffer management, kernel compilation, and profiling
"""

import pyopencl as cl
import numpy as np
import time
from pathlib import Path
from typing import List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GPUDispatcher")


class GPUComputeDispatcher:
    """
    High-level interface to GPU compute using OpenCL.
    Optimized for AMD RX 570 with proper workgroup sizing.
    """
    
    WORKGROUP_SIZE = 128
    
    def __init__(self, use_amd_gpu: bool = True, verbose: bool = True):
        """
        Initialize GPU compute context.
        
        Args:
            use_amd_gpu: Prioritize AMD devices
            verbose: Enable detailed logging
        """
        self.verbose = verbose
        self.platforms = cl.get_platforms()
        self.device = self._select_device(use_amd_gpu)
        self.context = cl.Context([self.device])
        self.queue = cl.CommandQueue(
            self.context, 
            properties=cl.command_queue_properties.PROFILING_ENABLE
        )
        
        self.programs = {}
        self.kernels = {}
        self.buffers = {}
        
        self._log(f"GPU Device: {self.device.name}")
        self._log(f"Compute Units: {self.device.max_compute_units}")
        self._log(f"Max Work Group Size: {self.device.max_work_group_size}")
        self._log(f"Global Memory: {self.device.global_mem_size / 1e9:.2f} GB")
    
    def _select_device(self, use_amd: bool = True):
        """Select GPU device (AMD preferred for this project)."""
        devices = []
        for platform in self.platforms:
            devices.extend(platform.get_devices(cl.device_type.GPU))
        
        if not devices:
            raise RuntimeError("No GPU devices found!")
        
        if use_amd:
            amd_devices = [d for d in devices if "AMD" in d.name or "Radeon" in d.name]
            if amd_devices:
                return amd_devices[0]
        
        return devices[0]  # Fallback to first available GPU
    
    def _log(self, msg: str):
        """Conditional logging."""
        if self.verbose:
            logger.info(msg)
    
    def compile_kernel(self, kernel_name: str, kernel_path: str):
        """
        Compile OpenCL kernel from source file.
        
        Args:
            kernel_name: Name for reference
            kernel_path: Path to .cl source file
        """
        try:
            with open(kernel_path, 'r') as f:
                kernel_source = f.read()
            
            program = cl.Program(self.context, kernel_source)
            program.build(options="-cl-fast-relaxed-math -cl-mad-enable")
            self.programs[kernel_name] = program
            self._log(f"✓ Kernel '{kernel_name}' compiled successfully")
            
        except cl.cffi_cl.LogicError as e:
            logger.error(f"Compilation error in {kernel_name}:")
            logger.error(str(e))
            raise
    
    def get_kernel(self, program_name: str, kernel_name: str):
        """Get compiled kernel by name."""
        if program_name not in self.programs:
            raise ValueError(f"Program '{program_name}' not compiled")
        return getattr(self.programs[program_name], kernel_name)
    
    def create_buffer(self, 
                     buffer_name: str,
                     data: np.ndarray,
                     read_only: bool = False) -> cl.Buffer:
        """
        Create GPU buffer (SSBO equivalent) from numpy array.
        
        Args:
            buffer_name: Reference name
            data: numpy array (must be C-contiguous)
            read_only: Buffer access mode
        """
        if not data.flags['C_CONTIGUOUS']:
            data = np.ascontiguousarray(data)
        
        flags = cl.mem_flags.READ_ONLY if read_only else cl.mem_flags.READ_WRITE
        flags |= cl.mem_flags.COPY_HOST_PTR
        
        buffer = cl.Buffer(self.context, flags, hostbuf=data)
        self.buffers[buffer_name] = buffer
        
        size_mb = data.nbytes / 1e6
        self._log(f"✓ Buffer '{buffer_name}' created: {size_mb:.2f} MB")
        
        return buffer
    
    def read_buffer(self, buffer_name: str, shape: Tuple, dtype: np.dtype) -> np.ndarray:
        """Read buffer data from GPU to CPU."""
        if buffer_name not in self.buffers:
            raise ValueError(f"Buffer '{buffer_name}' not found")
        
        output = np.empty(shape, dtype=dtype)
        cl.enqueue_copy(self.queue, output, self.buffers[buffer_name])
        self.queue.finish()
        
        return output
    
    def execute_kernel(self,
                      program_name: str,
                      kernel_name: str,
                      global_size: int,
                      local_size: Optional[int] = None,
                      args: List = None) -> Tuple[float, float]:
        """
        Execute kernel with profiling.
        
        Args:
            program_name: Compiled program name
            kernel_name: Kernel function name
            global_size: Global work size
            local_size: Local work size (workgroup)
            args: Kernel arguments
        
        Returns:
            (gpu_time_ms, wall_time_ms) tuple
        """
        if local_size is None:
            local_size = min(self.WORKGROUP_SIZE, global_size)
        
        kernel = self.get_kernel(program_name, kernel_name)
        
        # Align global size to local size
        global_size = ((global_size + local_size - 1) // local_size) * local_size
        
        wall_start = time.perf_counter()
        
        event = kernel(self.queue, (global_size,), (local_size,), *args)
        event.wait()
        
        wall_time = (time.perf_counter() - wall_start) * 1000  # ms
        gpu_time = (event.profile.end - event.profile.start) / 1e6  # ns -> ms
        
        return gpu_time, wall_time
    
    def profile_nbody_step(self,
                          num_bodies: int,
                          dt: float = 0.016) -> dict:
        """
        Profile a single N-Body simulation step.
        
        Returns:
            Dictionary with timing information
        """
        timings = {
            "force_computation": 0.0,
            "velocity_integration": 0.0,
            "position_integration": 0.0,
            "total_gpu": 0.0,
            "total_wall": 0.0
        }
        
        num_bodies_uint32 = np.uint32(num_bodies)
        dt_f32 = np.float32(dt)
        
        # Force computation
        gpu_t, wall_t = self.execute_kernel(
            "nbody", "nbody_compute_forces",
            global_size=num_bodies,
            args=[
                self.buffers["bodies"],
                self.buffers["accelerations"],
                num_bodies_uint32
            ]
        )
        timings["force_computation"] = gpu_t
        
        # Velocity integration
        gpu_t, wall_t = self.execute_kernel(
            "nbody", "integrate_velocity",
            global_size=num_bodies,
            args=[
                self.buffers["bodies"],
                self.buffers["accelerations"],
                dt_f32,
                num_bodies_uint32
            ]
        )
        timings["velocity_integration"] = gpu_t
        
        # Position integration
        gpu_t, wall_t = self.execute_kernel(
            "nbody", "integrate_position",
            global_size=num_bodies,
            args=[
                self.buffers["bodies"],
                dt_f32,
                num_bodies_uint32
            ]
        )
        timings["position_integration"] = gpu_t
        
        timings["total_gpu"] = sum(timings[k] for k in ["force_computation", "velocity_integration", "position_integration"])
        
        return timings
    
    def release(self):
        """Clean up GPU resources."""
        for buffer in self.buffers.values():
            buffer.release()
        self.buffers.clear()
        self._log("GPU resources released")


def create_test_bodies(num_bodies: int, seed: int = 42) -> np.ndarray:
    """
    Create random test bodies with proper std430 alignment.
    
    Returns:
        numpy array shaped (num_bodies,) with dtype matching PhysicsBody struct
    """
    from data.physics_types import PhysicsBody
    
    np.random.seed(seed)
    bodies = np.zeros(num_bodies, dtype=[
        ('pos', '<f4', 3),
        ('mass', '<f4'),
        ('vel', '<f4', 3),
        ('radius', '<f4'),
        ('acc', '<f4', 3),
        ('padding', '<f4')
    ])
    
    # Random positions in [-1000, 1000]
    bodies['pos'] = np.random.uniform(-1000, 1000, (num_bodies, 3))
    # Random masses [1e2, 1e6]
    bodies['mass'] = np.random.uniform(100, 1e6, num_bodies)
    # Random velocities [-50, 50]
    bodies['vel'] = np.random.uniform(-50, 50, (num_bodies, 3))
    # Random radii [1, 100]
    bodies['radius'] = np.random.uniform(1, 100, num_bodies)
    
    return bodies


if __name__ == "__main__":
    # Test dispatcher
    dispatcher = GPUComputeDispatcher(use_amd_gpu=True)
    
    kernel_path = Path(__file__).parent / "kernels" / "nbody.cl"
    dispatcher.compile_kernel("nbody", str(kernel_path))
    
    print("✓ GPU Dispatcher initialized successfully")
