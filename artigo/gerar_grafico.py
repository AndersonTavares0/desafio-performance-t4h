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
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2), dpi=300)

width = 0.44

# Painel A: Latencia de Cauda p95
bars1 = ax1.bar(
    x, p95_medians,
    yerr=[p95_err_low, p95_err_high],
    capsize=6,
    color='#e74c3c',
    edgecolor='#c0392b',
    linewidth=1.2,
    width=width,
    alpha=0.88,
    error_kw=dict(ecolor='#2c3e50', lw=1.3, capthick=1.3)
)
ax1.set_title('(a) Latência de Cauda p95 (Menor é Melhor)', fontsize=12, fontweight='bold', pad=14)
ax1.set_ylabel('Latência p95 (ms)', fontsize=10, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=10)
ax1.set_ylim(0, 24000)
ax1.grid(axis='y', linestyle='--', alpha=0.5)

# Rotulos de valores posicionados sempre ACIMA da barra de erro superior para evitar colisao
for bar, med, mx in zip(bars1, p95_medians, p95_maxs):
    y_pos = mx + 650
    ax1.text(bar.get_x() + bar.get_width() / 2.0, y_pos,
             f'{med:,.0f} ms'.replace(',', '.'),
             ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#2c3e50')

# Anotacao de reducao com posicionamento isolado
ax1.annotate('Queda de -75,3%\n(17.932 -> 4.428 ms)',
             xy=(3, p95_maxs[3] + 1800),
             xytext=(2.2, 14500),
             arrowprops=dict(arrowstyle='->', lw=1.8, color='#c0392b', connectionstyle='arc3,rad=-0.15'),
             fontsize=9, fontweight='bold', color='#922b21',
             ha='center',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#fdf2e9', edgecolor='#e74c3c', lw=1.2))

# Painel B: Vazao Throughput
bars2 = ax2.bar(
    x, rps_medians,
    yerr=[rps_err_low, rps_err_high],
    capsize=6,
    color='#2980b9',
    edgecolor='#1a5276',
    linewidth=1.2,
    width=width,
    alpha=0.88,
    error_kw=dict(ecolor='#2c3e50', lw=1.3, capthick=1.3)
)
ax2.set_title('(b) Vazão Throughput (Maior é Melhor)', fontsize=12, fontweight='bold', pad=14)
ax2.set_ylabel('Taxa de Requisições (req/s)', fontsize=10, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(labels, fontsize=10)
ax2.set_ylim(0, 42)
ax2.grid(axis='y', linestyle='--', alpha=0.5)

# Rotulos de valores posicionados sempre ACIMA da barra de erro superior para evitar colisao
for bar, med, mx in zip(bars2, rps_medians, rps_maxs):
    y_pos = mx + 1.2
    ax2.text(bar.get_x() + bar.get_width() / 2.0, y_pos,
             f'{med:.2f} req/s'.replace('.', ','),
             ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#2c3e50')

# Anotacao de ganho em regiao limpa e aberta (acima de Base e Pool)
ax2.annotate('Salto de 8x na vazão\n(+701,7% vs. Base)',
             xy=(3, rps_maxs[3] + 4.0),
             xytext=(0.85, 31.0),
             arrowprops=dict(arrowstyle='->', lw=1.8, color='#1a5276', connectionstyle='arc3,rad=0.18'),
             fontsize=9, fontweight='bold', color='#154360',
             ha='center',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#ebf5fb', edgecolor='#2980b9', lw=1.2))

fig.suptitle('Avaliação Empírica de Desempenho por Intervenção Arquitetural (n=3 rodadas de 60s / 20 VUs)',
             fontsize=12.5, fontweight='bold', y=0.97)
fig.text(0.5, 0.02,
         'Nota: As barras representam a mediana amostral oficial; linhas de erro indicam a amplitude [mínimo, máximo] das 3 execuções controladas.',
         ha='center', fontsize=8.5, color='#444444')

plt.tight_layout(rect=[0, 0.05, 1, 0.93])
output_path = os.path.join(os.path.dirname(__file__), 'img', 'p95-por-mudanca.png')
plt.savefig(output_path, dpi=300)
print(f'Grafico salvo com sucesso em: {output_path}')
