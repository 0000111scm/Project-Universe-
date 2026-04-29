# Project Universe - Visual/Collision Patch 2

## Corrigido
- Colisao estrela-estrela nao gera mais avalanche de fragmentos.
- Ana vermelha contra Sol agora vira fusao estelar/nova visual, sem travar o app.
- Fragmentos recebem cooldown de colisao para evitar colisao recursiva no mesmo frame.
- Adicionado limite maximo de corpos para impedir explosao de entidades.
- Fragmentos pequenos agora tem tempo de vida e desaparecem depois de alguns segundos.
- Impactos aquecem o corpo sobrevivente/resultante.

## Melhorado
- Painel de inspecao agora mostra corpo gravitacional dominante.
- Painel tambem mostra aceleracao gravitacional aproximada causada pelo corpo dominante.

## Ja feito do plano
1. Fundo espacial realista: iniciado no Visual Upgrade 1.
2. Glow realista: iniciado para estrelas e eventos.
4. Painel de inspecao: expandido com gravidade dominante.
5. Colisoes fase 1.5: iniciado com cooldown, limite de entidades, vida de fragmentos e colisao estelar segura.

## Fica para o proximo passo
3. Camera cinematografica completa.
6. Orbitas/vetores melhores e baricentro.
- Separar renderizacao do main.py em visuals/body_render.py e visuals/ui.py.
- Criar sistema de escala visual adaptativa.
