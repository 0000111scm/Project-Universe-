"""
Memory Alignment Verifier for std430 Layout
Ensures struct padding matches GPU SSBO buffer layout for AMD RX 570.
Critical to avoid data corruption from misaligned reads/writes.
"""

import struct
import numpy as np
from ctypes import sizeof, Structure, c_float, c_uint32, c_int32, POINTER
from typing import List, Dict, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MemoryAlignment")


class std430Validator:
    """
    Validates std430 memory layout compliance.
    std430 rules:
    - float32, int32: 4 bytes
    - vec2: 8 bytes
    - vec3: 12 bytes (NOT 16 like std140!)
    - vec4: 16 bytes
    - Structs/arrays: padded to 16-byte boundary
    """
    
    @staticmethod
    def validate_struct(struct_name: str, 
                       expected_size: int,
                       actual_data: bytes) -> bool:
        """Validate struct size matches std430 alignment."""
        actual_size = len(actual_data)
        is_valid = actual_size % 16 == 0 and actual_size == expected_size
        
        status = "✓" if is_valid else "✗"
        logger.info(f"{status} {struct_name}: {actual_size} bytes (expected {expected_size})")
        
        return is_valid
    
    @staticmethod
    def validate_all_bodies(bodies_buffer: np.ndarray, num_bodies: int) -> Tuple[bool, Dict]:
        """
        Validate array of PhysicsBody structs.
        
        Returns:
            (is_valid, diagnostics_dict)
        """
        from data.physics_types import PhysicsBody
        
        diagnostics = {
            "total_size": len(bodies_buffer),
            "expected_size": num_bodies * PhysicsBody.STRUCT_SIZE,
            "bytes_per_body": len(bodies_buffer) // num_bodies if num_bodies > 0 else 0,
            "alignment_ok": True,
            "sample_bodies": []
        }
        
        is_valid = diagnostics["total_size"] == diagnostics["expected_size"]
        
        if not is_valid:
            logger.error(f"Buffer size mismatch: {diagnostics['total_size']} != {diagnostics['expected_size']}")
        
        # Sample first 3 bodies for detailed inspection
        for i in range(min(3, num_bodies)):
            offset = i * PhysicsBody.STRUCT_SIZE
            body_data = bodies_buffer[offset:offset + PhysicsBody.STRUCT_SIZE]
            
            try:
                body = PhysicsBody.from_bytes(body_data)
                diagnostics["sample_bodies"].append({
                    "index": i,
                    "pos": tuple(body.pos),
                    "mass": float(body.mass),
                    "vel": tuple(body.vel),
                    "radius": float(body.radius)
                })
            except Exception as e:
                logger.error(f"Failed to parse body {i}: {e}")
                is_valid = False
        
        return is_valid, diagnostics


