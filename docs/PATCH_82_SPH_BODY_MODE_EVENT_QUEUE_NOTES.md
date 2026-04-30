# PATCH 82 — SPH Body Mode + Stable Collision Event Queue

Cronograma:
- SPH Body Mode

Adicionado por regressões:
- colisões piorando/travando
- mutação de self.bodies durante loop
- cascata de fragmentos

Mudanças:
- novo physics_core/sph_body_mode.py
- novo physics_core/collision_event_queue.py
- check_collisions reescrito para fila de eventos
- coleta colisões por snapshot
- resolve poucos eventos por frame
- bloqueia corpo duplicado no mesmo frame
- fragmentos não disparam colisão pesada
- SPH pesado segue desligado por padrão, com modo pending seguro
