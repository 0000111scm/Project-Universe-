# 🌌 Project Universe

> Simulador espacial em evolução com foco em física realista e futura transição para 3D.

---

## ✦ Visão geral

Simulação N-body em tempo real com arquitetura modular e foco em realismo físico.

- Interface em PT-BR  
- Unidades físicas reais (km, UA, m/s², °C)  
- Estrutura preparada para expansão  

---

## ✦ Estado atual

### Física
- Gravidade N-body  
- Colisões por tipo de corpo  
- Fragmentação com detritos  
- Temperatura dinâmica  
- Atmosfera simplificada  

### Simulação
- Habitabilidade baseada em fatores físicos  
- Zona habitável e limite de Roche  
- Baricentro e órbitas  

### Interação
- Editor orbital  
- Presets de sistemas  
- Controle de tempo  

---

## ✦ Controles

| Ação | Comando |
|------|--------|
| Selecionar / mover | Mouse |
| Mover corpo | Botão + setas |
| Navegar | Setas |
| Acelerar | Shift + setas |
| Zerar velocidade | V |
| Circularizar | Botão |
| Pausar | Espaço |

---

## ✦ Como rodar

### Windows
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Linux / macOS
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## ✦ Estrutura

```
project_universe/
├── main.py
├── simulation.py
├── physics/
├── systems/
└── visuals/
```

---

## ✦ Roadmap

- Refatorar UI  
- Melhorar colisões  
- Implementar SPH  
- Evoluir clima  
- Migrar para 3D  

---

## ✦ Licença

MIT
