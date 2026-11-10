-- 03-indices.sql: Indices estrategicos para eliminacao de Seq Scans

-- 1. Rota /clientes/:id/pedidos (peso 20%): busca de pedidos por cliente e itens por pedido
CREATE INDEX idx_pedidos_cliente_criado_em ON pedidos (cliente_id, criado_em DESC, id DESC);
CREATE INDEX idx_itens_pedido_pedido_id_id ON itens_pedido (pedido_id, id);
CREATE INDEX idx_itens_pedido_produto_id ON itens_pedido (produto_id);

-- 2. Rota /clientes?email= (peso 15%): busca case-insensitive por email
CREATE INDEX idx_clientes_lower_email ON clientes (lower(email));

-- 3. Rota /pedidos?status=&pagina= (peso 15%): filtro por status com ordenacao deterministica
CREATE INDEX idx_pedidos_status_criado_em ON pedidos (status, criado_em DESC, id DESC);

-- 4. Rota /relatorios/vendas-por-dia (peso 8%): filtro por intervalo de datas em pedidos nao cancelados
CREATE INDEX idx_pedidos_criado_em_date ON pedidos ((criado_em::date)) WHERE status <> 'cancelado';
