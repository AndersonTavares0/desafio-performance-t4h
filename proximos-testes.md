# Próximos Testes (Backlog de Otimizações)

Fichas técnicas de intervenções mapeadas durante o diagnóstico, mas não incluídas nas 3 mudanças principais por restrição de escopo e tempo. Nenhuma métrica aqui foi inventada; cada ficha traz a hipótese, o ganho teórico esperado, a fonte de referência e o protocolo para teste futuro.

---

### Ficha 01: Extensão `pg_trgm` e Índice GIN em `produtos(nome)`
- **Alvo:** Rota `GET /produtos/busca?q=` (peso 15% na carga).
- **Problema atual:** A busca usa `WHERE nome ILIKE '%' || $1 || '%'`. Índices B-tree tradicionais não indexam buscas que começam com caractere curinga (`%`), forçando `Seq Scan` em todos os 20.000 produtos a cada busca.
- **Intervenção proposta:**
  ```sql
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  CREATE INDEX idx_produtos_nome_trgm ON produtos USING gin (nome gin_trgm_ops);
  ```
- **Ganho esperado:** Redução do tempo de execução da query de ~9,2 ms para <1 ms.
- **Custo e Trade-offs:** Índices GIN aumentam o tempo de inserção de novos produtos e ocupam maior volume em disco.
- **Fonte de referência:** PostgreSQL Documentation: pg_trgm (https://www.postgresql.org/docs/16/pgtrgm.html).
- **Como testar:** Adicionar extensão e índice em script SQL, subir com `docker compose down -v && docker compose up -d`, validar contrato e medir com `scripts/medir.sh`.

---

### Ficha 02: Pré-agregação no PostgreSQL para `/relatorios/vendas-por-dia`
- **Alvo:** Rota `GET /relatorios/vendas-por-dia` (peso 8% na carga).
- **Problema atual:** A query atual busca linhas individuais transferindo até 13.000 registros para o Node.js, incluindo o campo de texto `observacoes` (largura de ~300 bytes) que não é utilizado na resposta. A agregação é feita por loops em JavaScript no Node.
- **Intervenção proposta:**
  Executar a agregação diretamente no PostgreSQL via `GROUP BY (p.criado_em::date)` e retornar apenas as colunas necessárias (`dia`, `pedidos`, `itens`, `receita_centavos`), sem trazer a coluna `observacoes`.
- **Ganho esperado:** Redução do tráfego de rede entre banco e API de ~4 MB para <5 KB por requisição, liberando memória e CPU do Node.js.
- **Fonte de referência:** Garcia-Molina et al., Database Systems (Capítulo 15 — Projection and Aggregation Pushdown).
- **Como testar:** Alterar a query em `api/src/rotas.js`, conferir contrato com `scripts/verificar-contrato.sh comparar` e medir com `scripts/medir.sh`.

---

### Ficha 03: Cache LRU ou Visão Materializada para `/relatorios/top-produtos`
- **Alvo:** Rota `GET /relatorios/top-produtos` (peso 2% na carga).
- **Problema atual:** Executa varredura e junção de 1,5 milhão de itens em toda chamada, consumindo ~950 ms de CPU em repouso e gerando p95 de 25 segundos na linha de base.
- **Intervenção proposta:**
  Implementar cache em memória no Node.js (com TTL curto, ex.: 30 segundos) ou tabela agregada com atualização assíncrona.
- **Ganho esperado:** Queda da latência de 25.000 ms para <1 ms para chamadas com cache quente.
- **Custo e Trade-offs:** Potencial inconsistência eventual caso dados novos de vendas não apareçam imediatamente no relatório.
- **Fonte de referência:** Martin Fowler, Patterns of Enterprise Application Architecture (Two-Step View / Gateway Caching).
- **Como testar:** Adicionar middleware de cache em memória no Node.js, validar contrato e comparar percentis p95 sob carga contínua.

---

### Ficha 04: Ajuste de Parâmetros de Memória do PostgreSQL (`postgresql.conf`)
- **Alvo:** Desempenho geral do banco de dados PostgreSQL 16.
- **Problema atual:** O container roda com a configuração padrão do PostgreSQL (`shared_buffers = 128MB`, `work_mem = 4MB`).
- **Intervenção proposta:**
  Ajustar parâmetros via `command` no `docker-compose.yml`:
  `-c shared_buffers=192MB -c work_mem=8MB -c effective_cache_size=384MB`.
- **Ganho esperado:** Maior taxa de acerto no cache compartilhado (`shared hit` em vez de `read` em disco) para tabelas e índices frequentemente acessados.
- **Fonte de referência:** PostgreSQL Documentation: Resource Consumption (https://www.postgresql.org/docs/16/runtime-config-resource.html).
- **Como testar:** Inserir flags no serviço `banco` do `docker-compose.yml`, reiniciar a stack e comparar a taxa de hits com a medição anterior.
