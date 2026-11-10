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

A linha de base foi medida na aplicação original após o encerramento de programas pesados e processos de background, garantindo baixa variabilidade entre execuções (coeficiente de variação de vazão CV = 3,0%, indicando medição altamente estável e reprodutível).

## Registro

| # | Ideia | Fonte | Status | Antes | Depois | Pastas de resultados | Conclusão |
|---|---|---|---|---|---|---|---|
| 00 | Linha de base (aplicação original, sem mudança) | — | Medido | — | 3,62 req/s · p95 17.932,0 ms · CPU banco 97,1% · CPU api 5,0% | [20261110-095041-00-linha-de-base](resultados/20261110-095041-00-linha-de-base/)<br>[20261110-095428-00-linha-de-base](resultados/20261110-095428-00-linha-de-base/)<br>[20261110-095605-00-linha-de-base](resultados/20261110-095605-00-linha-de-base/) | Saturação quase total do banco de dados (97,1% CPU média). Latência p95 dominada por `pedidos-do-cliente` (~18–20 s) e `top-produtos` (~21–25 s). Contrato mantido (42/42). |
| 01 | Connection pooling via `pg.Pool` (`max: 20`) | [node-postgres pooling](https://node-postgres.com/features/pooling) | Medido | 3,62 req/s · p95 17.932,0 ms · CPU banco 97,1% · CPU api 5,0% | 4,81 req/s (+32,9%) · p95 13.320,5 ms (-25,7%) · CPU banco 96,3% · CPU api 4,9% | [20261110-100637-01-connection-pool](resultados/20261110-100637-01-connection-pool/)<br>[20261110-100820-01-connection-pool](resultados/20261110-100820-01-connection-pool/)<br>[20261110-100958-01-connection-pool](resultados/20261110-100958-01-connection-pool/) | Ganho expressivo de vazão (+32,9%) e queda de 35,7% na latência mediana (de 1.248 ms para 802 ms). Rota `/clientes/:id` caiu de 297 ms para ~11–90 ms. Banco ainda satura em 96,3% devido à falta de índices (Seq Scans). Contrato mantido (42/42). |
| 02 | Índices B-tree estratégicos (`banco/03-indices.sql`) | [PostgreSQL 16 Indexes](https://www.postgresql.org/docs/16/indexes.html) · [Graefe (2011)](https://doi.org/10.1561/1900000028) | Medido | 4,81 req/s · p95 13.320,5 ms · CPU banco 96,3% · CPU api 4,9% | 28,23 req/s (+486,9%) · p95 4.408,9 ms (-66,9%) · CPU banco 86,9% · CPU api 20,9% | [20261110-101549-02-indices-banco](resultados/20261110-101549-02-indices-banco/)<br>[20261110-101731-02-indices-banco](resultados/20261110-101731-02-indices-banco/)<br>[20261110-101905-02-indices-banco](resultados/20261110-101905-02-indices-banco/) | Salto de vazão de quase 6x (+486,9% vs pool, +679,8% vs base). Latência mediana caiu de 802 ms para 82,1 ms (-89,8%) e p95 despencou para 4.408,9 ms. Rota `/clientes/:id/pedidos` caiu de 11.744 ms para 115 ms (100x mais rápida). Contrato mantido (42/42). |
| 03 | Pushdown de agregação SQL em `/relatorios/vendas-por-dia` | [PostgreSQL 16 Aggregate Functions](https://www.postgresql.org/docs/16/functions-aggregate.html) · [Garcia-Molina et al. (2008)](https://dl.acm.org/doi/book/10.5555/1455506) | Medido | 28,23 req/s · p95 4.408,9 ms · CPU banco 86,9% · CPU api 20,9% | 29,02 req/s (+2,8%) · p95 4.428,0 ms · CPU banco 89,1% · CPU api 3,1% | [20261110-102601-03-pushdown-agregacao](resultados/20261110-102601-03-pushdown-agregacao/)<br>[20261110-102739-03-pushdown-agregacao](resultados/20261110-102739-03-pushdown-agregacao/)<br>[20261110-102913-03-pushdown-agregacao](resultados/20261110-102913-03-pushdown-agregacao/) | Eliminação da transferência massiva de dezenas de milhares de registros e agregação in-memory no Node.js. Latência mediana global despencou de 82,1 ms para 26,5 ms (-67,7%). CPU da API caiu de 20,9% para 3,1% (-85,2%) e RAM média da API caiu para 26,4 MiB (queda de mais de 50%). Latência mediana de vendas-por-dia caiu para 2.330 ms. Contrato mantido (42/42). |
