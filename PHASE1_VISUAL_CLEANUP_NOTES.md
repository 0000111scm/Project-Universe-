# Project Universe - Phase 1 visual cleanup

## O que mudou

### 1. Rótulos de fragmentos/detritos
- Fragmentos agora nascem com `show_label = False`.
- O nome real continua sendo `Fragmento`, mas não fica poluindo a tela.
- O rótulo só aparece se o fragmento estiver selecionado/seguido ou, por pouco tempo, em zoom alto.
- Nomes longos são compactados com reticências.

### 2. Trilhas de detritos
- Corpos normais continuam com trilhas longas.
- Fragmentos usam trilhas curtas para reduzir sujeira visual.

### 3. Save/load
- O salvamento agora mantém `is_fragment` e `show_label`.

## Próxima parte da Fase 1

Recomendado:
1. Separar UI do `main.py` em módulos menores.
2. Criar painel de debug de simulação: FPS, corpos, substeps, tempo simulado.
3. Criar presets limpos: Sistema Solar, binária, colisão planetária, campo de asteroides.
4. Melhorar câmera/zoom com foco em corpo selecionado.
