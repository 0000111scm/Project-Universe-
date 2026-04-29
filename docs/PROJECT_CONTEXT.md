# PROJECT UNIVERSE — CONTEXTO DO PROJETO

## VISÃO GERAL

Project Universe é um simulador espacial 2D em Python com foco TOTAL em física realista.

NÃO é um jogo arcade.  
O comportamento deve ser emergente, derivado de leis físicas reais, não de scripts fixos.

---

## PRINCÍPIOS OBRIGATÓRIOS

- Sem "if mágico", como "massa maior absorve"
- Sem efeitos visuais substituindo física
- Energia não desaparece: apenas se transforma
- Momento linear e angular devem ser respeitados sempre que possível
- Código modular, principalmente dentro de `physics/`
- Física correta tem prioridade sobre performance nesta fase
- Performance será tratada depois com NumPy, Barnes-Hut, paralelismo e/ou engine moderna

---

## OBJETIVO FINAL

Criar um simulador espacial comparável ou superior ao Universe Sandbox em coerência física.

O simulador deve permitir fenômenos emergentes como:

- órbitas estáveis
- colisões físicas por energia, massa, ângulo e material
- crateras proporcionais
- fragmentação física coerente
- ejeção de massa
- perda atmosférica
- aquecimento local
- formação de detritos e anéis
- ruptura por maré
- discos de acreção
- evolução térmica
- evolução futura para 3D

---

## IDIOMA E UNIDADES

Interface, documentação e unidades devem seguir PT-BR.

Unidades preferenciais:

- temperatura: °C ou K conforme contexto físico
- velocidade: km/s
- distância: km ou UA
- pressão: bar
- gravidade: m/s²
- massa planetária: M⊕
- massa solar: M☉

---

## ARQUITETURA ATUAL

Estrutura principal:

- `main.py` → interface, entrada do usuário, renderização geral
- `simulation.py` → loop físico principal
- `body.py` → definição dos corpos celestes
- `physics/` → sistemas físicos
- `systems/` → sistemas auxiliares
- `visuals/` → renderização visual
- `docs/` → documentação

Arquivos físicos importantes já criados:

- `physics/impact_solver.py`
- `physics/material_model.py`
- `physics/angular_momentum.py`
- `physics/structural_damage.py`

---

## ESTADO ATUAL DA FÍSICA

### Gravidade

- Gravidade N-body funcional
- Cálculo de acelerações feito antes da integração
- Pares i/j calculados corretamente
- Ainda O(N²) em Python puro

Problema atual:
- integrador ainda é Euler/semi-Euler
- precisa migrar para Leapfrog ou Velocity Verlet

---

### Colisões

Já existe `ImpactSolver`.

Ele calcula:

- massa reduzida
- velocidade relativa
- velocidade normal
- velocidade tangencial
- energia de impacto
- energia específica
- limiar de disrupção

Classificação de impacto:

- accretion
- merge
- hit-and-run
- graze
- cratering
- partial disruption
- catastrophic disruption
- vaporization

O sistema antigo `_collision_kind()` ainda existe, mas a direção correta é usar `_collision_kind_from_impact()` baseado no solver.

---

### Energia

Energia do impacto é particionada em:

- calor
- deformação
- ejeção
- fragmentação

Problema atual:
- temperatura ainda é global por corpo
- impacto pequeno pode aquecer o corpo inteiro
- precisa de energia local por camadas no futuro

---

### Materiais

Modelo inicial de materiais:

- rock
- ice
- metal
- gas
- plasma
- blackhole

Cada material possui aproximações para:

- densidade
- resistência estrutural
- ponto de fusão
- ponto de vaporização
- restituição
- absorção térmica
- tendência de fragmentação
- tendência de ejeção

Limitação atual:
- ainda não existe EOS real ou simplificada por pressão/temperatura

---

### Fragmentação

Já existe fragmentação básica:

- baseada em energia disponível
- parcialmente direcional
- fragmentos herdam material/composição/cor do corpo original
- fragmentos recebem velocidade baseada em direção de ejeção

Limitação atual:
- ainda precisa melhorar conservação rigorosa de momento
- ainda existe alguma aleatoriedade controlada

---

### Momento angular

Já implementado parcialmente:

- impacto tangencial gera spin
- fusões conservam spin aproximado
- existe módulo `physics/angular_momentum.py`

---

### Atmosfera

Já existe perda atmosférica por impacto.

Depende de:

- energia específica
- velocidade relativa
- ângulo
- massa do projétil
- gravidade/escape do corpo

Limitação:
- atmosfera ainda é um escalar simples, não camada física real

---

### Dano estrutural

Já existe `physics/structural_damage.py`.

Implementado:

- integridade estrutural por corpo
- dano acumulado
- dano térmico
- ruptura progressiva
- impactos repetidos enfraquecem corpos

---

### Editor orbital

Já existe editor orbital básico:

- circularizar órbita
- zerar velocidade
- seguir corpo
- mover corpo pausado preservando/recalculando órbita

