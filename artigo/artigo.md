# Otimização de Performance em Node.js e PostgreSQL: Maximizando Vazão em 8x com Recursos Computacionais Inalterados

**Autor:** Anderson Tavares (`anderson.g.tavares@gmail.com`)  
**Data:** 10 de novembro de 2026  
**Repositório do Projeto:** [AndersonTavares0/desafio-performance-t4h](https://github.com/AndersonTavares0/desafio-performance-t4h)

## 1. Resumo

Uma API em Node.js e PostgreSQL operava sob lentidão severa com 20 usuários virtuais, atingindo 3,62 req/s, p95 de 17,9 s e saturação de 97,1% da CPU do banco. Identificou-se sobrecarga de conexões sem pool, ausência de índices em chaves estrangeiras e transferência massiva de dados para agregação no Node.js. Implementou-se pool de conexões (`pg.Pool`), 6 índices B-tree estratégicos e pushdown de agregação SQL. A vazão subiu 8x (29,02 req/s) e a latência mediana caiu de 1.248 ms para 26,5 ms (-97,9%), com custo zero de infraestrutura e contrato 100% preservado.

## 2. Contexto e diagnóstico

A aplicação opera em dois containers Docker limitados a 0,5 CPU e 256 MiB (API Node.js 20) e 1,0 CPU e 512 MiB (PostgreSQL 16), com base sintética de 100 mil clientes, 20 mil produtos, 500 mil pedidos e 1,5 milhão de itens. Na linha de base ([20261110-095041-00-linha-de-base](../resultados/20261110-095041-00-linha-de-base/)), o sistema registrou 3,62 req/s e p95 de 17.932,0 ms, com CPU do banco em 97,1% e API em 5,0%.

Inspeções salvas em [diagnostico/](../diagnostico/) identificaram três causas-raiz:
1. **Conexões Efêmeras:** `api/src/db.js` criava um `new pg.Client()` por query. Como o PostgreSQL adota processos via `fork()`, o ciclo contínuo de handshakes gerou contenção de CPU no SO ([02-conexao-e-pooling.txt](../diagnostico/02-conexao-e-pooling.txt)), atingindo até 30 forks por requisição em `/clientes/:id/pedidos`.
2. **Varreduras Sequenciais em Chaves Estrangeiras:** O `EXPLAIN (ANALYZE, BUFFERS)` revelou ausência de índices secundários ([01-explain-queries-linha-de-base.txt](../diagnostico/01-explain-queries-linha-de-base.txt)). Buscas por `cliente_id` liam 500 mil pedidos e 1,5 milhão de itens via `Seq Scan`, elevando a rota `/clientes/:id/pedidos` a 15.252,4 ms.
3. **Agregação In-Memory no Node.js:** A rota `/relatorios/vendas-por-dia` transferia milhares de tuplas para o Node.js agrupar com `Map`, gerando sobrecarga de memória e processamento.

Hipótese 1: Conexões efêmeras saturam a CPU do banco por criação contínua de processos via `fork()`.  
Hipótese 2: A ausência de índices em chaves estrangeiras força varreduras completas em milhões de linhas a cada junção.  
Hipótese 3: Transferir dados analíticos brutos sobrecarrega a rede e a memória do runtime Node.js.

## 3. Estado da arte

### Pooling de Conexões em Arquiteturas Baseadas em Processos
O PostgreSQL aloca um processo dedicado por sessão via `fork()`. A documentação oficial (Cap. 20) e a do `node-postgres` explicam que clientes efêmeros acarretam alocação de sockets, autenticação e catálogos locais a cada requisição. O Connection Pooling preserva conexões abertas para atender consultas em fila, reduzindo latência e consumo de descritores de arquivo.

### Indexação B-Tree em Relacionamentos e Expressões
Graefe (2011) demonstra que o acesso por árvore B tem custo O(log N), contra O(N) da varredura sequencial. Garcia-Molina et al. (2008) destacam que consultas sem índices secundários forçam varreduras completas ou tabelas hash volumosas. A documentação do PostgreSQL 16 (Cap. 11) adverte que restrições `REFERENCES` não são indexadas automaticamente. Ademais, para filtros case-insensitive (`lower(email)`), índices funcionais viabilizam busca indexada direta.

### Pushdown de Agregação e Eficiência de I/O
O princípio de pushdown computation estabelece que agregações devem ocorrer no motor de armazenamento (Garcia-Molina et al., 2008). O PostgreSQL possui funções nativas (`COUNT`, `SUM`, `GROUP BY`) vetorizadas em C (Cap. 9.21). Agregar no banco comprime dezenas de milhares de registros em poucas linhas, reduzindo tráfego de rede e liberando o Event Loop do Node.js (Node.js LTS Docs).

## 4. Alternativas consideradas

Para selecionar intervenções de maior impacto e menor risco, avaliou-se a matriz registrada em [pesquisa/alternativas-e-escolha.md](../pesquisa/alternativas-e-escolha.md):

| Alternativa | Custo | Desempenho | Risco | Esforço |
|---|---|---|---|---|
| A. Connection Pooling (`pg.Pool`) | Zero (sem dependências novas) | Alto alívio de CPU e queda de latência | Nulo (não altera consultas) | Baixo (5 linhas em `db.js`) |
| B. Índices B-Tree Estratégicos | Baixo (~62 MiB de disco/RAM) | Crítico (elimina gargalo de 99% da latência) | Muito baixo (preserva esquema) | Baixo (DDL em `03-indices.sql`) |
| C. Pushdown de Agregação SQL | Zero | Redução de tráfego de rede e consumo de RAM | Baixo (exige tipagem exata) | Médio (reestruturação de query) |
| D. Cache em Memória (Redis) | Médio (container adicional e RAM) | Alto para rotas analíticas repetidas | Médio (invalidação de dados) | Alto (gestão de ciclo de vida) |
| E. Índice Trigrama GIN (`pg_trgm`) | Médio (extensão C e índice pesado) | Alto em buscas textuais com `ILIKE` | Baixo | Médio (extensão do PostgreSQL) |

As alternativas A, B e C foram selecionadas por atacarem as causas-raiz a custo zero. A alternativa D (Redis) foi descartada por exigir novo container antes de esgotar as otimizações nativas. A alternativa E (`pg_trgm`) foi postergada por focar em rota de 15% do tráfego, enquanto as chaves estrangeiras cobriam 70% da carga. Ambas constam em [proximos-testes.md](../proximos-testes.md).

## 5. Solução escolhida e por quê

A intervenção foi conduzida em três etapas atômicas:
1. **Connection Pooling no Driver:** Substituição de `new Client()` por `new Pool({ max: 20 })` em `api/src/db.js`. O dimensionamento para 20 conexões reflete a concorrência dos 20 usuários virtuais do teste, eliminando o custo de `fork()` sem saturar a memória do banco.
2. **Índices B-Tree Estratégicos:** Criação de `banco/03-indices.sql` contendo 6 índices B-tree cobrindo chaves estrangeiras (`pedidos.cliente_id`, `itens_pedido.pedido_id`), índice funcional (`lower(email)`), ordenação paginada (`status, criado_em DESC`) e índice temporal. Transforma o custo de junções de varreduras lineares para buscas logarítmicas instantâneas.
3. **Pushdown SQL em Vendas por Dia:** Reescrever `/relatorios/vendas-por-dia` em `api/src/rotas.js` delegando `GROUP BY`, `SUM` e `COUNT` ao PostgreSQL, mapeando com `Number(...)` para garantir o contrato. Descartou-se manter a agregação em memória no JavaScript para eliminar desperdício de CPU e RAM no Node.js.

## 6. Experimento e resultado

Cada mudança seguiu o protocolo oficial (3 baterias de 60s com 20 VUs, calculando a mediana):

| Mudança | Hipótese | p95 antes → depois | req/s antes → depois | CPU/memória | Pastas de resultados | Conclusão |
|---|---|---|---|---|---|---|
| **01-connection-pool** | Reutilizar conexões elimina sobrecarga de forks | 17.932 ms → 13.321 ms (-25,7%) | 3,62 → 4,81 (+32,9%) | Banco: 97,1% → 96,3%<br>API: 5,0% → 4,9% (RAM: 40,8 MiB) | [01-connection-pool](../resultados/20261110-100637-01-connection-pool/) | Vazão aumentou 32,9% e a rota simples `/clientes/:id` caiu de 296,9 ms para 88,1 ms. Banco seguiu saturado por falta de índices. |
| **02-indices-banco** | Índices em chaves estrangeiras eliminam Seq Scans | 13.321 ms → 4.409 ms (-66,9%) | 4,81 → 28,23 (+486,9%) | Banco: 96,3% → 86,9%<br>API: 4,9% → 20,9% (RAM: 58,3 MiB) | [02-indices-banco](../resultados/20261110-101549-02-indices-banco/) | Salto de quase 6x na vazão. A rota `/clientes/:id/pedidos` caiu de 15.252 ms para 115 ms (>100x mais rápida). Contrato 42/42. |
| **03-pushdown-agregacao** | Agregar no banco reduz tráfego e uso de CPU/RAM na API | 4.409 ms → 4.428 ms (estável) | 28,23 → 29,02 (+2,8%) | Banco: 86,9% → 89,1%<br>API: 20,9% → 3,1% (RAM: 26,4 MiB) | [03-pushdown-agregacao](../resultados/20261110-102601-03-pushdown-agregacao/) | Latência mediana global caiu para 26,5 ms. A CPU da API recuou 85,2% e a RAM caiu pela metade. Contrato 42/42 mantido. |

O resultado consolidado final alcançou **29,02 req/s** (**+701,7%** vs. base de 3,62 req/s) e latência mediana de **26,5 ms** (contra 1.248,0 ms na base), preservando rigorosamente todas as 42 respostas da aplicação original.

![p95 antes e depois de cada mudança](img/p95-por-mudanca.png)

## 7. Limites e testes futuros

A solução apresenta os seguintes limites operacionais e considerações metodológicas:
1. **Sobrecarga em Escritas:** Os 6 índices B-tree ocupam ~62 MiB e introduzem manutenção de páginas em `INSERT`/`UPDATE`. Sob tráfego com predominância de escritas, esse trade-off deve ser reavaliado.
2. **Busca Textual sem Índice:** A rota `/produtos/busca` ainda utiliza `ILIKE '%termo%'`, exigindo varredura sequencial em 20 mil produtos.
3. **Amostragem Estatística:** Adotou-se rigorosamente a amostra de 3 baterias (n=3) conforme estipulado pelo protocolo do desafio. Em ambientes de produção com ruído de rede, recomenda-se estender a amostragem para n >= 5, calculando o Coeficiente de Variação (CV < 5%) e Intervalo de Confiança a 95% (IC 95%) para descartar variações do escalonador.

**O que refutaria a conclusão:**  
Nossa conclusão seria refutada se uma carga mista com alta concorrência de escritas gerasse contenção severa de locks nas árvores B, ou se o catálogo de produtos crescesse em ordens de grandeza tornando o `ILIKE` o gargalo dominante.

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

Usei IA como acelerador operacional para rascunhar variações de queries analíticas de pushdown em SQL, agilizar consultas na documentação técnica do PostgreSQL e estruturar scripts auxiliares de automação (CI e geração de gráficos). Todas as intervenções foram validadas sob três barreiras: checagem estrita de contrato (42/42 casos idênticos ao baseline), auditoria dos planos de execução via EXPLAIN ANALYZE no psql e três baterias empíricas de carga pelo k6.
