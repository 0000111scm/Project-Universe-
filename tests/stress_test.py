"""
Stress Test and Profiling Suite for N-Body GPU Compute
Tests with 50,000 entities on AMD RX 570
Measures GPU compute time vs CPU dispatch overhead separately
"""

import numpy as np
import time
import logging
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("StressTest")


class GPUBenchmark:
    """
    Comprehensive benchmark suite for N-Body GPU compute.
    """
    
    def __init__(self, dispatcher):
        """
        Args:
            dispatcher: GPUComputeDispatcher instance
        """
        self.dispatcher = dispatcher
        self.results = {
            "device_info": {
                "name": str(dispatcher.device.name),
                "compute_units": dispatcher.device.max_compute_units,
                "max_clock": dispatcher.device.max_clock_frequency,
                "global_mem_mb": dispatcher.device.global_mem_size / 1e6
            },
            "benchmarks": []
        }
    
    def create_large_dataset(self, num_bodies: int) -> np.ndarray:
        """Create dataset with num_bodies physics bodies."""
        logger.info(f"Generating {num_bodies} test bodies...")
        
        bodies = np.zeros(num_bodies, dtype=[
            ('pos', '<f4', 3),
            ('mass', '<f4'),
            ('vel', '<f4', 3),
            ('radius', '<f4'),
            ('acc', '<f4', 3),
            ('padding', '<f4')
        ])
        
        # Realistic distribution: Sun-like body with planets
        np.random.seed(42)
        
        # Central mass (Sun)
        bodies['pos'][0] = [0, 0, 0]
        bodies['mass'][0] = 1e6
        bodies['radius'][0] = 30
        bodies['vel'][0] = [0, 0, 0]
        
        # Distributed bodies (planets/asteroids)
        for i in range(1, num_bodies):
            # Orbital distribution around central body
            angle = np.random.uniform(0, 2 * np.pi)
            distance = np.random.uniform(100, 2000)
            
            bodies['pos'][i] = [
                distance * np.cos(angle),
                distance * np.sin(angle),
                np.random.uniform(-100, 100)
            ]
            bodies['mass'][i] = np.random.uniform(1e2, 1e5)
            bodies['radius'][i] = np.random.uniform(1, 50)
            
            # Orbital velocity (simplified)
            orbital_speed = np.sqrt(6.67e-11 * bodies['mass'][0] / distance) if distance > 0 else 0
            vx = -orbital_speed * np.sin(angle)
            vy = orbital_speed * np.cos(angle)
            bodies['vel'][i] = [vx, vy, np.random.uniform(-5, 5)]
        
        logger.info(f"✓ Generated {num_bodies} bodies")
        logger.info(f"  Total mass: {np.sum(bodies['mass']):.2e}")
        logger.info(f"  Avg radius: {np.mean(bodies['radius']):.2f}")
        
        return bodies
    
    def benchmark_nbody_step(self, num_bodies: int, num_iterations: int = 100) -> Dict:
        """
        Benchmark N-Body computation with detailed timing breakdown.
        
        Returns:
            Dictionary with timing statistics
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"N-Body Benchmark: {num_bodies} bodies, {num_iterations} iterations")
        logger.info(f"{'='*70}")
        
        # Create test data
        bodies = self.create_large_dataset(num_bodies)
        
        # Create GPU buffers
        bodies_buffer = self.dispatcher.create_buffer("bodies", bodies)
        
        accelerations = np.zeros((num_bodies, 3), dtype=np.float32)
        accel_buffer = self.dispatcher.create_buffer("accelerations", accelerations)
        
        # Warm-up run
        logger.info("Warming up GPU...")
        self.dispatcher.execute_kernel(
            "nbody", "nbody_compute_forces",
            global_size=num_bodies,
            args=[bodies_buffer, accel_buffer, np.uint32(num_bodies)]
        )
        
        # Benchmark runs
        timings = {
            "gpu_times_ms": [],
            "wall_times_ms": [],
            "dispatch_overhead_ms": []
        }
        
        logger.info(f"\nRunning {num_iterations} iterations...")
        
        for iteration in range(num_iterations):
            wall_start = time.perf_counter()
            
            gpu_time, wall_time = self.dispatcher.execute_kernel(
                "nbody", "nbody_compute_forces",
                global_size=num_bodies,
                args=[bodies_buffer, accel_buffer, np.uint32(num_bodies)]
            )
            
            wall_elapsed = (time.perf_counter() - wall_start) * 1000
            dispatch_overhead = wall_elapsed - gpu_time
            
            timings["gpu_times_ms"].append(gpu_time)
            timings["wall_times_ms"].append(wall_elapsed)
            timings["dispatch_overhead_ms"].append(dispatch_overhead)
            
            if (iteration + 1) % 20 == 0:
                avg_gpu = np.mean(timings["gpu_times_ms"][-20:])
                avg_wall = np.mean(timings["wall_times_ms"][-20:])
                logger.info(f"  Iteration {iteration + 1}/{num_iterations} "
                           f"(GPU: {avg_gpu:.2f}ms, Wall: {avg_wall:.2f}ms)")
        
        # Calculate statistics
        stats = {
            "num_bodies": num_bodies,
            "num_iterations": num_iterations,
            "gpu_time_ms": {
                "mean": float(np.mean(timings["gpu_times_ms"])),
                "std": float(np.std(timings["gpu_times_ms"])),
                "min": float(np.min(timings["gpu_times_ms"])),
                "max": float(np.max(timings["gpu_times_ms"]))
            },
            "wall_time_ms": {
                "mean": float(np.mean(timings["wall_times_ms"])),
                "std": float(np.std(timings["wall_times_ms"])),
                "min": float(np.min(timings["wall_times_ms"])),
                "max": float(np.max(timings["wall_times_ms"]))
            },
            "dispatch_overhead_ms": {
                "mean": float(np.mean(timings["dispatch_overhead_ms"])),
                "std": float(np.std(timings["dispatch_overhead_ms"])),
                "min": float(np.min(timings["dispatch_overhead_ms"])),
                "max": float(np.max(timings["dispatch_overhead_ms"]))
            },
            "efficiency": {
                "overhead_percent": (np.mean(timings["dispatch_overhead_ms"]) / 
                                   np.mean(timings["wall_times_ms"]) * 100),
                "gflops": self._calculate_gflops(num_bodies, np.mean(timings["gpu_times_ms"]))
            }
        }
        
        # Print results
        logger.info(f"\n{'='*70}")
        logger.info("RESULTS SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"GPU Time (ms):     {stats['gpu_time_ms']['mean']:.3f} ± {stats['gpu_time_ms']['std']:.3f}")
        logger.info(f"Wall Time (ms):    {stats['wall_time_ms']['mean']:.3f} ± {stats['wall_time_ms']['std']:.3f}")
        logger.info(f"Dispatch OH (ms):  {stats['dispatch_overhead_ms']['mean']:.3f} ± {stats['dispatch_overhead_ms']['std']:.3f}")
        logger.info(f"Overhead %:        {stats['efficiency']['overhead_percent']:.1f}%")
        logger.info(f"Est. GPU GFLOPS:   {stats['efficiency']['gflops']:.1f}")
        logger.info(f"{'='*70}\n")
        
        # Cleanup
        self.dispatcher.buffers.pop("bodies", None)
        self.dispatcher.buffers.pop("accelerations", None)
        
        self.results["benchmarks"].append(stats)
        return stats
    
    @staticmethod
    def _calculate_gflops(num_bodies: int, gpu_time_ms: float) -> float:
        """
        Calculate GPU GFLOPS for N-Body computation.
        Each body interacts with N-1 other bodies: ~20 FLOPs per interaction
        Total: num_bodies * (num_bodies - 1) * 20 / 2
        """
        flops = num_bodies * num_bodies * 20 / gpu_time_ms / 1e6
        return flops
    
    def save_results(self, output_path: str = "benchmark_results.json"):
        """Save benchmark results to JSON."""
        self.results["timestamp"] = datetime.now().isoformat()
        
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"✓ Results saved to {output_path}")


def run_stress_test():
    """Execute full stress test suite."""
    try:
        from gpu.compute_dispatcher import GPUComputeDispatcher
        from pathlib import Path
        
        logger.info("Initializing GPU Compute Dispatcher...")
        dispatcher = GPUComputeDispatcher(use_amd_gpu=True, verbose=True)
        
        # Compile kernel
        kernel_path = Path("gpu/kernels/nbody.cl")
        if not kernel_path.exists():
            logger.error(f"Kernel not found at {kernel_path}")
            return
        
        logger.info(f"Compiling kernel from {kernel_path}...")
        dispatcher.compile_kernel("nbody", str(kernel_path))
        
        # Run benchmarks
        benchmark = GPUBenchmark(dispatcher)
        
        # Test scaling with different body counts
        test_sizes = [1000, 5000, 10000, 25000, 50000]
        
        for size in test_sizes:
            try:
                benchmark.benchmark_nbody_step(size, num_iterations=50)
            except Exception as e:
                logger.warning(f"Failed to run benchmark for {size} bodies: {e}")
                continue
        
        # Save results
        benchmark.save_results("benchmark_results.json")
        dispatcher.release()
        
        logger.info("✓ Stress test completed successfully")
        
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Ensure PyOpenCL is installed: pip install pyopencl")
    except Exception as e:
        logger.error(f"Stress test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_stress_test()
