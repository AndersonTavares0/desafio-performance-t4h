# Próximos Testes (Backlog de Otimizações)

Fichas técnicas de intervenções mapeadas durante o diagnóstico e a pesquisa bibliográfica, mas reservadas para testes futuros por restrição de escopo e tempo. Conforme as regras do edital, nenhuma métrica aqui foi inventada: cada ficha traz o problema identificado, a hipótese de ganho, a fonte primária de referência e o protocolo para validação futura.

---

### Ficha 01: Extensão `pg_trgm` e Índice GIN em `produtos(nome)`
- **Alvo:** Rota `GET /produtos/busca?q=` (peso 15% na carga).
- **Problema atual:** A busca textual utiliza `WHERE nome ILIKE '%' || $1 || '%'`. Índices B-tree tradicionais não indexam predicados que iniciam com curinga (`%`), forçando varredura sequencial (`Seq Scan`) em todos os 20.000 produtos a cada requisição.
- **Intervenção proposta:**
  ```sql
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  CREATE INDEX idx_produtos_nome_trgm ON produtos USING gin (nome gin_trgm_ops);
  ```
- **Ganho esperado:** Substituição do `Seq Scan` por `Bitmap Index Scan`, reduzindo o tempo de consulta de ~9,2 ms para <1 ms.
- **Custo e Trade-offs:** Índices GIN aumentam o tempo de inserção de novos produtos e ocupam maior volume de armazenamento em disco.
- **Fonte de referência:** PostgreSQL 16 Documentation: pg_trgm (<https://www.postgresql.org/docs/16/pgtrgm.html>).
- **Como testar:** Adicionar extensão e índice DDL em script SQL, subir com `docker compose down -v && docker compose up -d`, validar contrato com `scripts/verificar-contrato.sh comparar` e medir com `scripts/medir.sh`.

---

### Ficha 02: Cache em Memória com TTL para `/relatorios/top-produtos`
- **Alvo:** Rota `GET /relatorios/top-produtos` (peso 2% na carga).
- **Problema atual:** A rota processa e agrega 1,5 milhão de itens a cada chamada, gerando latência na casa dos 4,7 a 5,5 segundos mesmo após a indexação básica.
- **Intervenção proposta:**
  Implementar cache em memória no Node.js (via Map LRU ou Redis leve) com tempo de expiração curto (TTL de 30 a 60 segundos).
- **Ganho esperado:** Queda da latência de ~4.700 ms para submilissegundo para requisições com cache quente.
- **Custo e Trade-offs:** Potencial inconsistência eventual transitória caso novas vendas ocorram dentro da janela do TTL.
- **Fonte de referência:** Martin Fowler, *Patterns of Enterprise Application Architecture* (Gateway Caching).
- **Como testar:** Inserir middleware de cache em memória em `api/src/rotas.js`, validar o contrato com `scripts/verificar-contrato.sh comparar` e avaliar p95 sob carga com `scripts/medir.sh`.

---

### Ficha 03: Ajuste de Parâmetros de Memória do PostgreSQL (`postgresql.conf`)
- **Alvo:** Desempenho e taxa de acerto de cache do PostgreSQL 16.
- **Problema atual:** O container roda com a configuração padrão conservadora do PostgreSQL (`shared_buffers = 128MB`, `work_mem = 4MB`).
- **Intervenção proposta:**
  Ajustar parâmetros de memória via diretiva `command` no `docker-compose.yml`:
  ```yaml
  command: ["postgres", "-c", "shared_buffers=192MB", "-c", "work_mem=16MB", "-c", "effective_cache_size=384MB"]
  ```
- **Ganho esperado:** Maior retenção de páginas de dados e índices no pool de buffers compartilhados (`shared hit`), diminuindo a necessidade de I/O em disco sob concorrência.
- **Fonte de referência:** PostgreSQL 16 Documentation: Resource Consumption (<https://www.postgresql.org/docs/16/runtime-config-resource.html>).
- **Como testar:** Aplicar as flags no `docker-compose.yml`, reiniciar a stack e comparar taxas de cache hit e tempo de resposta geral.

---

### Ficha 04: Paginação por Keyset (Cursor) em `/pedidos`
- **Alvo:** Rota `GET /pedidos?status=&pagina=` (peso 15% na carga).
- **Problema atual:** A paginação é baseada em `OFFSET`. Para páginas altas (ex.: página 15.000), o PostgreSQL precisa ler e descartar milhares de tuplas antes de retornar as 20 desejadas.
- **Intervenção proposta:**
  Adicionar paginação orientada a chaves (Keyset Pagination) utilizando `WHERE criado_em < $cursor_data OR (criado_em = $cursor_data AND id < $cursor_id)`.
- **Ganho esperado:** Custo de consulta constante $O(1)$ independentemente da profundidade da página navegada.
- **Custo e Trade-offs:** Exigiria adaptação da assinatura dos parâmetros da API (de `pagina=N` para `cursor=token`), demandando alteração contratual que o edital atual veda.
- **Fonte de referência:** Markus Winand, *Use The Index, Luke!* — Paging Through Results.
- **Como testar:** Em evolução arquitetural que permita atualização do contrato de paginação da API.

---

### Ficha 05: Logging Assíncrono com Pino no Runtime Node.js
- **Alvo:** Vazão global da API e redução de latência do Event Loop.
- **Problema atual:** Em `api/src/server.js`, a cada requisição é executado `console.log(JSON.stringify(registro))`. Em ambientes Linux conteinerizados, gravações em stdout conectadas a pipes do Docker operam de forma síncrona, bloqueando o Event Loop da aplicação (diagnóstico documentado em `diagnostico/03-logging-e-event-loop.txt`).
- **Intervenção proposta:**
  Substituir o middleware de log manual pela biblioteca `pino`, que utiliza escrita em buffer com descritor assíncrono.
- **Ganho esperado:** Liberação de tempo de Event Loop do Node.js, prevenindo eventuais atrasos de enfileiramento em requisições de alta concorrência.
- **Fonte de referência:** Node.js 20 LTS Documentation: Process I/O & Synchronous Writes (<https://nodejs.org/docs/latest-v20.x/api/process.html#a-note-on-process-io>).
- **Como testar:** Substituir a chamada de log em `api/src/server.js`, validar contrato e medir estabilidade de vazão.
