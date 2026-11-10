# De 3,6 para 29 req/s: como multiplicamos a vazão da API por 8 sem gastar mais recursos

**Autor:** Anderson Tavares (`anderson.g.tavares@gmail.com`)  
**Data:** 10 de novembro de 2026  
**Repositório do Projeto:** [AndersonTavares0/desafio-performance-t4h](https://github.com/AndersonTavares0/desafio-performance-t4h)

## 1. Resumo

A API da loja fictícia sofria para atender 20 usuários virtuais: entregava apenas 3,62 req/s, com latência mediana de 1,2 s, p95 de 17,9 s e o banco consumindo 97,1% da CPU. Investigando os logs, encontramos três problemas: conexões abertas do zero a cada query, falta de índices em chaves estrangeiras e agregação de dados brutos na memória do Node.js. Colocamos um pool de conexões (`pg.Pool`), criamos 6 índices B-tree e passamos a agregação para o SQL. Sem alterar os limites dos containers (0,5 CPU na API e 1,0 CPU no banco) e mantendo as 42 respostas do contrato idênticas às originais, a vazão subiu 8 vezes (29,02 req/s) e a latência mediana caiu 97,9% (de 1.248 ms para 26,5 ms).

## 2. Contexto e diagnóstico

A aplicação roda em dois containers Docker limitados: a API Node.js 20 tem 0,5 CPU e 256 MiB, e o banco PostgreSQL 16 tem 1,0 CPU e 512 MiB, com dados sintéticos de 100 mil clientes, 20 mil produtos, 500 mil pedidos e 1,5 milhão de itens. Na linha de base ([20261110-095041-00-linha-de-base](../resultados/20261110-095041-00-linha-de-base/)), o sistema registrou 3,62 req/s e p95 de 17.932,0 ms, com CPU do banco em 97,1% e API em 5,0%.

Os diagnósticos em [diagnostico/](../diagnostico/) apontaram três gargalos:
1. **Conexões efêmeras:** `api/src/db.js` criava `new pg.Client()` por consulta. No PostgreSQL (baseado em `fork`), isso gerou sobrecarga no SO ([02-conexao-e-pooling.txt](../diagnostico/02-conexao-e-pooling.txt)), com até 30 forks por chamada em `/clientes/:id/pedidos`.
2. **Varreduras sequenciais:** `EXPLAIN (ANALYZE, BUFFERS)` ([01-explain-queries-linha-de-base.txt](../diagnostico/01-explain-queries-linha-de-base.txt)) confirmou a falta de índices. Consultas por `cliente_id` liam 500 mil pedidos e 1,5 milhão de itens via `Seq Scan`, elevando `/clientes/:id/pedidos` a 15,2 s.
3. **Agregação em memória:** `/relatorios/vendas-por-dia` transferia milhares de tuplas para o Node.js agrupar com `Map`, gastando rede e memória.

Hipóteses de causa:
- *Hipótese 1:* Conexões efêmeras saturam a CPU do banco pelo custo de `fork()`.
- *Hipótese 2:* A falta de índices força varreduras completas em milhões de linhas a cada junção.
- *Hipótese 3:* Transferir dados brutos para agregação em memória sobrecarrega a rede e a CPU da API.

## 3. Estado da arte

### Pooling de conexões em bancos baseados em processos
O PostgreSQL aloca um processo dedicado por sessão via `fork()`. A documentação oficial (Cap. 20) e a do `node-postgres` explicam que clientes efêmeros acarretam alocação de sockets, autenticação e catálogos locais a cada requisição. O Connection Pooling preserva conexões abertas para atender consultas em fila, reduzindo latência e consumo de descritores de arquivo.

### Índices B-Tree para chaves estrangeiras e buscas
Graefe (2011) demonstra que a árvore B tem custo O(log N), contra O(N) da varredura sequencial. Garcia-Molina et al. (2008) destacam que consultas sem índices secundários forçam varreduras completas. A documentação do PostgreSQL 16 (Cap. 11) adverte que chaves `REFERENCES` não são indexadas automaticamente, e que filtros case-insensitive (`lower(email)`) demandam índices funcionais.

### Agregação no próprio banco (Pushdown)
O princípio de pushdown estabelece que filtros e somatórios devem rodar no motor de banco (Garcia-Molina et al., 2008). O PostgreSQL possui rotinas de agregação (`COUNT`, `SUM`, `GROUP BY`) vetorizadas em C (Cap. 9.21). Agregar no SQL comprime milhares de linhas em poucas tuplas, economizando rede e liberando o Event Loop da API (Node.js LTS Docs).

## 4. Alternativas consideradas

Para priorizar o que testar primeiro, comparamos as alternativas pelo impacto esperado, risco e esforço na matriz de [pesquisa/alternativas-e-escolha.md](../pesquisa/alternativas-e-escolha.md):

| Alternativa | Custo | Desempenho | Risco | Esforço |
|---|---|---|---|---|
| A. Connection Pooling (`pg.Pool`) | Zero (sem dependências novas) | Alto alívio de CPU e queda de latência | Nulo (não altera consultas) | Baixo (5 linhas em `db.js`) |
| B. Índices B-Tree Estratégicos | Baixo (~62 MiB de disco/RAM) | Crítico (elimina gargalo dominante das junções) | Muito baixo (preserva esquema) | Baixo (DDL em `03-indices.sql`) |
| C. Pushdown de Agregação SQL | Zero | Redução de tráfego de rede e consumo de RAM | Baixo (exige tipagem exata) | Médio (reestruturação de query) |
| D. Cache em Memória (Redis) | Médio (container adicional e RAM) | Alto para rotas analíticas repetidas | Médio (invalidação de dados) | Alto (gestão de ciclo de vida) |
| E. Índice Trigrama GIN (`pg_trgm`) | Médio (extensão C e índice pesado) | Alto em buscas textuais com `ILIKE` | Baixo | Médio (extensão do PostgreSQL) |

Escolhemos A, B e C por atacarem os gargalos a custo zero. Descartamos o Redis (D) de início para evitar complexidade prematura. O índice trigrama (E) ficou para depois em [proximos-testes.md](../proximos-testes.md), pois o foco principal era o tráfego de chaves estrangeiras.

## 5. Solução escolhida e por quê

Aplicamos as melhorias em três passos separados, medindo cada um:
1. **Connection Pooling no Driver:** Uso de `new Pool({ max: 20 })` em `api/src/db.js`, casando com 20 VUs e eliminando `fork()` repetido sem estourar a memória do banco.
2. **Índices B-Tree Estratégicos:** Script `banco/03-indices.sql` com 6 índices em chaves estrangeiras (`pedidos.cliente_id`, `itens_pedido.pedido_id`), busca (`lower(email)`), paginação e datas. Reduz o custo de junções de varredura linear para busca em árvore B.
3. **Pushdown SQL em Vendas por Dia:** Reescrita de `/relatorios/vendas-por-dia` em `api/src/rotas.js` delegando `GROUP BY`, `SUM` e `COUNT` ao SQL, com `Number(...)` para manter os tipos. Descartou-se agregar no Node.js para poupar CPU e RAM.

## 6. Experimento e resultado

Cada mudança seguiu o protocolo do edital (3 baterias de 60s com 20 VUs, calculando a mediana):

| Mudança | Hipótese | p95 antes → depois | req/s antes → depois | CPU/memória | Pastas de resultados | Conclusão |
|---|---|---|---|---|---|---|
| **01-connection-pool** | Reutilizar conexões elimina sobrecarga de forks | 17.932 ms → 13.321 ms (-25,7%) | 3,62 → 4,81 (+32,9%) | Banco: 97,1% → 96,3%<br>API: 5,0% → 4,9% (RAM: 40,8 MiB) | [01-connection-pool](../resultados/20261110-100637-01-connection-pool/) | Vazão subiu 32,9% e `/clientes/:id` caiu para 88 ms. Banco continuou no teto por falta de índices. |
| **02-indices-banco** | Índices em chaves estrangeiras eliminam Seq Scans | 13.321 ms → 4.409 ms (-66,9%) | 4,81 → 28,23 (+486,9%) | Banco: 96,3% → 86,9%<br>API: 4,9% → 20,9% (RAM: 58,3 MiB) | [02-indices-banco](../resultados/20261110-101549-02-indices-banco/) | Salto de 6x na vazão. A rota `/clientes/:id/pedidos` caiu para 115 ms. Contrato mantido. |
| **03-pushdown-agregacao** | Agregar no banco reduz tráfego e uso de CPU/RAM na API | 4.409 ms → 4.428 ms (estável) | 28,23 → 29,02 (+2,8%) | Banco: 86,9% → 89,1%<br>API: 20,9% → 3,1% (RAM: 26,4 MiB) | [03-pushdown-agregacao](../resultados/20261110-102601-03-pushdown-agregacao/) | Latência mediana caiu para 26,5 ms. CPU da API recuou 85% e RAM caiu pela metade. Contrato mantido. |

No resultado final, a vazão subiu para **29,02 req/s** (**+701,7%** vs. base de 3,62 req/s) e a latência mediana caiu para **26,5 ms** (contra 1.248,0 ms na base), com todas as 42 respostas do contrato preservadas.

**O que não funcionou e por quê:**  
O pool isolado não destravou o banco (CPU de 97% para 96%), pois o gargalo eram as buscas sem índice. Já o pushdown SQL não reduziu o p95 global (~4,4 s), pois a cauda de latência é puxada por duas consultas pesadas: a paginação profunda via OFFSET em `/pedidos` (páginas até 1.000 com p95 de ~10 s) e o somatório de 1,5 milhão de itens em `top-produtos` (~4,7 s). O pushdown poupou CPU e RAM na API, mas não eliminou a cauda dessas duas rotas.

![p95 antes e depois de cada mudança](img/p95-por-mudanca.png)

## 7. Limites e testes futuros

A solução tem limites práticos que precisam ser considerados:
1. **Sobrecarga em Escrita:** Os 6 índices ocupam ~62 MiB e geram manutenção de páginas em `INSERT`/`UPDATE`, exigindo reavaliação sob cargas com predominância de escrita.
2. **Busca Textual sem Índice:** A rota `/produtos/busca` ainda utiliza `ILIKE '%termo%'`, exigindo varredura sequencial em 20 mil produtos.
3. **Amostragem e Hardware:** Seguimos o protocolo de 3 baterias (n=3) do edital. As métricas absolutas refletem a máquina de teste (16 CPUs, Linux); em outro hardware os valores mudam, mas as proporções de ganho tendem a se manter. Em produção, recomendam-se mais baterias (n >= 5) com avaliação de CV e intervalo de confiança.

**O que refutaria a conclusão:**  
Nossa tese seria refutada se uma carga mista de escrita gerasse contenção de travas nas árvores B que superasse o ganho nas leituras, ou se o catálogo de produtos crescesse a ponto de tornar o `ILIKE` o gargalo único do sistema.

Testes futuros priorizados em [proximos-testes.md](../proximos-testes.md):
- Índice GIN trigrama (`pg_trgm`) para acelerar buscas textuais.
- Camada de cache em memória com TTL para `/relatorios/top-produtos`.
- Ajuste de parâmetros do PostgreSQL (`shared_buffers = 128MB`, `work_mem = 16MB`).

## 8. Referências

1. The PostgreSQL Global Development Group. *PostgreSQL 16.4 Documentation: Chapter 11 — Indexes*. 2024. Disponível em: <https://www.postgresql.org/docs/16/indexes.html>. Acesso em: 10 nov. 2026.
2. The PostgreSQL Global Development Group. *PostgreSQL 16.4 Documentation: Chapter 20 — Server Configuration: Connections and Authentication*. 2024. Disponível em: <https://www.postgresql.org/docs/16/runtime-config-connection.html>. Acesso em: 10 nov. 2026.
3. The PostgreSQL Global Development Group. *PostgreSQL 16.4 Documentation: Chapter 9.21 — Aggregate Functions*. 2024. Disponível em: <https://www.postgresql.org/docs/16/functions-aggregate.html>. Acesso em: 10 nov. 2026.
4. Carlson, Brian; Comunidade node-postgres. *node-postgres Documentation: Connection Pooling*. 2024. Disponível em: <https://node-postgres.com/features/pooling>. Acesso em: 10 nov. 2026.
5. Graefe, Goetz. *Modern B-Tree Techniques*. Foundations and Trends in Databases, Vol. 3, No. 4, pp. 203–402, 2011. DOI: <https://doi.org/10.1561/1900000028>. Acesso em: 10 nov. 2026.
6. Garcia-Molina, Hector; Ullman, Jeffrey D.; Widom, Jennifer. *Database Systems: The Complete Book*. 2ª edição. Pearson Prentice Hall, 2008. Capítulos 15 e 16.
7. OpenJS Foundation. *Node.js 20 LTS Documentation: Process I/O & Synchronous Writes*. 2024. Disponível em: <https://nodejs.org/docs/latest-v20.x/api/process.html#a-note-on-process-io>. Acesso em: 10 nov. 2026.

## 9. Uso de IA

Usei IA para consultar documentações, organizar tarefas, auxiliar em scripts e atuar como revisora crítica — questionando hipóteses técnicas, apontando limitações metodológicas e sugerindo verificações adicionais (a configuração do CI foi manual). Nenhuma resposta foi tratada como evidência ou aceita sem validação: confrontei cada apontamento com o código e validei as decisões via 42 testes de contrato, análise de planos no EXPLAIN ANALYZE e medições empíricas com o k6.
