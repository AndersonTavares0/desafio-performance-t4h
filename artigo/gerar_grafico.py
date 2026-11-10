#!/usr/bin/env python3
"""
Gera o grafico cientifico comparativo de desempenho (p95 e vazao)
a partir das medianas e intervalos empiricos [min, max] medidos nas
3 rodadas oficiais de cada intervencao registradas em resultados/.

Requisitos:
    pip install matplotlib numpy
Uso:
    python3 artigo/gerar_grafico.py
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Dados empiricos consolidados das 3 rodadas oficiais (resultados/)
labels = ['00. Base', '01. Pool', '02. Índices', '03. Pushdown']
x = np.arange(len(labels))

# Metricas p95 (ms)
p95_medians = [17932.0, 13320.5, 4408.9, 4428.0]
p95_mins = [17200.9, 13235.7, 4180.1, 4182.2]
p95_maxs = [18138.3, 15596.6, 4735.9, 5295.9]
p95_err_low = [med - mn for med, mn in zip(p95_medians, p95_mins)]
p95_err_high = [mx - med for med, mx in zip(p95_medians, p95_maxs)]

# Metricas Vazao (req/s)
rps_medians = [3.62, 4.81, 28.23, 29.02]
rps_mins = [3.55, 4.54, 26.73, 23.91]
rps_maxs = [3.77, 4.84, 29.02, 30.49]
rps_err_low = [med - mn for med, mn in zip(rps_medians, rps_mins)]
rps_err_high = [mx - med for med, mx in zip(rps_medians, rps_maxs)]

# Estilo de publicacao cientifica
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8), dpi=300)

# Painel A: Latencia de Cauda p95
bars1 = ax1.bar(
    x, p95_medians,
    yerr=[p95_err_low, p95_err_high],
    capsize=5,
    color='#d9534f',
    edgecolor='#b52b27',
    width=0.55,
    alpha=0.9,
    ecolor='#333333'
)
ax1.set_title('(a) Latência de Cauda p95 (Menor é Melhor)', fontsize=12, fontweight='bold', pad=12)
ax1.set_ylabel('Latência p95 (ms)', fontsize=10, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=10)
ax1.set_ylim(0, 21000)
ax1.grid(axis='y', linestyle='--', alpha=0.6)

for bar, med in zip(bars1, p95_medians):
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width() / 2.0, yval + 700, f'{med:,.0f} ms'.replace(',', '.'),
             ha='center', va='bottom', fontsize=9, fontweight='bold')

ax1.annotate('-75,3% no p95', xy=(3, 4428.0), xytext=(2.2, 10000),
             arrowprops=dict(arrowstyle='->', lw=1.5, color='#b52b27'),
             fontsize=9, fontweight='bold', color='#b52b27',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#fdf2e9', edgecolor='#d9534f', lw=1))

# Painel B: Vazao Throughput
bars2 = ax2.bar(
    x, rps_medians,
    yerr=[rps_err_low, rps_err_high],
    capsize=5,
    color='#3498db',
    edgecolor='#1f618d',
    width=0.55,
    alpha=0.9,
    ecolor='#333333'
)
ax2.set_title('(b) Vazão Throughput (Maior é Melhor)', fontsize=12, fontweight='bold', pad=12)
ax2.set_ylabel('Requisições por Segundo (req/s)', fontsize=10, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(labels, fontsize=10)
ax2.set_ylim(0, 36)
ax2.grid(axis='y', linestyle='--', alpha=0.6)

for bar, med in zip(bars2, rps_medians):
    yval = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width() / 2.0, yval + 1.0, f'{med:.2f}'.replace('.', ','),
             ha='center', va='bottom', fontsize=9, fontweight='bold')

ax2.annotate('8x vazão (+701,7%)', xy=(3, 29.02), xytext=(1.0, 31.5),
             arrowprops=dict(arrowstyle='->', lw=1.5, color='#1f618d'),
             fontsize=9, fontweight='bold', color='#1f618d',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='#ebf5fb', edgecolor='#3498db', lw=1))

fig.suptitle('Avaliação Empírica de Desempenho por Intervenção Arquitetural (n=3 rodadas)',
             fontsize=13, fontweight='bold', y=0.98)
fig.text(0.5, 0.01,
         'Nota: Barras indicam a mediana amostral; linhas de erro representam os limites [mínimo, máximo] das 3 baterias de 60s com 20 VUs.',
         ha='center', fontsize=8, color='#555555')

plt.tight_layout(rect=[0, 0.04, 1, 0.94])
output_path = os.path.join(os.path.dirname(__file__), 'img', 'p95-por-mudanca.png')
plt.savefig(output_path, dpi=300)
print(f'Grafico salvo com sucesso em: {output_path}')
