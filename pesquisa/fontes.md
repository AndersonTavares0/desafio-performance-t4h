# Levantamento Bibliográfico e Fontes Primárias

Registro das fontes primárias e acadêmicas consultadas para fundamentar as intervenções arquiteturais no desafio de performance (Tech for Humans 2026). Todas as fontes foram abertas, lidas e verificadas.

---

## 1. Fontes Primárias e Acadêmicas

### Fonte 1 (Primária — Banco de Dados)
- **Título:** PostgreSQL 16.4 Documentation: Chapter 11 — Indexes (11.2 Index Types; 11.7 Indexes on Expressions)
- **Autor/Instituição:** The PostgreSQL Global Development Group (2024)
- **Link:** https://www.postgresql.org/docs/16/indexes.html
- **Data de acesso:** 10/11/2026
- **O que a fonte afirma:**
  - Índices B-tree fornecem busca em complexidade logarítmica $O(\log N)$ para predicados de igualdade e intervalos.
  - O PostgreSQL não cria automaticamente índices em colunas de chave estrangeira (`REFERENCES`); sem eles, consultas que filtram por chaves estrangeiras executam varreduras sequenciais completas (`Seq Scan`).
  - Índices funcionais (em expressões, ex.: `lower(email)`) permitem que buscas com transformações não-sargáveis utilizem a estrutura em árvore em vez de aplicar a função a cada linha durante um Seq Scan.
- **Fato vs. Opinião:**
  - *Fato:* Mecanismo documentado oficialmente e verificado via `EXPLAIN (ANALYZE, BUFFERS)`.
  - *Opinião:* Não se aplica (documentação oficial do motor).

### Fonte 2 (Primária — Arquitetura de Conexões)
- **Título:** PostgreSQL 16.4 Documentation: Chapter 1.2 — Architectural Fundamentals
- **Autor/Instituição:** The PostgreSQL Global Development Group (2024)
- **Link:** https://www.postgresql.org/docs/16/tutorial-arch.html
- **Data de acesso:** 15/11/2026
- **O que a fonte afirma:**
  - O PostgreSQL usa modelo cliente/servidor: um processo servidor gerencia os arquivos e executa ações em nome dos clientes.
  - Para atender múltiplas conexões concorrentes, o servidor inicia ("forks") um novo processo para cada conexão; cliente e processo servidor passam a se comunicar sem intervenção do processo supervisor.
- **Fato vs. Opinião:**
  - *Fato:* Modelo de concorrência por processo descrito na documentação oficial.
  - *Opinião:* Não se aplica.

### Fonte 3 (Primária — Driver de Aplicação)
- **Título:** node-postgres Documentation: Connection Pooling
- **Autor/Instituição:** Brian Carlson / Comunidade open source (2024)
- **Link:** https://node-postgres.com/features/pooling
- **Data de acesso:** 10/11/2026
- **O que a fonte afirma:**
  - A classe `pg.Pool` gerencia um conjunto de instâncias `pg.Client` persistentes.
  - O uso de pool reaproveita o socket TCP e a sessão já autenticada no PostgreSQL, reduzindo o tempo de latência de cada query e evitando saturação de descritores de arquivo.
- **Fato vs. Opinião:**
  - *Fato:* Comportamento do pool em manter conexões quentes e despachar consultas via fila de espera.

### Fonte 4 (Acadêmica — Teoria de Bancos de Dados)
- **Título:** Modern B-Tree Techniques
- **Autor:** Goetz Graefe
- **Publicação:** Foundations and Trends in Databases, Vol. 3, No. 4, pp. 203–402 (2011)
- **DOI/Link:** https://doi.org/10.1561/1900000028
- **Data de acesso:** 10/11/2026
- **O que a fonte afirma:**
  - O custo de busca em árvores B escala com a profundidade da árvore ($O(\log_B N)$), onde $B$ é o fator de ramificação das páginas.
  - Em junções relacionais entre tabelas fato e dimensão, a ausência de índice secundário no lado dependente degenera o custo da operação para $O(N \cdot M)$ ou exige a criação de tabelas hash inteiras em memória intermediária.
