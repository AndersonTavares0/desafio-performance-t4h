# Otimização de Desempenho e Eficiência Computacional em Arquitetura Node.js e PostgreSQL: Um Estudo Empírico e Guiado por Hipóteses

**Autor:** Anderson Tavares (`anderson.g.tavares@gmail.com`)  
**Data:** 10 de novembro de 2026  
**Repositório do Projeto:** [AndersonTavares0/desafio-performance-t4h](https://github.com/AndersonTavares0/desafio-performance-t4h)

---

## 1. Introdução e Contexto

Em arquiteturas de microsserviços conteinerizadas sob restrições severas de hardware, a escalabilidade é frequentemente limitada por ineficiências no ciclo de vida de conexões e na indexação de dados. Este estudo investiga a otimização de uma aplicação de e-commerce representativa, composta por uma API em Node.js 20 (Express) e um banco relacional PostgreSQL 16.4. Os serviços operam sob cotas rígidas via Docker Compose: 0,5 CPU e 256 MiB para a API, e 1,0 CPU e 512 MiB para o banco. A base de dados sintética contém 100.000 clientes, 20.000 produtos, 500.000 pedidos e 1.500.000 itens de pedido.

O objetivo consiste em maximizar a vazão (requisições por segundo) e minimizar a latência (mediana e p95) sob carga de 20 usuários virtuais durante 60 segundos de medição formal, preservando rigorosamente o contrato de respostas da API verificado por 42 casos de teste automatizados.

---

## 2. Diagnóstico dos Gargalos

Três baterias de testes na aplicação original ([20261110-095041-00-linha-de-base](../resultados/20261110-095041-00-linha-de-base/), [20261110-095428-00-linha-de-base](../resultados/20261110-095428-00-linha-de-base/) e [20261110-095605-00-linha-de-base](../resultados/20261110-095605-00-linha-de-base/)) registraram medianas de 3,62 req/s, latência mediana de 1.248,0 ms e p95 de 17.932,0 ms. A CPU do banco saturou em 97,1%, enquanto a da API manteve-se em 5,0%, evidenciando gargalo concentrado no SGBD.

Investigações estruturadas (salvas em [diagnostico/](../diagnostico/)) revelaram três causas críticas:
1. **Conexões Efêmeras sem Pooling:** `api/src/db.js` criava um `new pg.Client()` por consulta. Como o PostgreSQL adota modelo baseado em processos via `fork()`, o ciclo contínuo de handshake TCP, autenticação e criação de processos consumia excessivamente o escalonador do SO ([02-conexao-e-pooling.txt](../diagnostico/02-conexao-e-pooling.txt)), atingindo até 30 forks por requisição em `/clientes/:id/pedidos`.
2. **Varreduras Sequenciais em Chaves Estrangeiras:** O `EXPLAIN (ANALYZE, BUFFERS)` revelou ausência de índices secundários nas colunas de relacionamento ([01-explain-queries-linha-de-base.txt](../diagnostico/01-explain-queries-linha-de-base.txt)). A filtragem por `pedidos.cliente_id` varria 500.000 tuplas (`Seq Scan`), e a busca por `itens_pedido.pedido_id` varria 1.500.000 tuplas, elevando a rota `/clientes/:id/pedidos` a 11.744 ms de latência.
3. **Agregação em Memória na Aplicação:** A rota `/relatorios/vendas-por-dia` transferia dezenas de milhares de registros completos para o Node.js agrupar e somar valores com instâncias de `Map` em JavaScript, onerando o Event Loop e gerando pico de consumo de memória.

---

## 3. Fundamentação e Hipóteses

As causas foram modeladas à luz da literatura de bancos de dados e sistemas distribuídos:

- **Hipótese 1 (Reuso de Conexões):** A introdução de um pool estático de conexões persistentes elimina handshakes TCP e invocações de `fork()` no PostgreSQL. *Fundamentação:* Documentação do PostgreSQL 16 (Cap. 20) e do `node-postgres`. *Critério de Refutação:* Caso a vazão não apresente aumento superior ao ruído experimental (CV > 15%), a hipótese é refutada.
- **Hipótese 2 (Indexação B-Tree de Chaves Estrangeiras):** O PostgreSQL não indexa automaticamente restrições `REFERENCES`. Índices B-tree compostos reduzem o custo de busca de $O(N)$ para $O(\log N)$, eliminando leituras de blocos não-pertinentes. *Fundamentação:* Graefe (2011), Garcia-Molina et al. (2008) e documentação do PostgreSQL 16 (Cap. 11). *Critério de Refutação:* Se o otimizador mantiver `Seq Scan` nas junções de pedidos e itens, a hipótese é refutada.
- **Hipótese 3 (Pushdown de Agregação Relacional):** Delegar agrupamentos e somatórios (`GROUP BY`, `SUM`, `COUNT`) diretamente ao motor SQL reduz o payload de rede de megabytes para dezenas de bytes, aliviando a CPU e memória da API. *Fundamentação:* Garcia-Molina et al. (2008) e documentação de agregadores do PostgreSQL (Cap. 9). *Critério de Refutação:* Se a memória e CPU da API não reduzirem na rota analítica, o pushdown é inócuo.

---

## 4. Soluções Implementadas

As intervenções foram aplicadas incrementalmente com commits atômicos:

1. **Intervenção 01 (Connection Pooling):** Em `api/src/db.js`, substituiu-se `new Client()` por uma instância de `pg.Pool({ max: 20 })`, dimensionada para acomodar a concorrência alvo dos 20 usuários simultâneos.
2. **Intervenção 02 (Índices B-Tree Estratégicos):** Em `banco/03-indices.sql`, foram definidos 6 índices B-tree:
   - `idx_pedidos_cliente_criado_em` em `pedidos (cliente_id, criado_em DESC, id DESC)`;
   - `idx_itens_pedido_pedido_id_id` em `itens_pedido (pedido_id, id)`;
   - `idx_itens_pedido_produto_id` em `itens_pedido (produto_id)`;
   - `idx_clientes_lower_email` funcional em `clientes (lower(email))`;
   - `idx_pedidos_status_criado_em` em `pedidos (status, criado_em DESC, id DESC)`;
   - `idx_pedidos_criado_em_date` parcial em `pedidos ((criado_em::date)) WHERE status <> 'cancelado'`.  
   O banco foi reiniciado com `docker compose down -v && docker compose up -d` para reconstrução limpa dos esquemas.
3. **Intervenção 03 (Pushdown SQL em Vendas por Dia):** Em `api/src/rotas.js`, substituiu-se o processamento in-memory por consulta analítica com agregação nativa no PostgreSQL (`to_char`, `count(DISTINCT p.id)`, `sum(quantidade)`, `sum(quantidade * preco_unitario_centavos)`), mapeando resultados com `Number(...)` para atender à tipagem exata do contrato.

---

## 5. Resultados e Comparação Quantitativa

Cada estado do sistema foi medido em triplicata sob condições ambientais estáveis. As medianas consolidadas são apresentadas a seguir:

| Intervenção | Vazão (req/s) | $\Delta$ vs. Base | Latência Mediana | Latência p95 | CPU Banco | CPU API | RAM API | Contrato |
|---|---|---|---|---|---|---|---|---|
| **00. Linha de Base** | 3,62 | — | 1.248,0 ms | 17.932,0 ms | 97,1% | 5,0% | 23,2 MiB | 42/42 |
| **01. Connection Pool** | 4,81 | +32,9% | 802,0 ms | 13.320,5 ms | 96,3% | 4,9% | 24,1 MiB | 42/42 |
| **02. Índices B-Tree** | 28,23 | +679,8% | 82,1 ms | 4.408,9 ms | 86,9% | 20,9% | 58,1 MiB | 42/42 |
| **03. Pushdown SQL** | 29,02 | +701,7% | 26,5 ms | 4.428,0 ms | 89,1% | 3,1% | 26,4 MiB | 42/42 |

*Fontes dos dados:* Rodadas de resultados arquivadas em [00-linha-de-base](../resultados/20261110-095041-00-linha-de-base/), [01-connection-pool](../resultados/20261110-100637-01-connection-pool/), [02-indices-banco](../resultados/20261110-101549-02-indices-banco/) e [03-pushdown-agregacao](../resultados/20261110-102601-03-pushdown-agregacao/).

### Impacto nas Rotas Críticas
- **`/clientes/:id/pedidos`:** A latência mediana caiu de 11.744,0 ms na linha de base para 66,9 ms após a indexação (redução de 99,4%), demonstrando a eficácia da conversão de Seq Scan para Index Scan.
- **`/clientes/:id`:** O pooling reduziu a latência de 297,1 ms para 5,6 ms, comprovando a remoção do gargalo de conexão.
- **`/relatorios/vendas-por-dia`:** O pushdown SQL descarregou o Node.js: a CPU da API recuou de 20,9% para 3,1% (-85,2%) e a memória média caiu de 58,1 MiB para 26,4 MiB.
- **Preservação de Contrato:** Todas as medições atestaram conformidade estrita (42/42 respostas idênticas).

---

## 6. Análise de Custos e Trade-offs

A otimização gerou um salto de vazão de 8x (de 3,62 para 29,02 req/s) mantendo intactas as cotas orçamentárias de infraestrutura (0,5 CPU / 256 MiB na API e 1,0 CPU / 512 MiB no banco). Os 6 índices secundários demandaram aproximadamente 62 MiB adicionais de armazenamento e memória de buffers no PostgreSQL, um acréscimo insignificante face ao tamanho total da base (780 MB). Embora índices introduzam sobrecusto em operações de inserção e atualização, o ganho em cargas com predominância de leitura justifica amplamente o compromisso de espaço.

---

## 7. Ameaças à Validade e Limites

Para manter o rigor metodológico, registram-se os limites deste estudo:
1. **Condições do Host:** O ambiente de testes utilizou um host Linux de múltiplos núcleos físicos. Embora os limites de CPU e memória tenham sido impostos pelos cgroups do Docker, variações de I/O em discos mecânicos ou instâncias de nuvem com créditos de bursting podem divergir dos resultados locais.
2. **Modelo de Carga Sintético:** O k6 utilizou 20 usuários virtuais em loop fechado sem tempo de reflexão (`think time`). Em ambientes produtivos reais, pausas entre requisições alteram as dinâmicas de enfileiramento.
3. **Ausência de Escritas Concorrentes:** O benchmark avalia predominantemente rotas de consulta. Sob transações massivas de escrita simultânea, a sobrecarga de atualização dos índices B-tree deve ser mensurada.

---

## 8. Próximos Passos

Apoiando-se no catálogo de alternativas de [proximos-testes.md](../proximos-testes.md), destacam-se três frentes futuras:
1. **Índice Trigrama (`pg_trgm`) em Produtos:** Substituir o `ILIKE '%termo%'` na rota `/produtos/busca` por índice GIN trigrama, eliminando a varredura sequencial em 20.000 produtos.
2. **Cache com Invalidação Temporal:** Empregar camada de cache em memória (ex.: Redis) com TTL de 60 segundos na rota `/relatorios/top-produtos` para amortizar ordenações pesadas de 1,5 milhão de itens.
3. **Sintonia de Parâmetros do PostgreSQL:** Ajustar `shared_buffers = 128MB` e `work_mem = 16MB` no `postgresql.conf` para otimizar alocação nos 512 MiB dedicados ao SGBD.

---

## 9. Declaração Factual de Uso de IA

Ferramentas de inteligência artificial baseadas em modelos de linguagem foram utilizadas exclusivamente como suporte para pesquisa sintática de documentações oficiais, formatação tabular e revisão gramatical do texto. Todos os diagnósticos de causa-raiz, formulações de hipóteses, implementações de código SQL e JavaScript, execuções de testes no terminal e compilações numéricas foram integralmente projetados, conduzidos e validados pelo autor.

---

## 10. Referências Bibliográficas

1. **The PostgreSQL Global Development Group.** *PostgreSQL 16.4 Documentation: Chapter 11 — Indexes*. 2024. Disponível em: <https://www.postgresql.org/docs/16/indexes.html>. Acesso em: 10 nov. 2026.
2. **The PostgreSQL Global Development Group.** *PostgreSQL 16.4 Documentation: Chapter 20 — Server Configuration: Connections and Authentication*. 2024. Disponível em: <https://www.postgresql.org/docs/16/runtime-config-connection.html>. Acesso em: 10 nov. 2026.
3. **The PostgreSQL Global Development Group.** *PostgreSQL 16.4 Documentation: Chapter 9.21 — Aggregate Functions*. 2024. Disponível em: <https://www.postgresql.org/docs/16/functions-aggregate.html>. Acesso em: 10 nov. 2026.
4. **Carlson, Brian; Comunidade node-postgres.** *node-postgres Documentation: Connection Pooling*. 2024. Disponível em: <https://node-postgres.com/features/pooling>. Acesso em: 10 nov. 2026.
5. **Graefe, Goetz.** *Modern B-Tree Techniques*. Foundations and Trends in Databases, Vol. 3, No. 4, pp. 203–402, 2011. DOI: <https://doi.org/10.1561/1900000028>.
6. **Garcia-Molina, Hector; Ullman, Jeffrey D.; Widom, Jennifer.** *Database Systems: The Complete Book*. 2ª edição. Pearson Prentice Hall, 2008. Capítulos 15 (Query Execution) e 16 (The Query Compiler).
7. **OpenJS Foundation.** *Node.js 20 LTS Documentation: Process I/O & Synchronous Writes*. 2024. Disponível em: <https://nodejs.org/docs/latest-v20.x/api/process.html#a-note-on-process-io>. Acesso em: 10 nov. 2026.
