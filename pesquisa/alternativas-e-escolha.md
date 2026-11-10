# Matriz de Decisão de Alternativas e Escolha das Intervenções

Análise multicritério para selecionar no máximo 2 a 3 intervenções prioritárias para o ciclo de medição (Etapa 4), conforme estipulado no enunciado e no `planejamento.md`.

---

## 1. Matriz Comparativa de Alternativas

| Área | Alternativa | Ganho Esperado | Custo Computacional | Risco ao Contrato | Esforço | Decisão |
|---|---|---|---|---|---|---|
| **Conexões** | **A1: `pg.Pool` nativo** no Node.js | Alto (elimina handshakes e forks por query) | Nenhum recurso extra; reduz CPU do banco | Nulo (mesmas queries executadas) | Baixo (ajuste em `api/src/db.js`) | **Aprovada (Intervenção 01)** |
| **Conexões** | **A2: PgBouncer** como container sidecar | Alto | Adiciona consumo de RAM/CPU de novo container | Baixo | Médio (altera compose e configs) | *Descartada* (A1 é suficiente sem custo extra) |
| **Bancos / Índices** | **B1: Índices B-Tree** em FKs e filtros (`cliente_id`, `pedido_id`, `lower(email)`, `status+criado_em`) | Massivo (elimina Seq Scans de 500k e 1,5M linhas) | Pequeno aumento de disco (<150 MB); reduz 90% CPU do banco | Nulo | Baixo (arquivo `banco/03-indices.sql`) | **Aprovada (Intervenção 02)** |
| **Bancos / Índices** | **B2: Índices parciais** (`WHERE status = 'pago'`) | Médio | Menor consumo de disco | Baixo | Baixo | *Descartada* (o índice composto B1 atende a todos os status) |
| **Bancos / Busca** | **B3: Extensão `pg_trgm`** + GIN em `produtos.nome` | Médio (rota tem peso 15%) | Alto custo de CPU em build de índice GIN | Baixo | Médio (requer extensão no Postgres) | *Movida para `proximos-testes.md`* |
| **Aplicação** | **C1: Eliminar N+1** em `/clientes/:id/pedidos` via query única / batch | Alto (reduz round-trips de rede) | Reduz CPU do Node e do Banco | Médio (exige replicar exatamente o JSON do contrato) | Médio | **Aprovada (Intervenção 03)** |
| **Aplicação** | **C2: Remoção do log síncrono** em `server.js` | Médio sob alta vazão | Reduz latência de Event Loop | Nulo | Baixo | *Movida para `proximos-testes.md`* |

---

## 2. Escolha das 2 a 3 Intervenções do Desafio

As intervenções foram priorizadas pela combinação de: **Peso da rota na carga $\times$ Tamanho do gargalo comprovado $\times$ Custo de infraestrutura $\times$ Risco ao contrato**.

### Intervenção 01: Connection Pooling via `pg.Pool` (`01-connection-pool`)
- **Justificativa:** Ataca o gargalo global G1. Atualmente, cada query abre um socket TCP e dispara um `fork()` de processo no PostgreSQL. Como `/clientes/:id/pedidos` realiza até 30 queries por requisição, o pooling estabiliza o banco imediatamente sem alterar nenhuma linha de SQL ou resposta JSON.

### Intervenção 02: Índices B-Tree Estratégicos (`02-indices-banco`)
- **Justificativa:** Ataca diretamente os gargalos G2, G3 e G4, que concentram mais de 70% de todo o tráfego do teste de carga:
  - `CREATE INDEX idx_pedidos_cliente_id ON pedidos (cliente_id);`
  - `CREATE INDEX idx_itens_pedido_pedido_id ON itens_pedido (pedido_id);`
  - `CREATE INDEX idx_clientes_lower_email ON clientes (lower(email));`
  - `CREATE INDEX idx_pedidos_status_criado_em ON pedidos (status, criado_em DESC, id DESC);`
  - Substitui varreduras sequenciais de 1,5 milhão de registros por buscas em profundidade $O(\log N)$ com custo <1 ms.

### Intervenção 03: Eliminação do Loop $N+1$ em Pedidos (`03-elimina-n-mais-um`)
- **Justificativa:** A rota `/clientes/:id/pedidos` responde por 20% do tráfego e possui o maior p95 do fluxo principal (18 a 20 segundos na linha de base). Transformar o loop de queries individuais em consultas agrupadas (batching ou agregação) reduz o número de round-trips de rede entre Node.js e PostgreSQL a um número constante $O(1)$.
