# PATCH 80 HOTFIX — Performance Cadence

Corrige benchmark lento:
- colisão/Roche não rodam todo substep em sistemas grandes
- termodinâmica/surface grid entram por cadência
- SPH steps entram por cadência em muitos corpos
- Barnes-Hut threshold reduzido para 48 corpos

Gravidade principal continua rodando todo substep.