class AMDGPUMemoryAnalyzer:
    """
    AMD RX 570 specific memory optimization analysis.
    """
    
    # AMD RX 570 specs
    CACHE_LINE_SIZE = 64  # bytes
    L1_CACHE_SIZE = 16384  # bytes per compute unit
    LDS_SIZE = 65536  # Local Data Share (shared memory) per compute unit
    WORKGROUP_SIZE = 128
    
    @staticmethod
    def analyze_buffer_access_pattern(num_bodies: int,
                                     workgroup_size: int = 128) -> Dict:
        """
        Analyze memory access patterns for N-Body kernel.
        
        Returns:
            Optimization metrics and recommendations
        """
        from data.physics_types import PhysicsBody
        
        body_size = PhysicsBody.STRUCT_SIZE  # 64 bytes
        
        # Each workgroup loads WORKGROUP_SIZE bodies into LDS
        lds_usage_bytes = workgroup_size * body_size
        lds_utilization = (lds_usage_bytes / AMDGPUMemoryAnalyzer.LDS_SIZE) * 100
        
        # Cache line efficiency
        bodies_per_cache_line = AMDGPUMemoryAnalyzer.CACHE_LINE_SIZE // body_size
        wasted_per_line = AMDGPUMemoryAnalyzer.CACHE_LINE_SIZE - (bodies_per_cache_line * body_size)
        
        # Bandwidth estimation
        bytes_per_body_per_iteration = body_size * (num_bodies // workgroup_size + 1)
        total_bytes = workgroup_size * bytes_per_body_per_iteration
        
        analysis = {
            "num_bodies": num_bodies,
            "workgroup_size": workgroup_size,
            "body_size": body_size,
            "lds_usage_bytes": lds_usage_bytes,
            "lds_utilization_percent": lds_utilization,
            "cache_line_efficiency": {
                "bodies_per_cache_line": bodies_per_cache_line,
                "wasted_bytes_per_line": wasted_per_line,
                "efficiency_percent": (bodies_per_cache_line * body_size / AMDGPUMemoryAnalyzer.CACHE_LINE_SIZE) * 100
            },
            "memory_bandwidth_estimate_mb": total_bytes / 1e6,
            "recommendations": []
        }
        
        # Generate recommendations
        if lds_utilization > 75:
            analysis["recommendations"].append(
                f"⚠ LDS utilization high ({lds_utilization:.1f}%). Consider reducing workgroup size."
            )
        
        if analysis["cache_line_efficiency"]["efficiency_percent"] < 50:
            analysis["recommendations"].append(
                f"⚠ Cache efficiency low. Body struct may benefit from reordering."
            )
        
        if lds_utilization <= 60:
            analysis["recommendations"].append(
                f"✓ LDS utilization optimal ({lds_utilization:.1f}%)"
            )
        
        return analysis
    
    @staticmethod
    def print_analysis(analysis: Dict):
        """Pretty-print memory analysis."""
        logger.info("=" * 60)
        logger.info("AMD RX 570 Memory Analysis")
        logger.info("=" * 60)
        logger.info(f"Bodies: {analysis['num_bodies']}")
        logger.info(f"Workgroup Size: {analysis['workgroup_size']}")
        logger.info(f"Body Struct Size: {analysis['body_size']} bytes")
        logger.info(f"LDS Usage: {analysis['lds_usage_bytes']} bytes ({analysis['lds_utilization_percent']:.1f}%)")
        logger.info(f"Cache Line Efficiency: {analysis['cache_line_efficiency']['efficiency_percent']:.1f}%")
        logger.info(f"Est. Memory Bandwidth: {analysis['memory_bandwidth_estimate_mb']:.2f} MB")
        
        if analysis["recommendations"]:
            logger.info("\nRecommendations:")
            for rec in analysis["recommendations"]:
                logger.info(f"  {rec}")
        
        logger.info("=" * 60)


def verify_std430_alignment():
    """Run complete alignment verification."""
    from data.physics_types import PhysicsBody, MaterialComposition, SPHParticle
    
    logger.info("Starting std430 Memory Alignment Verification...")
    logger.info("=" * 60)
    
    # Test single body serialization
    test_body = PhysicsBody(
        pos=(10.0, 20.0, 30.0),
        mass=1e6,
        vel=(1.0, 2.0, 3.0),
        radius=50.0
    )
    
    body_bytes = test_body.to_bytes()
    validator = std430Validator()
    
    is_valid = validator.validate_struct("PhysicsBody", PhysicsBody.STRUCT_SIZE, body_bytes)
    
    # Test array of bodies
    logger.info("\nTesting body array (1000 bodies)...")
    bodies = np.array([test_body for _ in range(1000)])
    bodies_bytes = b''.join(body.to_bytes() for body in bodies)
    
    is_valid_array, diags = validator.validate_all_bodies(bodies_bytes, 1000)
    logger.info(f"Array validation: {'✓ PASS' if is_valid_array else '✗ FAIL'}")
    logger.info(f"Total buffer size: {diags['total_size']} bytes")
    logger.info(f"Per-body size: {diags['bytes_per_body']} bytes")
    
    # Memory analysis
    logger.info("\nMemory Analysis for N-Body Kernel:")
    analysis = AMDGPUMemoryAnalyzer.analyze_buffer_access_pattern(num_bodies=10000)
    AMDGPUMemoryAnalyzer.print_analysis(analysis)
    
    return is_valid and is_valid_array


if __name__ == "__main__":
    success = verify_std430_alignment()
    exit(0 if success else 1)
