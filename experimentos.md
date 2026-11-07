# Experimentos

Registro de cada ideia aplicada, com a medição que a sustenta. Todo número abaixo vem de `resultados/` (gerado por `scripts/medir.sh`). Antes/depois são sempre medianas de 3 execuções com os mesmos parâmetros.

## Protocolo

- Parâmetros de carga: `VUS=20`, `DURACAO=60s`, `AQUECIMENTO=15s`, `SEMENTE=42` (padrão do `medir.sh`, sem alteração).
- Limites dos containers originais: API 0,5 CPU / 256 MB; banco 1 CPU / 512 MB.
- Critério: mediana das 3 execuções. Com 3 execuções não há teste estatístico de significância: diferenças pequenas ou instáveis são descritas como inconclusivas.
- Antes de cada medição: `scripts/verificar-contrato.sh comparar` deve terminar em "Contrato mantido".

## Ambiente de medição

- Máquina: Linux 7.2 (Fedora 44), 16 CPUs, 15 GiB de RAM, governador de CPU `powersave`.
- Programas pesados fechados antes da linha de base (ver seção "Condição da máquina" abaixo).

## Desvio de ambiente: build da imagem da API

- **Sintoma:** `docker compose up -d --build` construiu a imagem sem `express` (`Cannot find module 'express'`, container reiniciando). O log do build mostra `npm error Exit handler never called!` e `http fetch GET https://registry.npmjs.org/... failed with EAI_AGAIN`.
- **Causa verificada:** o DNS dos containers do Docker (`45.90.28.0`, `45.90.30.0`, ...) não é alcançável a partir da rede padrão; o host resolve `registry.npmjs.org` normalmente. O `RUN npm ci` terminou com código 0 mesmo sem instalar as dependências, por isso o `docker compose build` não falhou.
- **Correção aplicada (só no build, sem mudar código, Dockerfile ou compose):**
  ```bash
  docker build --network host -t desafio-performance-api api
  docker compose up -d
  ```
  A imagem final tem o mesmo conteúdo (`express` e `pg` instalados via `npm ci --omit=dev`). Verificado com `docker run ... test -f /app/node_modules/express/package.json`.
- **Impacto na comparação:** nenhum sobre o runtime medido (rede, limites e código são os mesmos). Todas as medições, incluindo a linha de base, usam este mesmo método de build. Se alguma mudança exigir rebuild, usar o mesmo comando.
- Diagnóstico salvo em: `diagnostico/00-build-npm-dns.log` (ver commit de diagnóstico).

## Condição da máquina

A linha de base é a primeira medição com a aplicação original. Antes dela, a máquina estava com Firefox, Discord, OpenCode e outros programas abertos (memória livre ~640 MB). Por decisão do autor, esses programas são fechados antes das três medições da linha de base.

## Registro

| # | Ideia | Fonte | Status | Antes | Depois | Pastas de resultados | Conclusão |
|---|---|---|---|---|---|---|---|
| 00 | Linha de base (aplicação original, sem mudança) | — | — | — | — | (a preencher) | — |