- **Fato vs. Opinião:**
  - *Fato:* Teorema de complexidade assintótica e análise formal de acesso a blocos em meios persistentes.

### Fonte 5 (Acadêmica — Processamento e Otimização de Consultas)
- **Título:** Database Systems: The Complete Book (2nd Edition)
- **Autores:** Hector Garcia-Molina, Jeffrey D. Ullman, Jennifer Widom
- **Editora:** Pearson (2008), Capítulos 15 (Query Execution) e 16 (The Query Compiler)
- **Data de acesso:** 10/11/2026
- **O que a fonte afirma:**
  - A varredura sequencial completa consome $B$ transferências de bloco de disco para a memória principal. Em tabelas volumosas, varreduras concorrentes sobrecarregam a largura de banda de I/O e desalojam páginas úteis do cache compartilhado.
  - Índices seletivos reduzem o acesso estritamente aos blocos que contêm as tuplas qualificadas, tornando o custo quase independente do tamanho total da tabela.
  - O capítulo 16 trata da reescrita de consultas por leis algébricas, incluindo antecipar seleções no plano (§16.2.3 — *Pushing Selections*) e mover agregações (§16.2.7 — *Laws Involving Grouping and Aggregation*).
- **Fato vs. Opinião:**
  - *Fato:* Modelagem canônica de custo de planos de execução adotada por otimizadores modernos (inclusive o PostgreSQL). A divisão em seções foi conferida no sumário da 2ª edição.

### Fonte 6 (Primária — Runtime Node.js)
- **Título:** Node.js Documentation: The Node.js Event Loop
- **Autor/Instituição:** OpenJS Foundation (2024)
- **Link:** https://nodejs.org/en/learn/asynchronous-work/event-loop-timers-and-nexttick
- **Data de acesso:** 15/11/2026
- **O que a fonte afirma:**
  - O Event Loop permite ao Node.js executar I/O não bloqueante apesar de usar uma única thread JavaScript por padrão, delegando operações ao kernel.
  - Callbacks de longa duração atrasam as fases seguintes do Event Loop; trabalho pesado em JavaScript compete com o atendimento das requisições.
- **Fato vs. Opinião:**
  - *Fato:* Funcionamento documentado do Event Loop e da camada libuv.

### Fonte 7 (Primária — Agregação)
- **Título:** PostgreSQL 16.4 Documentation: Chapter 9.21 — Aggregate Functions
- **Autor/Instituição:** The PostgreSQL Global Development Group (2024)
- **Link:** https://www.postgresql.org/docs/16/functions-aggregate.html
- **Data de acesso:** 15/11/2026
- **O que a fonte afirma:**
  - Funções de agregação calculam um único resultado a partir de um conjunto de linhas de entrada (`count`, `sum`, entre outras).
  - Combinadas com `GROUP BY`, as agregações são calculadas por grupo, e apenas o resultado agregado é devolvido ao cliente.
- **Fato vs. Opinião:**
  - *Fato:* Comportamento documentado da linguagem SQL no PostgreSQL.
  - *Opinião:* Não se aplica.

### Fonte 8 (Primária — Caso de Mercado em Pooling)
- **Título:** PgBouncer Features
- **Autor/Instituição:** PgBouncer Project (2024)
- **Link:** https://www.pgbouncer.org/features.html
- **Data de acesso:** 15/11/2026
- **O que a fonte afirma:**
  - O PgBouncer é um pooler leve de conexões para PostgreSQL, usado como intermediário entre aplicação e banco.
  - Oferece três níveis de reúso: de sessão (conexão do servidor presa ao cliente enquanto ele está conectado), de transação (devolvida ao pool ao fim de cada transação) e de statement (só `autocommit`).
- **Fato vs. Opinião:**
  - *Fato:* Modos de pooling descritos na documentação oficial do projeto.
  - *Opinião:* Não se aplica.
