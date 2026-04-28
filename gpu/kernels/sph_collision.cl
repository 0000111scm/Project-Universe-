/*
SPH (Smoothed Particle Hydrodynamics) Collision Dynamics Kernel
Implements realistic collision physics with material fragmentation
Optimized for AMD RX 570 GPU
*/

#define WORKGROUP_SIZE 128
#define SOFTENING 1.0f
#define SPH_KERNEL_RADIUS 2.0f
#define DENSITY_THRESHOLD 100.0f
#define PRESSURE_SCALE 1000.0f
#define FRAGMENTATION_THRESHOLD 0.5f

typedef struct {
    float pos[3];
    float mass;
    float vel[3];
    float radius;
    float acc[3];
    float padding;
} PhysicsBody;

typedef struct {
    float pos[3];
    float mass;
    float vel[3];
    float radius;
    float density;
    float pressure;
    float material_id;
    float smoothing_length;
} SPHParticle;

/*
 * Spatial Hash Grid Cell Computation
 * Maps 3D position to linear hash cell index
 */
uint compute_grid_hash(float3 pos, float cell_size) {
    int3 grid_pos = (int3)(
        convert_int(floor(pos.x / cell_size)),
        convert_int(floor(pos.y / cell_size)),
        convert_int(floor(pos.z / cell_size))
    );
    
    uint hash = ((grid_pos.x * 73856093) ^ (grid_pos.y * 19349663) ^ (grid_pos.z * 83492791));
    return hash & 0x7FFFFFFF;  /* Keep positive */
}

/*
 * SPH Kernel Function - Cubic Spline
 * Smooths force contributions based on distance
 */
float sph_kernel_cubic(float r, float h) {
    if (r > h) return 0.0f;
    
    float q = r / h;
    float factor = 8.0f / (3.14159f * h * h * h);
    
    if (q < 0.5f) {
        return factor * (6.0f * q * q * q - 6.0f * q * q + 1.0f);
    } else {
        return factor * 2.0f * (1.0f - q) * (1.0f - q) * (1.0f - q);
    }
}

/*
 * SPH Kernel Gradient
 */
float3 sph_kernel_gradient(float3 r, float h) {
    float r_mag = length(r);
    if (r_mag < 0.001f || r_mag > h) return (float3)(0.0f);
    
    float q = r_mag / h;
    float factor = 8.0f / (3.14159f * h * h * h * h);
    float gradient_mag;
    
    if (q < 0.5f) {
        gradient_mag = factor * (18.0f * q * q - 12.0f * q);
    } else {
        gradient_mag = factor * (-6.0f * (1.0f - q) * (1.0f - q));
    }
    
    return gradient_mag * (r / r_mag);
}

/*
 * Density Calculation Kernel
 * Computes local density at each particle position using nearby particles
 * Uses spatial hashing for O(n) neighbor search
 */
__kernel void sph_density_calculation(
    __global SPHParticle *particles,
    __global uint *grid_indices,
    __global uint *grid_counts,
    uint num_particles,
    float cell_size,
    float mass_scale)
{
    uint global_id = get_global_id(0);
    if (global_id >= num_particles) return;
    
    SPHParticle p = particles[global_id];
    float density = 0.0f;
    float h = p.smoothing_length;
    
    /* Check neighboring grid cells (3x3x3 = 27 cells) */
    int3 grid_pos = (int3)(
        convert_int(floor(p.pos[0] / cell_size)),
        convert_int(floor(p.pos[1] / cell_size)),
        convert_int(floor(p.pos[2] / cell_size))
    );
    
    for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
            for (int dz = -1; dz <= 1; dz++) {
                int3 neighbor_pos = grid_pos + (int3)(dx, dy, dz);
                uint neighbor_hash = compute_grid_hash(
                    (float3)(neighbor_pos.x * cell_size, 
                             neighbor_pos.y * cell_size, 
                             neighbor_pos.z * cell_size),
                    cell_size
                );
                
                /* Density contribution from neighbors in this cell */
                uint cell_start = grid_indices[neighbor_hash];
                uint cell_count = grid_counts[neighbor_hash];
                
                for (uint i = 0; i < cell_count; i++) {
                    uint j = cell_start + i;
                    if (j >= num_particles) continue;
                    
                    SPHParticle neighbor = particles[j];
                    float3 r_diff = (float3)(
                        neighbor.pos[0] - p.pos[0],
                        neighbor.pos[1] - p.pos[1],
                        neighbor.pos[2] - p.pos[2]
                    );
                    float r = length(r_diff);
                    
                    if (r < h) {
                        density += neighbor.mass * sph_kernel_cubic(r, h);
                    }
                }
            }
        }
    }
    
    particles[global_id].density = max(density, DENSITY_THRESHOLD);
}

