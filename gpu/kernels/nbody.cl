/* 
N-Body Gravitational Computation Kernel
OpenCL kernel optimized for AMD RX 570 GPU
Workgroup size: 128 threads
Uses local (shared) memory to reduce VRAM bandwidth
*/

#define SOFTENING 25.0f  /* Collision distance softening */
#define G 200.0f         /* Gravitational constant (scaled for simulation) */
#define WORKGROUP_SIZE 128

/* Physics body struct - matches std430 layout from Python */
typedef struct {
    float pos[3];
    float mass;
    float vel[3];
    float radius;
    float acc[3];
    float padding;
} PhysicsBody;

/*
 * N-Body Force Calculation Kernel
 * Each work item processes one body and calculates its gravitational acceleration
 * Local memory stores body data for the current workgroup for efficient reuse
 */
__kernel void nbody_compute_forces(
    __global PhysicsBody *bodies,
    __global float *forces,  /* Output: flattened acceleration vectors */
    uint num_bodies)
{
    uint global_id = get_global_id(0);
    uint local_id = get_local_id(0);
    uint group_id = get_group_id(0);
    
    /* Local memory for body positions and masses (reduce VRAM bandwidth) */
    __local float4 local_bodies[WORKGROUP_SIZE];  /* pos + mass packed */
    __local float local_mass[WORKGROUP_SIZE];
    
    /* Initialize acceleration for this body */
    float ax = 0.0f, ay = 0.0f, az = 0.0f;
    
    if (global_id >= num_bodies) return;
    
    /* Load this body's data */
    float px = bodies[global_id].pos[0];
    float py = bodies[global_id].pos[1];
    float pz = bodies[global_id].pos[2];
    float m_self = bodies[global_id].mass;
    
    /* Process all bodies in chunks (workgroup tiles) */
    for (uint tile = 0; tile < (num_bodies + WORKGROUP_SIZE - 1) / WORKGROUP_SIZE; tile++) {
        uint body_idx = tile * WORKGROUP_SIZE + local_id;
        
        /* Load tile into local memory */
        if (body_idx < num_bodies) {
            local_bodies[local_id] = (float4)(
                bodies[body_idx].pos[0],
                bodies[body_idx].pos[1],
                bodies[body_idx].pos[2],
                bodies[body_idx].mass
            );
            local_mass[local_id] = bodies[body_idx].mass;
        } else {
            local_bodies[local_id] = (float4)(0.0f, 0.0f, 0.0f, 0.0f);
            local_mass[local_id] = 0.0f;
        }
        
        /* Synchronize to ensure all data is loaded */
        barrier(CLK_LOCAL_MEM_FENCE);
        
        /* Compute forces from all bodies in this tile */
        #pragma unroll 4
        for (uint i = 0; i < WORKGROUP_SIZE; i++) {
            uint idx = tile * WORKGROUP_SIZE + i;
            if (idx >= num_bodies || idx == global_id) continue;
            
            /* Gravitational force calculation */
            float dx = local_bodies[i].x - px;
            float dy = local_bodies[i].y - py;
            float dz = local_bodies[i].z - pz;
            
            float dist_sq = dx*dx + dy*dy + dz*dz + SOFTENING*SOFTENING;
            float dist = sqrt(dist_sq);
            float dist_cubed = dist_sq * dist;
            
            /* Avoid division by zero */
            if (dist_cubed < 1e-6f) continue;
            
            float force_magnitude = G * m_self * local_bodies[i].w / dist_cubed;
            
            ax += force_magnitude * dx;
            ay += force_magnitude * dy;
            az += force_magnitude * dz;
        }
        
        barrier(CLK_LOCAL_MEM_FENCE);
    }
    
    /* Write back accelerations */
    forces[global_id * 3 + 0] = ax / m_self;
    forces[global_id * 3 + 1] = ay / m_self;
    forces[global_id * 3 + 2] = az / m_self;
}

/*
 * Velocity Integration Kernel (Verlet-style)
 * Updates velocities based on computed accelerations
 */
__kernel void integrate_velocity(
    __global PhysicsBody *bodies,
    __global const float *accelerations,
    float dt,
    uint num_bodies)
{
    uint global_id = get_global_id(0);
    if (global_id >= num_bodies) return;
    
    /* Semi-implicit Euler: v = v + a*dt */
    bodies[global_id].vel[0] += accelerations[global_id * 3 + 0] * dt;
    bodies[global_id].vel[1] += accelerations[global_id * 3 + 1] * dt;
    bodies[global_id].vel[2] += accelerations[global_id * 3 + 2] * dt;
}

/*
 * Position Integration Kernel
 * Updates positions based on velocities
 */
__kernel void integrate_position(
    __global PhysicsBody *bodies,
    float dt,
    uint num_bodies)
{
    uint global_id = get_global_id(0);
    if (global_id >= num_bodies) return;
    
    /* Update position: x = x + v*dt */
    bodies[global_id].pos[0] += bodies[global_id].vel[0] * dt;
    bodies[global_id].pos[1] += bodies[global_id].vel[1] * dt;
    bodies[global_id].pos[2] += bodies[global_id].vel[2] * dt;
}

/*
 * RK4 Stage Kernel - First stage
 * Compute k1 = f(t, y)
 */
__kernel void rk4_stage1(
    __global PhysicsBody *bodies,
    __global float *k1_accelerations,
    uint num_bodies)
{
    /* This kernel computes k1 - same as nbody_compute_forces */
    uint global_id = get_global_id(0);
    uint local_id = get_local_id(0);
    
    __local float4 local_bodies[WORKGROUP_SIZE];
    
    float ax = 0.0f, ay = 0.0f, az = 0.0f;
    
    if (global_id >= num_bodies) return;
    
    float px = bodies[global_id].pos[0];
    float py = bodies[global_id].pos[1];
    float pz = bodies[global_id].pos[2];
    float m_self = bodies[global_id].mass;
    
    for (uint tile = 0; tile < (num_bodies + WORKGROUP_SIZE - 1) / WORKGROUP_SIZE; tile++) {
        uint body_idx = tile * WORKGROUP_SIZE + local_id;
        
        if (body_idx < num_bodies) {
            local_bodies[local_id] = (float4)(
                bodies[body_idx].pos[0],
                bodies[body_idx].pos[1],
                bodies[body_idx].pos[2],
                bodies[body_idx].mass
            );
        } else {
            local_bodies[local_id] = (float4)(0.0f);
        }
        
        barrier(CLK_LOCAL_MEM_FENCE);
        
        for (uint i = 0; i < WORKGROUP_SIZE; i++) {
            uint idx = tile * WORKGROUP_SIZE + i;
            if (idx >= num_bodies || idx == global_id) continue;
            
            float dx = local_bodies[i].x - px;
            float dy = local_bodies[i].y - py;
            float dz = local_bodies[i].z - pz;
            
            float dist_sq = dx*dx + dy*dy + dz*dz + SOFTENING*SOFTENING;
            float dist = sqrt(dist_sq);
            float dist_cubed = dist_sq * dist;
            
            if (dist_cubed < 1e-6f) continue;
            
            float force_magnitude = G * m_self * local_bodies[i].w / dist_cubed;
            
            ax += force_magnitude * dx;
            ay += force_magnitude * dy;
            az += force_magnitude * dz;
        }
        
        barrier(CLK_LOCAL_MEM_FENCE);
    }
    
    k1_accelerations[global_id * 3 + 0] = ax / m_self;
    k1_accelerations[global_id * 3 + 1] = ay / m_self;
    k1_accelerations[global_id * 3 + 2] = az / m_self;
}
