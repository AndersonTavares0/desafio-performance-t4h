# Síntese Diagnóstica — Desafio de Performance T4H 2026

Evidências coletadas na linha de base (`resultados/`) e nos testes instrumentados (`diagnostico/`).

---

## 1. Mapeamento de Gargalos Confirmados

| # | Componente / Rota | Problema Observado | Evidência Direta | Causa Raiz Hipotetizada | Critério de Refutação |
|---|---|---|---|---|---|
| **G1** | Driver PG (`db.js`) | Ausência de Connection Pooling | Cada consulta chama `new Client()`, `connect()` e `end()`. | Handshake TCP e fork de processo dedicado no PostgreSQL por query (até 30 conexões por request em `/clientes/:id/pedidos`). | Se a introdução de `pg.Pool` não reduzir a contenção de CPU do PostgreSQL em repouso nem diminuir a latência média sob concorrência. |
| **G2** | Rota `/clientes/:id/pedidos` (Peso 20%) | Cascata $N+1$ e falta de índices de FK | `EXPLAIN` aponta `Parallel Seq Scan` em 500k linhas de `pedidos` (27 ms) e `Parallel Seq Scan` em 1,5M linhas de `itens_pedido` (36 ms) por pedido. | Falta de índices B-tree em `pedidos(cliente_id)` e `itens_pedido(pedido_id)` associada a loops seriais de queries no Node. | Se índices em `cliente_id` e `pedido_id` não alterarem o plano de `Seq Scan` para `Index Scan`. |
| **G3** | Rota `/clientes?email=` (Peso 15%) | Seq Scan em tabela de 100k registros | `EXPLAIN` aponta `Seq Scan on clientes` (32,5 ms) avaliando `lower(email)`. | Ausência de índice funcional em `lower(email)`. | Se um índice `ON clientes (lower(email))` não reduzir o tempo de query para <1 ms. |
| **G4** | Rota `/pedidos?status=` (Peso 15%) | Dois Seq Scans de 500k linhas por requisição | `EXPLAIN` aponta 53 ms para `count(*)` e 81 ms para listagem com `ORDER BY criado_em DESC, id DESC`. | Ausência de índice composto cobrindo o predicado de filtro e as colunas de ordenação. | Se um índice `ON pedidos (status, criado_em DESC, id DESC)` não for utilizado pelo otimizador de consultas. |
| **G5** | Rota `/relatorios/top-produtos` (Peso 2%) | Varredura de 1,5M linhas com agregação pesada | `EXPLAIN` aponta 948 ms por execução em repouso e p95 de 25 s sob carga. | HashJoin e HashAggregate em toda a base de pedidos e itens ativos para cada chamada. | Se a query não for responsável pelos picos máximos de latência do banco. |
| **G6** | Rota `/relatorios/vendas-por-dia` (Peso 8%) | Predicado não-sargável e transporte de payload redundante | `EXPLAIN` aponta 270 ms; transfere coluna `observacoes` e agrega ~13k linhas no Node.js. | Uso de `criado_em::date BETWEEN` impede índice direto e transfere overhead de rede e CPU para o Node. | Se pré-agregar no PostgreSQL não reduzir tempo de CPU e uso de memória. |
| **G7** | Middleware de log (`server.js`) | Serialização síncrona de payload JSON | Código executa `JSON.stringify(corpo)` e `console.log` síncrono a cada requisição. | Bloqueio potencial do Event Loop do Node.js sob alta vazão. | Se remover o log completo da resposta não alterar o uso de CPU da API sob alta vazão (>100 req/s). |

---

## 2. Hipóteses Descartadas ou Secundárias

1. **Memória Insuficiente do PostgreSQL:**
   - *Observação:* O PostgreSQL utilizou 448 MiB de memória média (dentro do teto de 512 MiB configurado no compose). Não houve OOM ou término anormal de containers.
   - *Conclusão:* O gargalo primário do banco é **CPU (97,1%)** decorrente de processamento de Seq Scans massivos e criação/destruição de processos, não falta de RAM.

2. **Gargalo no Node.js na Linha de Base:**
   - *Observação:* A CPU da API permaneceu em **5,0%**.
   - *Conclusão:* A API Node.js não é o gargalo limitante atual porque passa mais de 90% do tempo ociosa aguardando o socket do PostgreSQL responder.

---

## 3. Priorização de Intervenções (Impacto vs Risco)

Seguindo a regra de escolher no máximo 2 a 3 mudanças de maior retorno sistêmico:

1. **Intervenção Prioritária 1: Connection Pooling no Driver (`pg.Pool`)**
   - *Por quê:* Afeta 100% das rotas e elimina imediatamente a sobrecarga de forks de processos e handshakes no PostgreSQL.
   - *Risco ao contrato:* Nulo (mesmas queries, apenas reaproveitamento de conexões).

2. **Intervenção Prioritária 2: Criação de Índices Estratégicos (`banco/03-indices.sql`)**
   - *Por quê:* Ataca diretamente as rotas que representam 70% da carga (`/clientes/:id/pedidos`, `/clientes?email=`, `/pedidos?status=`), transformando Seq Scans de 500k e 1,5M linhas em Index Lookups de frações de milissegundo.
   - *Risco ao contrato:* Nulo se os tipos e ordenações forem preservados.

3. **Intervenção Prioritária 3: Pushdown de Agregação SQL em `/relatorios/vendas-por-dia`**
   - *Por quê:* A rota transferia dezenas de milhares de registros completos (~4 MB por chamada) para agregação manual em JavaScript `Map` no Node.js. Transferir a agregação para o PostgreSQL (`GROUP BY 1`, `SUM`, `COUNT`) reduz o payload de rede para <5 KB e desonera o Event Loop da API.
   - *Risco ao contrato:* Baixo — exige conversão explícita com `Number(...)` para atender à tipagem inteira do JSON gravado no contrato original.
   - *Nota sobre `/clientes/:id/pedidos`:* A indexação B-tree na Intervenção 02 reduziu a latência da rota de 15.252 ms para 115 ms (mais de 100x mais rápida), resolvendo o gargalo dominante de I/O e tornando desnecessário refatorar o loop da rota, preservando a simplicidade do código da aplicação.