/*
 * Pressure Calculation Kernel
 * Computes pressure based on density and equation of state
 */
__kernel void sph_pressure_calculation(
    __global SPHParticle *particles,
    uint num_particles,
    float rest_density,
    float gas_constant,
    float gamma)
{
    uint global_id = get_global_id(0);
    if (global_id >= num_particles) return;
    
    SPHParticle p = particles[global_id];
    
    /* Tait equation of state: P = B * ((rho/rho0)^gamma - 1) */
    float density_ratio = p.density / rest_density;
    float pressure = (gas_constant / gamma) * (pow(density_ratio, gamma) - 1.0f);
    
    particles[global_id].pressure = max(0.0f, pressure);
}

/*
 * Collision Force Calculation Kernel
 * Computes pressure and viscous forces between nearby particles
 */
__kernel void sph_collision_forces(
    __global SPHParticle *particles,
    __global float3 *forces,
    __global uint *grid_indices,
    __global uint *grid_counts,
    uint num_particles,
    float cell_size,
    float viscosity,
    float dt)
{
    uint global_id = get_global_id(0);
    uint local_id = get_local_id(0);
    
    if (global_id >= num_particles) return;
    
    __local float3 local_forces[WORKGROUP_SIZE];
    local_forces[local_id] = (float3)(0.0f);
    
    SPHParticle p = particles[global_id];
    float3 pressure_force = (float3)(0.0f);
    float3 viscous_force = (float3)(0.0f);
    float h = p.smoothing_length;
    
    /* Neighbor search in grid */
    int3 grid_pos = (int3)(
        convert_int(floor(p.pos[0] / cell_size)),
        convert_int(floor(p.pos[1] / cell_size)),
        convert_int(floor(p.pos[2] / cell_size))
    );
    
    for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
            for (int dz = -1; dz <= 1; dz++) {
                int3 neighbor_pos = grid_pos + (int3)(dx, dy, dz);
                uint neighbor_hash = compute_grid_hash(
                    (float3)(neighbor_pos.x * cell_size,
                             neighbor_pos.y * cell_size,
                             neighbor_pos.z * cell_size),
                    cell_size
                );
                
                uint cell_start = grid_indices[neighbor_hash];
                uint cell_count = grid_counts[neighbor_hash];
                
                for (uint i = 0; i < cell_count; i++) {
                    uint j = cell_start + i;
                    if (j >= num_particles || j == global_id) continue;
                    
                    SPHParticle neighbor = particles[j];
                    float3 r_diff = (float3)(
                        neighbor.pos[0] - p.pos[0],
                        neighbor.pos[1] - p.pos[1],
                        neighbor.pos[2] - p.pos[2]
                    );
                    float r = length(r_diff);
                    
                    if (r < h && r > 0.001f) {
                        /* Pressure force */
                        float3 grad_kernel = sph_kernel_gradient(r_diff, h);
                        float pressure_term = -(p.pressure / (p.density * p.density) + 
                                              neighbor.pressure / (neighbor.density * neighbor.density));
                        pressure_force += neighbor.mass * pressure_term * grad_kernel;
                        
                        /* Viscous force (artificial viscosity) */
                        float3 vel_diff = (float3)(
                            neighbor.vel[0] - p.vel[0],
                            neighbor.vel[1] - p.vel[1],
                            neighbor.vel[2] - p.vel[2]
                        );
                        
                        float dot_prod = dot(vel_diff, r_diff);
                        if (dot_prod < 0.0f) {  /* Only if approaching */
                            float alpha = 0.01f;
                            float c_avg = 50.0f;  /* Sound speed estimate */
                            float rho_avg = (p.density + neighbor.density) / 2.0f;
                            
                            float viscous_term = -2.0f * alpha * c_avg * viscosity / rho_avg;
                            viscous_force += neighbor.mass * viscous_term * 
                                           (dot_prod / (r*r + 0.01f*h*h)) * grad_kernel;
                        }
                    }
                }
            }
        }
    }
    
    float3 total_force = pressure_force + viscous_force;
    forces[global_id] = total_force;
}

