# Otimização de Performance em Node.js e PostgreSQL: Maximizando Vazão em 8x com Recursos Computacionais Inalterados

**Autor:** Anderson Tavares (`anderson.g.tavares@gmail.com`)  
**Data:** 10 de novembro de 2026  
**Repositório do Projeto:** [AndersonTavares0/desafio-performance-t4h](https://github.com/AndersonTavares0/desafio-performance-t4h)

## 1. Resumo

Uma API em Node.js e PostgreSQL sofria com lentidão sob 20 usuários virtuais: 3,62 req/s, p95 de 17,9 s e saturação de 97,1% da CPU do banco. O diagnóstico revelou conexões sem pool, ausência de índices em chaves estrangeiras e transferência de dados brutos para agregação no Node.js. Aplicou-se connection pool (`pg.Pool`), 6 índices B-tree estratégicos e pushdown de agregação SQL. A vazão subiu 8x (29,02 req/s) e a latência mediana caiu de 1.248 ms para 26,5 ms (-97,9%), a custo zero de infraestrutura e com contrato 100% preservado.

## 2. Contexto e diagnóstico

A aplicação opera em dois containers Docker limitados a 0,5 CPU e 256 MiB (API Node.js 20) e 1,0 CPU e 512 MiB (PostgreSQL 16), com base sintética de 100 mil clientes, 20 mil produtos, 500 mil pedidos e 1,5 milhão de itens. Na linha de base ([20261110-095041-00-linha-de-base](../resultados/20261110-095041-00-linha-de-base/)), o sistema registrou 3,62 req/s e p95 de 17.932,0 ms, com CPU do banco em 97,1% e API em 5,0%.

Inspeções salvas em [diagnostico/](../diagnostico/) revelaram três problemas:
1. **Conexões Efêmeras:** `api/src/db.js` criava `new pg.Client()` por consulta. No PostgreSQL (baseado em processos via `fork`), o ciclo repetido de autenticação gerou sobrecarga no SO ([02-conexao-e-pooling.txt](../diagnostico/02-conexao-e-pooling.txt)), atingindo até 30 forks por requisição em `/clientes/:id/pedidos`.
2. **Varreduras Sequenciais:** O `EXPLAIN (ANALYZE, BUFFERS)` revelou ausência de índices secundários ([01-explain-queries-linha-de-base.txt](../diagnostico/01-explain-queries-linha-de-base.txt)). Buscas por `cliente_id` liam 500 mil pedidos e 1,5 milhão de itens via `Seq Scan`, elevando a rota `/clientes/:id/pedidos` a 15.252,4 ms.
3. **Agregação In-Memory:** `/relatorios/vendas-por-dia` transferia milhares de tuplas para o Node.js agrupar com `Map`, sobrecarregando o Event Loop.

Hipóteses de causa:
- *Hipótese 1:* Conexões efêmeras saturam a CPU do banco pelo custo contínuo de `fork()`.
- *Hipótese 2:* A ausência de índices força varreduras completas em milhões de linhas a cada junção.
- *Hipótese 3:* Transferir dados brutos para agregação em memória sobrecarrega a rede e a CPU da API.

## 3. Estado da arte

### Pooling de Conexões em Arquiteturas Baseadas em Processos
O PostgreSQL aloca um processo dedicado por sessão via `fork()`. A documentação oficial (Cap. 20) e a do `node-postgres` explicam que clientes efêmeros acarretam alocação de sockets, autenticação e catálogos locais a cada requisição. O Connection Pooling preserva conexões abertas para atender consultas em fila, reduzindo latência e consumo de descritores de arquivo.

### Indexação B-Tree em Relacionamentos e Expressões
Graefe (2011) demonstra que a árvore B tem custo O(log N), contra O(N) da varredura sequencial. Garcia-Molina et al. (2008) destacam que consultas sem índices secundários forçam varreduras completas. A documentação do PostgreSQL 16 (Cap. 11) adverte que chaves `REFERENCES` não são indexadas automaticamente, e que filtros case-insensitive (`lower(email)`) demandam índices funcionais.

### Pushdown de Agregação e Eficiência de I/O
O princípio de pushdown computation estabelece que agregações devem ocorrer no motor de dados (Garcia-Molina et al., 2008). O PostgreSQL possui funções nativas (`COUNT`, `SUM`, `GROUP BY`) vetorizadas em C (Cap. 9.21). Agregar no banco comprime dezenas de milhares de registros em poucas tuplas, reduzindo tráfego de rede e liberando o Event Loop da API (Node.js LTS Docs).

## 4. Alternativas consideradas

Para selecionar intervenções de maior impacto e menor risco, avaliou-se a matriz registrada em [pesquisa/alternativas-e-escolha.md](../pesquisa/alternativas-e-escolha.md):

| Alternativa | Custo | Desempenho | Risco | Esforço |
|---|---|---|---|---|
| A. Connection Pooling (`pg.Pool`) | Zero (sem dependências novas) | Alto alívio de CPU e queda de latência | Nulo (não altera consultas) | Baixo (5 linhas em `db.js`) |
| B. Índices B-Tree Estratégicos | Baixo (~62 MiB de disco/RAM) | Crítico (elimina gargalo de 99% da latência) | Muito baixo (preserva esquema) | Baixo (DDL em `03-indices.sql`) |
| C. Pushdown de Agregação SQL | Zero | Redução de tráfego de rede e consumo de RAM | Baixo (exige tipagem exata) | Médio (reestruturação de query) |
| D. Cache em Memória (Redis) | Médio (container adicional e RAM) | Alto para rotas analíticas repetidas | Médio (invalidação de dados) | Alto (gestão de ciclo de vida) |
| E. Índice Trigrama GIN (`pg_trgm`) | Médio (extensão C e índice pesado) | Alto em buscas textuais com `ILIKE` | Baixo | Médio (extensão do PostgreSQL) |

As alternativas A, B e C foram selecionadas por atacarem as causas-raiz a custo zero e sem novos serviços. A alternativa D (Redis) foi descartada por adicionar complexidade de infraestrutura antes de esgotar os recursos nativos. A alternativa E (`pg_trgm`) foi postergada por focar em rota de 15% do tráfego, enquanto as chaves estrangeiras cobriam 70% da carga. Ambas constam em [proximos-testes.md](../proximos-testes.md).

## 5. Solução escolhida e por quê

A intervenção foi conduzida em três etapas atômicas:
1. **Connection Pooling no Driver:** Adoção de `new Pool({ max: 20 })` em `api/src/db.js`, refletindo a concorrência de 20 VUs e eliminando o custo de `fork()` sem saturar a memória do banco.
2. **Índices B-Tree Estratégicos:** Criação de `banco/03-indices.sql` com 6 índices cobrindo chaves estrangeiras (`pedidos.cliente_id`, `itens_pedido.pedido_id`), busca funcional (`lower(email)`), paginação (`status, criado_em DESC`) e intervalo temporal. Transforma o custo de junções de varreduras lineares para buscas logarítmicas.
3. **Pushdown SQL em Vendas por Dia:** Reescrever `/relatorios/vendas-por-dia` em `api/src/rotas.js` delegando `GROUP BY`, `SUM` e `COUNT` ao PostgreSQL, mapeando com `Number(...)` para garantir o contrato. Descartou-se agregar no JavaScript para eliminar desperdício de CPU e RAM na API.

## 6. Experimento e resultado

Cada mudança seguiu o protocolo oficial (3 baterias de 60s com 20 VUs, calculando a mediana):

| Mudança | Hipótese | p95 antes → depois | req/s antes → depois | CPU/memória | Pastas de resultados | Conclusão |
|---|---|---|---|---|---|---|
| **01-connection-pool** | Reutilizar conexões elimina sobrecarga de forks | 17.932 ms → 13.321 ms (-25,7%) | 3,62 → 4,81 (+32,9%) | Banco: 97,1% → 96,3%<br>API: 5,0% → 4,9% (RAM: 40,8 MiB) | [01-connection-pool](../resultados/20261110-100637-01-connection-pool/) | Vazão aumentou 32,9% e `/clientes/:id` caiu para 88,1 ms. Banco continuou saturado por falta de índices. |
| **02-indices-banco** | Índices em chaves estrangeiras eliminam Seq Scans | 13.321 ms → 4.409 ms (-66,9%) | 4,81 → 28,23 (+486,9%) | Banco: 96,3% → 86,9%<br>API: 4,9% → 20,9% (RAM: 58,3 MiB) | [02-indices-banco](../resultados/20261110-101549-02-indices-banco/) | Salto de 6x na vazão. A rota `/clientes/:id/pedidos` caiu de 15.252 ms para 115 ms (>100x mais rápida). Contrato 42/42. |
| **03-pushdown-agregacao** | Agregar no banco reduz tráfego e uso de CPU/RAM na API | 4.409 ms → 4.428 ms (estável) | 28,23 → 29,02 (+2,8%) | Banco: 86,9% → 89,1%<br>API: 20,9% → 3,1% (RAM: 26,4 MiB) | [03-pushdown-agregacao](../resultados/20261110-102601-03-pushdown-agregacao/) | Latência mediana caiu para 26,5 ms. A CPU da API recuou 85,2% e a RAM caiu pela metade. Contrato 42/42. |

O resultado consolidado final alcançou **29,02 req/s** (**+701,7%** vs. base de 3,62 req/s) e latência mediana de **26,5 ms** (contra 1.248,0 ms na base), preservando todas as 42 respostas da aplicação original.

**O que não funcionou e limitações dos ganhos:**  
O pool de conexões isolado não aliviou a CPU do banco (recuo sutil de 97,1% para 96,3%), pois não resolve varreduras sequenciais. Já o pushdown SQL não reduziu o p95 global (manteve-se em ~4,4 s), pois a cauda de latência continuou governada pelas consultas com paginação profunda via OFFSET em `/pedidos` (páginas até 1.000 com p95 de ~10 s) e pelo somatório de 1,5 milhão de itens em `/relatorios/top-produtos` (~4,7 s). Isso comprova que pushdown em `vendas-por-dia` desonera o runtime da API, mas não resolve gargalos de paginação por offset nem de agregação global sem amortização de cache.

![p95 antes e depois de cada mudança](img/p95-por-mudanca.png)

## 7. Limites e testes futuros

A solução apresenta os seguintes limites e considerações metodológicas:
1. **Sobrecarga em Escrita:** Os 6 índices ocupam ~62 MiB e geram manutenção de páginas em `INSERT`/`UPDATE`, exigindo reavaliação sob cargas com predominância de escrita.
2. **Busca Textual sem Índice:** A rota `/produtos/busca` ainda utiliza `ILIKE '%termo%'`, exigindo varredura sequencial em 20 mil produtos.
3. **Amostragem Estatística:** Seguiu-se o protocolo de 3 baterias (n=3) do desafio. Em produção com ruído de rede, recomenda-se n >= 5, calculando Coeficiente de Variação (CV < 5%) e Intervalo de Confiança a 95% (IC 95%).

**O que refutaria a conclusão:**  
Nossa conclusão seria refutada se uma carga mista gerasse contenção severa de locks nas árvores B, ou se o catálogo crescesse tornando o `ILIKE` o gargalo dominante.

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

Usei IA como apoio para explorar alternativas de consultas SQL, consultar documentações técnicas, organizar o trabalho e auxiliar na criação de scripts. Revisei as sugestões e validei as mudanças sob três barreiras: 42 testes de contrato garantindo conformidade total da API, EXPLAIN ANALYZE no PostgreSQL para auditar os planos de consulta e baterias de teste de carga com o k6 para comparar o desempenho antes e depois de cada intervenção.
