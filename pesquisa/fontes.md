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
  - *Fato:* Mecanismo de plano de execução demonstrado no código-fonte e verificado via `EXPLAIN (ANALYZE, BUFFERS)`.
  - *Opinião:* Não se aplica (documentação oficial do motor).

### Fonte 2 (Primária — Arquitetura de Conexões)
- **Título:** PostgreSQL 16.4 Documentation: Chapter 20 — Server Configuration: Connections and Authentication
- **Autor/Instituição:** The PostgreSQL Global Development Group (2024)
- **Link:** https://www.postgresql.org/docs/16/runtime-config-connection.html
- **Data de acesso:** 10/11/2026
- **O que a fonte afirma:**
  - O PostgreSQL utiliza arquitetura baseada em processos (um processo dedicado para cada conexão cliente).
  - O estabelecimento de nova conexão exige `fork()` no sistema operacional, autenticação, inicialização de catálogo e alocação de buffers de sessão.
  - Conexões abertas e fechadas por consulta unitária geram contenção massiva de CPU e do escalonador do SO.
- **Fato vs. Opinião:**
  - *Fato:* Modelo de concorrência por processo comprovado na arquitetura do PostgreSQL.
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
- **Fato vs. Opinião:**
  - *Fato:* Modelagem canônica de custo de planos de execução adotada por otimizadores modernos (inclusive o PostgreSQL).

### Fonte 6 (Primária — Runtime Node.js)
- **Título:** Node.js 20 LTS Documentation: Process I/O & Synchronous Writes
- **Autor/Instituição:** OpenJS Foundation (2024)
- **Link:** https://nodejs.org/docs/latest-v20.x/api/process.html#a-note-on-process-io
- **Data de acesso:** 10/11/2026
- **O que a fonte afirma:**
  - No Node.js em sistemas POSIX, gravações em `stdout` e `stderr` através de `console.log` tornam-se síncronas quando a saída está conectada a arquivos ou pipes.
  - Gravações síncronas bloqueiam o Event Loop da aplicação até que os dados sejam aceitos pelo descritor de arquivo.
- **Fato vs. Opinião:**
  - *Fato:* Implementação documentada da camada libuv/C++ que gerencia os fluxos de saída padrão.
