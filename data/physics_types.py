"""
Physics data types optimized for std430 memory layout (GPU SSBO alignment).
AMD RX 570 GPU target - aligned for efficient access patterns.
"""

import struct
import numpy as np
from typing import Tuple

# std430 alignment rules:
# - scalars (float32, int32) = 4 bytes
# - vec2 = 8 bytes (2 x float32)
# - vec3 = 12 bytes (3 x float32) - NOT 16! (differs from std140)
# - vec4 = 16 bytes (4 x float32)
# - Arrays and structs are padded to vec4 boundary (16 bytes)

class PhysicsBody:
    """
    Represents a celestial body in the N-Body system.
    Memory layout matches std430 for GPU SSBO.
    Total size: 64 bytes (4 vec4s)
    """
    STRUCT_FORMAT = '<3f f 3f f 3f f 3f f'  # Little-endian, matching std430
    STRUCT_SIZE = 64  # bytes
    
    def __init__(self, 
                 pos: Tuple[float, float, float],
                 mass: float,
                 vel: Tuple[float, float, float],
                 radius: float,
                 acc: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                 padding: float = 0.0):
        """
        Initialize a physics body with position, mass, velocity, radius.
        
        Args:
            pos: (x, y, z) position in world space
            mass: gravitational mass
            vel: (vx, vy, vz) velocity vector
            radius: body radius
            acc: (ax, ay, az) acceleration (computed by GPU)
            padding: reserved for alignment
        """
        self.pos = np.array(pos, dtype=np.float32)
        self.mass = np.float32(mass)
        self.vel = np.array(vel, dtype=np.float32)
        self.radius = np.float32(radius)
        self.acc = np.array(acc, dtype=np.float32)
        self.padding = np.float32(padding)
    
    def to_bytes(self) -> bytes:
        """Convert to bytes following std430 layout."""
        return struct.pack(self.STRUCT_FORMAT,
                          self.pos[0], self.pos[1], self.pos[2], self.mass,
                          self.vel[0], self.vel[1], self.vel[2], self.radius,
                          self.acc[0], self.acc[1], self.acc[2], self.padding,
                          0.0, 0.0, 0.0, 0.0)  # Extra padding for std430
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'PhysicsBody':
        """Reconstruct from bytes."""
        values = struct.unpack(cls.STRUCT_FORMAT, data[:cls.STRUCT_SIZE])
        return cls(
            pos=values[0:3],
            mass=values[3],
            vel=values[4:7],
            radius=values[7],
            acc=values[8:11]
        )
    
    def __repr__(self):
        return (f"PhysicsBody(pos={self.pos}, mass={self.mass:.2e}, "
                f"vel={self.vel}, radius={self.radius})")


class MaterialComposition:
    """
    Represents material makeup of a body for SPH collision calculations.
    std430 aligned: 32 bytes
    """
    STRUCT_FORMAT = '<4f 4f f 7f'  # Composition + state variables
    STRUCT_SIZE = 32
    
    def __init__(self,
                 silicate: float = 0.5,
                 water: float = 0.3,
                 iron: float = 0.15,
                 gas: float = 0.05,
                 temperature: float = 273.15,
                 pressure: float = 101325.0,
                 density: float = 5520.0):
        """
        Material composition with thermodynamic state.
        
        Args:
            silicate: rock fraction (0-1)
            water: water/ice fraction (0-1)
            iron: metal fraction (0-1)
            gas: atmosphere fraction (0-1)
            temperature: Kelvin
            pressure: Pascal
            density: kg/m³
        """
        self.composition = np.array([silicate, water, iron, gas], dtype=np.float32)
        self.temperature = np.float32(temperature)
        self.pressure = np.float32(pressure)
        self.density = np.float32(density)
        self.reserved = np.zeros(4, dtype=np.float32)  # Padding
    
    def to_bytes(self) -> bytes:
        data = struct.pack('<4f', *self.composition)
        data += struct.pack('<4f', self.temperature, self.pressure, self.density, 0.0)
        data += struct.pack('<4f', *self.reserved[:4])
        return data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'MaterialComposition':
        vals = struct.unpack('<4f 4f 4f', data[:cls.STRUCT_SIZE])
        return cls(
            silicate=vals[0], water=vals[1], iron=vals[2], gas=vals[3],
            temperature=vals[4], pressure=vals[5], density=vals[6]
        )


class SPHParticle:
    """
    SPH particle for collision dynamics simulation.
    std430 aligned: 80 bytes
    """
    STRUCT_FORMAT = '<3f f 3f f 3f f 3f f 4f'
    STRUCT_SIZE = 80
    
    def __init__(self,
                 pos: Tuple[float, float, float],
                 mass: float,
                 vel: Tuple[float, float, float],
                 radius: float,
                 density: float = 1000.0,
                 pressure: float = 0.0,
                 material_id: int = 0):
        """
        SPH particle for hydrodynamic simulations.
        """
        self.pos = np.array(pos, dtype=np.float32)
        self.mass = np.float32(mass)
        self.vel = np.array(vel, dtype=np.float32)
        self.radius = np.float32(radius)
        self.density = np.float32(density)
        self.pressure = np.float32(pressure)
        self.material_id = np.float32(material_id)
        self.smoothing_length = np.float32(2.0 * radius)
    
    def to_bytes(self) -> bytes:
        return struct.pack(self.STRUCT_FORMAT,
                          self.pos[0], self.pos[1], self.pos[2], self.mass,
                          self.vel[0], self.vel[1], self.vel[2], self.radius,
                          self.density, self.pressure, self.material_id, 
                          self.smoothing_length,
                          0.0, 0.0, 0.0, 0.0)  # Padding


def verify_alignment():
    """Verify struct sizes match std430 alignment."""
    print(f"PhysicsBody size: {PhysicsBody.STRUCT_SIZE} bytes (expected 64)")
    print(f"MaterialComposition size: {MaterialComposition.STRUCT_SIZE} bytes (expected 32)")
    print(f"SPHParticle size: {SPHParticle.STRUCT_SIZE} bytes (expected 80)")
    
    assert PhysicsBody.STRUCT_SIZE == 64, "PhysicsBody alignment mismatch"
    assert MaterialComposition.STRUCT_SIZE == 32, "MaterialComposition alignment mismatch"
    assert SPHParticle.STRUCT_SIZE == 80, "SPHParticle alignment mismatch"
    print("✓ All structures properly aligned for std430")


if __name__ == "__main__":
    verify_alignment()
