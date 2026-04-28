# 🌌 Project Universe

# 

# Simulador espacial em evolução — foco em física realista, exploração e futura transição para 3D.

# 

# ✦ Visão geral

# 

# Projeto em Python com foco em simulação física N-body em tempo real, evolução de sistemas e construção de uma base sólida para uma engine moderna.

# 

# Interface em PT-BR

# Unidades físicas reais (km, UA, m/s², etc)

# Arquitetura modular e expansível

# ✦ Estado atual

# Física

# Gravidade N-body em tempo real

# Sistema de colisões por tipo de corpo

# Conservação básica de massa e momento

# Fragmentação com detritos físicos

# Temperatura dinâmica baseada em fluxo estelar

# Atmosfera simplificada (N₂, O₂, CO₂, CH₄)

# Simulação

# Habitabilidade baseada em fatores físicos

# Zonas habitáveis e limite de Roche

# Baricentro e zonas gravitacionais

# Evolução estelar básica

# Interação

# Editor orbital (mover, zerar V, circularizar)

# Presets de sistemas

# Controle de tempo (escala variável)

# ✦ Controles

# Ação	Comando

# Selecionar / mover	Mouse esquerdo

# Mover corpo	Botão "Mover" + mouse/setas

# Navegar câmera	Setas

# Movimento rápido	Shift + setas

# Zerar velocidade	Tecla V

# Circularizar órbita	Botão "Circularizar"

# Pausar tempo	Espaço

# ✦ Como rodar

# 

# Windows:

# 

# python -m venv .venv

# .venv\\Scripts\\activate

# pip install -r requirements.txt

# python main.py

# 

# Linux / macOS:

# 

# python3 -m venv .venv

# source .venv/bin/activate

# pip install -r requirements.txt

# python main.py

# 

# ✦ Estrutura do projeto

# 

# project\_universe/

# ├── main.py

# ├── simulation.py

# ├── body.py

# ├── catalog.py

# ├── config.py

# ├── engine.py

# ├── physics/

# │ ├── celestial.py

# │ ├── collision\_rules.py

# │ ├── environment.py

# │ ├── habitability.py

# │ ├── presets.py

# │ ├── sph.py

# │ └── units.py

# ├── systems/

# │ ├── labels.py

# │ └── orbits.py

# └── visuals/

# ├── background.py

# ├── body\_render.py

# └── panel.py

# 

# ✦ Roadmap

# Refatorar painel lateral

# Finalizar regras de colisão

# Implementar SPH real

# Melhorar clima e atmosfera

# Migrar para engine 3D

# ✦ Sistema de colisões

# absorb → corpo maior absorve menor

# merge → fusão em baixa velocidade

# fragment → gera detritos

# shatter → impacto destrutivo

# ✦ Convenção de branches

# 

# main → versão estável

# dev → integração

# patch-x → testes

# 

# ✦ Exemplo de commit

# 

# git add .

# git commit -m "Patch 12: orbital editor, BR units cleanup and repo polish"

# git push

# 

# ✦ Licença

# 

# Recomendado: MIT

# 

# ✦ Direção futura

# Renderização 3D

# Física avançada (SPH real)

# Engine moderna / Unity DOTS

# Simulação de galáxias e formação estelar

