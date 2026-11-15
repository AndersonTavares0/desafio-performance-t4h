# Matriz de Decisão de Alternativas e Escolha das Intervenções

Análise multicritério para selecionar no máximo 2 a 3 intervenções prioritárias para o ciclo de medição (Etapa 4), conforme estipulado no enunciado.

---

## 1. Matriz Comparativa de Alternativas

| Área | Alternativa | Ganho Esperado | Custo Computacional | Risco ao Contrato | Esforço | Decisão |
|---|---|---|---|---|---|---|
| **Conexões** | **A1: `pg.Pool` nativo** no Node.js | Alto (elimina handshakes e forks por query) | Nenhum recurso extra; reduz CPU do banco | Nulo (mesmas queries executadas) | Baixo (ajuste em `api/src/db.js`) | **Aprovada (Intervenção 01)** |
| **Conexões** | **A2: PgBouncer** como container sidecar | Alto | Adiciona consumo de RAM/CPU de novo container | Baixo | Médio (altera compose e configs) | *Descartada* (A1 é suficiente sem custo extra) |
| **Bancos / Índices** | **B1: Índices B-Tree** em FKs e filtros (`cliente_id`, `pedido_id`, `lower(email)`, `status+criado_em`) | Massivo (elimina Seq Scans de 500k e 1,5M linhas) | ~90 MiB de disco (medido em `diagnostico/05-tamanho-indices.txt`); reduz 90% CPU do banco | Nulo | Baixo (arquivo `banco/03-indices.sql`) | **Aprovada (Intervenção 02)** |
| **Bancos / Índices** | **B2: Índices parciais** (`WHERE status = 'pago'`) | Médio | Menor consumo de disco | Baixo | Baixo | *Parcialmente adotada*: índice funcional parcial em `criado_em::date` com `WHERE status <> 'cancelado'` |
| **Bancos / Busca** | **B3: Extensão `pg_trgm`** + GIN em `produtos.nome` | Médio (rota tem peso 15%) | Alto custo de CPU em build de índice GIN | Baixo | Médio (requer extensão no Postgres) | *Movida para `proximos-testes.md`* |
| **Aplicação** | **C1: Pushdown de agregação** em `/relatorios/vendas-por-dia` (`GROUP BY`, `SUM`, `COUNT` no SQL) | Médio (elimina transferência de linhas brutas) | Reduz CPU e RAM da API | Baixo (exige `Number(...)` para manter os tipos) | Médio | **Aprovada (Intervenção 03)** |
| **Aplicação** | **C2: Eliminar N+1** em `/clientes/:id/pedidos` via query única / batch | Alto (reduz round-trips de rede) | Reduz CPU do Node e do Banco | Médio (exige replicar exatamente o JSON do contrato) | Médio | *Descartada*: a Intervenção 02 já levou a rota de 11.744 ms para 115 ms |
| **Aplicação** | **C3: Remoção do log síncrono** em `server.js` | Médio sob alta vazão | Reduz latência de Event Loop | Nulo | Baixo | *Movida para `proximos-testes.md`* |

---

## 2. Escolha das 2 a 3 Intervenções do Desafio

As intervenções foram priorizadas pela combinação de: **Peso da rota na carga $\times$ Tamanho do gargalo comprovado $\times$ Custo de infraestrutura $\times$ Risco ao contrato**.

### Intervenção 01: Connection Pooling via `pg.Pool` (`01-connection-pool`)
- **Justificativa:** Ataca o gargalo global G1. Atualmente, cada query abre um socket TCP e dispara um `fork()` de processo no PostgreSQL. Como `/clientes/:id/pedidos` realiza até 30 queries por requisição, o pooling estabiliza o banco imediatamente sem alterar nenhuma linha de SQL ou resposta JSON.

### Intervenção 02: Índices B-Tree Estratégicos (`02-indices-banco`)
- **Justificativa:** Ataca diretamente os gargalos G2, G3, G4 e G6, que concentram a maior parte do tráfego do teste de carga. O `banco/03-indices.sql` cria 6 índices:
  - `CREATE INDEX idx_pedidos_cliente_criado_em ON pedidos (cliente_id, criado_em DESC, id DESC);`
  - `CREATE INDEX idx_itens_pedido_pedido_id_id ON itens_pedido (pedido_id, id);`
  - `CREATE INDEX idx_itens_pedido_produto_id ON itens_pedido (produto_id);`
  - `CREATE INDEX idx_clientes_lower_email ON clientes (lower(email));`
  - `CREATE INDEX idx_pedidos_status_criado_em ON pedidos (status, criado_em DESC, id DESC);`
  - `CREATE INDEX idx_pedidos_criado_em_date ON pedidos ((criado_em::date)) WHERE status <> 'cancelado';`
  - Substitui varreduras sequenciais de 1,5 milhão de registros por buscas em profundidade $O(\log N)$. Os 6 índices somam ~90 MiB, medidos em `diagnostico/05-tamanho-indices.txt`.

### Intervenção 03: Pushdown de Agregação em Vendas por Dia (`03-pushdown-agregacao`)
- **Justificativa:** A rota `/relatorios/vendas-por-dia` transferia todas as linhas do período, incluindo a coluna `observacoes`, para agregação manual em um `Map` no Node.js. Mover `GROUP BY`, `SUM` e `COUNT` para o SQL faz trafegar apenas o resultado agregado, reduzindo CPU e RAM da API. Esta intervenção substituiu a eliminação do loop $N+1$ originalmente prevista: os índices da Intervenção 02 já reduziram `/clientes/:id/pedidos` de 11.744 ms para 115 ms, tornando a refatoração desnecessária para o contrato.
