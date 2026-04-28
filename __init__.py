"""Project Universe - Astrophysics GPU Simulator"""

__version__ = "0.1.0"
__author__ = "Senior Software Engineer"

from .data.physics_types import PhysicsBody, MaterialComposition, SPHParticle

__all__ = [
    "PhysicsBody",
    "MaterialComposition", 
    "SPHParticle"
]