---

## PROBLEMAS CRÍTICOS IDENTIFICADOS

### 1. Integrador é Euler/semi-Euler

Trecho conceitual atual:

```python
b.vel += b.acc * sdt
b.pos += b.vel * sdt
```

Problema:

- não conserva energia orbital
- órbitas derivam com o tempo
- piora com `time_scale` alto
- pode forçar hacks como `_limit_giant_velocity`

Correção necessária:

- implementar Leapfrog ou Velocity Verlet

---

### 2. `_limit_giant_velocity` é hack não físico

Problema:

- corta velocidade artificialmente
- viola conservação de momento
- provavelmente mascara instabilidade do integrador

Direção:

- manter temporariamente durante PATCH 47
- remover ou reduzir depois que o integrador estiver estável

---

### 3. `check_roche()` está vazio

Problema:

- ruptura por maré não existe fisicamente no loop
- corpos só interagem por colisão geométrica

Correção futura:

- implementar Roche real
- corpos dentro do limite devem sofrer deformação/perda de massa/ruptura progressiva

---

### 4. Temperatura é global por corpo

Problema:

- um asteroide pequeno não deveria aquecer o planeta inteiro
- crateras, fusão local e gradientes térmicos não emergem

Correção futura:

- modelo mínimo de camadas:
  - crosta
  - manto
  - núcleo

Impacto deposita energia na crosta primeiro.

---

### 5. `simulate_preview()` usa integrador inconsistente

Problema:

- preview orbital pode mostrar trajetória diferente da simulação real

Correção:

- aplicar o mesmo método de integração do loop principal

---

## ROADMAP ATUAL

### PATCH 47 — INTEGRADOR FÍSICO CORRETO

Prioridade máxima.

Objetivo:

- substituir Euler/semi-Euler por Leapfrog ou Velocity Verlet
- corrigir `step()`
- corrigir `simulate_preview()`
- preservar comportamento visual
- não alterar colisões neste patch

Regras:

- calcular acelerações para todos os corpos
- aplicar meio passo de velocidade
- atualizar posição
- recalcular aceleração
- aplicar segundo meio passo de velocidade
- manter independência da ordem dos corpos

Importante:

- não remover `_limit_giant_velocity` ainda
- se instabilidade aparecer, ajustar `sdt`, `SUB` ou `time_scale`

---

### PATCH 48 — NUMPY N-BODY

Objetivo:

- vetorizar cálculo de gravidade com NumPy
- acelerar `_compute_accelerations`
- manter fallback Python caso NumPy não exista

Ganho esperado:

- 5x a 20x dependendo do número de corpos

---

### PATCH 49 — ROCHE REAL

Objetivo:

- implementar `check_roche()`
- detectar corpos dentro do limite de Roche
- aplicar dano estrutural progressivo
- gerar perda de massa antes da colisão direta

---

### PATCH 50 — ENERGIA LOCAL POR CAMADAS

Objetivo:

- criar modelo interno mínimo:
  - crosta
  - manto
  - núcleo

Cada camada deve ter:

- fração de massa
- temperatura
- estado físico
- material dominante

Impacto deve depositar energia localmente, não no corpo inteiro.

---

### PATCH 51 — FRAGMENTAÇÃO CONSERVATIVA MELHORADA

Objetivo:

- melhorar conservação de momento linear
- reduzir aleatoriedade
- derivar velocidades dos fragmentos da geometria do impacto
- melhorar formação de detritos/anéis

---

### PATCH 52 — EOS SIMPLIFICADA

Objetivo:

- materiais devem responder a temperatura e pressão
- sólido/líquido/gás/plasma
- comportamento dinâmico por material

---

## DIREÇÃO FUTURA

### Médio prazo

- adaptive timestep
- forças de maré
- discos de acreção
- anéis
- melhor evolução térmica
- atmosfera em camadas

### Longo prazo

- Barnes-Hut para gravidade O(N log N)
- SPH para colisões de alta energia
- migração para 3D
- engine moderna, idealmente Unity DOTS/C# ou equivalente
- GPU compute para partículas/fluidos

---

## EXPECTATIVA PARA QUALQUER AGENTE DE CÓDIGO

Antes de modificar o projeto:

1. Ler este arquivo inteiro
2. Entender que o projeto prioriza física realista
3. Implementar apenas o patch solicitado
4. Evitar refatorações grandes não pedidas
5. Não adicionar soluções arcade
6. Explicar arquivos alterados
7. Explicar por que a mudança é fisicamente correta
8. Manter compatibilidade com o projeto atual

---

## ESTADO ATUAL DA CONTINUAÇÃO

Estamos no início de:

```txt
PATCH 47 — Integrador Leapfrog / Velocity Verlet
```

Tarefa imediata:

- analisar `simulation.py`
- substituir o integrador atual
- ajustar `simulate_preview()`
- validar estabilidade orbital
- não alterar colisões ainda