/*
 * Material Fragmentation Kernel
 * Determines if collision energy exceeds fragmentation threshold
 * Marks particles for ejecta generation
 */
__kernel void sph_fragmentation_check(
    __global SPHParticle *particles,
    __global uint *fragment_markers,
    __global float3 *ejecta_velocities,
    uint num_particles,
    float fragmentation_energy_threshold,
    float material_strength)
{
    uint global_id = get_global_id(0);
    if (global_id >= num_particles) return;
    
    SPHParticle p = particles[global_id];
    
    /* Calculate kinetic energy per unit mass */
    float vel_mag_sq = (p.vel[0]*p.vel[0] + p.vel[1]*p.vel[1] + p.vel[2]*p.vel[2]);
    float kinetic_energy_per_mass = 0.5f * vel_mag_sq;
    
    /* Calculate stress (pressure over density) */
    float stress = p.pressure / p.density;
    
    /* Fragmentation criterion: total energy exceeds threshold */
    float total_energy = kinetic_energy_per_mass + stress;
    
    if (total_energy > fragmentation_energy_threshold / p.mass) {
        fragment_markers[global_id] = 1;  /* Mark for fragmentation */
        
        /* Ejecta velocity = current velocity + thermal expansion */
        float expansion_factor = sqrt(total_energy) * 0.1f;
        ejecta_velocities[global_id] = (float3)(
            p.vel[0] * (1.0f + expansion_factor),
            p.vel[1] * (1.0f + expansion_factor),
            p.vel[2] * (1.0f + expansion_factor)
        );
    } else {
        fragment_markers[global_id] = 0;
        ejecta_velocities[global_id] = (float3)(p.vel[0], p.vel[1], p.vel[2]);
    }
}

/*
 * Atmospheric Drag Kernel
 * Simulates aerodynamic drag and thermal ablation for incoming particles
 */
__kernel void sph_atmospheric_drag(
    __global SPHParticle *particles,
    __global float *mass_loss,
    uint num_particles,
    float atmosphere_density,
    float drag_coefficient,
    float ablation_temperature,
    float dt)
{
    uint global_id = get_global_id(0);
    if (global_id >= num_particles) return;
    
    SPHParticle p = particles[global_id];
    
    /* Velocity magnitude */
    float vel_mag = sqrt(p.vel[0]*p.vel[0] + p.vel[1]*p.vel[1] + p.vel[2]*p.vel[2]);
    
    /* Drag force: F_d = 0.5 * rho * v^2 * A * C_d */
    float cross_section = 3.14159f * p.radius * p.radius;
    float drag_force = 0.5f * atmosphere_density * vel_mag * vel_mag * cross_section * drag_coefficient;
    
    /* Deceleration */
    float deceleration = drag_force / p.mass;
    
    /* Thermal ablation: mass loss proportional to kinetic energy */
    float ablation_factor = (vel_mag * vel_mag) / (2.0f * ablation_temperature);
    float mass_loss_rate = max(0.0f, ablation_factor * p.mass * dt * 0.001f);
    
    mass_loss[global_id] = mass_loss_rate;
    
    /* Surface heating (simplified - for visualization) */
    if (vel_mag > 10.0f) {
        particles[global_id].pressure += mass_loss_rate * 100.0f;  /* Heat accumulation */
    }
}

/*
 * Integration Kernel - Update velocity and position with collision forces
 */
__kernel void sph_integrate_step(
    __global SPHParticle *particles,
    __global const float3 *forces,
    float dt,
    uint num_particles)
{
    uint global_id = get_global_id(0);
    if (global_id >= num_particles) return;
    
    SPHParticle p = particles[global_id];
    
    /* Update velocity: v = v + (F/m) * dt */
    float3 acceleration = forces[global_id] / p.mass;
    
    particles[global_id].vel[0] += acceleration.x * dt;
    particles[global_id].vel[1] += acceleration.y * dt;
    particles[global_id].vel[2] += acceleration.z * dt;
    
    /* Update position: x = x + v * dt */
    particles[global_id].pos[0] += particles[global_id].vel[0] * dt;
    particles[global_id].pos[1] += particles[global_id].vel[1] * dt;
    particles[global_id].pos[2] += particles[global_id].vel[2] * dt;
}
