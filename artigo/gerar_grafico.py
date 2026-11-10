#!/usr/bin/env python3
import matplotlib.pyplot as plt
import numpy as np
import os

labels = ['00. Base', '01. Pool', '02. Índices', '03. Pushdown']
x = np.arange(len(labels))

p95_medians = [17932.0, 13320.5, 4408.9, 4428.0]
p95_mins = [17200.9, 13235.7, 4180.1, 4182.2]
p95_maxs = [18138.3, 15596.6, 4735.9, 5295.9]
p95_err_low = [med - mn for med, mn in zip(p95_medians, p95_mins)]
p95_err_high = [mx - med for med, mx in zip(p95_medians, p95_maxs)]

rps_medians = [3.62, 4.81, 28.23, 29.02]
rps_mins = [3.55, 4.54, 26.73, 23.91]
rps_maxs = [3.77, 4.84, 29.02, 30.49]
rps_err_low = [med - mn for med, mn in zip(rps_medians, rps_mins)]
rps_err_high = [mx - med for med, mx in zip(rps_medians, rps_maxs)]

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.8), dpi=300)

width = 0.42

bars1 = ax1.bar(
    x, p95_medians,
    yerr=[p95_err_low, p95_err_high],
    capsize=5,
    color='#e74c3c',
    edgecolor='#c0392b',
    linewidth=1.0,
    width=width,
    alpha=0.88,
    error_kw=dict(ecolor='#2c3e50', lw=1.2, capthick=1.2)
)
ax1.set_title('(a) Latência p95 (menor é melhor)', fontsize=11, fontweight='bold', pad=12)
ax1.set_ylabel('Tempo de resposta (ms)', fontsize=10)
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=9.5)
ax1.set_ylim(0, 23000)
ax1.grid(axis='y', linestyle='--', alpha=0.5)

for bar, med, mx in zip(bars1, p95_medians, p95_maxs):
    ax1.text(bar.get_x() + bar.get_width() / 2.0, mx + 500,
             f'{med:,.0f} ms'.replace(',', '.'),
             ha='center', va='bottom', fontsize=9, fontweight='bold', color='#2c3e50')

ax1.text(3, p95_maxs[3] + 2500, '-75%',
         ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#922b21',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#fdf2e9', edgecolor='#e74c3c', lw=1))

bars2 = ax2.bar(
    x, rps_medians,
    yerr=[rps_err_low, rps_err_high],
    capsize=5,
    color='#2980b9',
    edgecolor='#1a5276',
    linewidth=1.0,
    width=width,
    alpha=0.88,
    error_kw=dict(ecolor='#2c3e50', lw=1.2, capthick=1.2)
)
ax2.set_title('(b) Vazão (maior é melhor)', fontsize=11, fontweight='bold', pad=12)
ax2.set_ylabel('Requisições por segundo (req/s)', fontsize=10)
ax2.set_xticks(x)
ax2.set_xticklabels(labels, fontsize=9.5)
ax2.set_ylim(0, 40)
ax2.grid(axis='y', linestyle='--', alpha=0.5)

for bar, med, mx in zip(bars2, rps_medians, rps_maxs):
    ax2.text(bar.get_x() + bar.get_width() / 2.0, mx + 1.0,
             f'{med:.2f} req/s'.replace('.', ','),
             ha='center', va='bottom', fontsize=9, fontweight='bold', color='#2c3e50')

ax2.text(3, rps_maxs[3] + 4.2, '8x (+702%)',
         ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#154360',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#ebf5fb', edgecolor='#2980b9', lw=1))

fig.suptitle('Desempenho antes e depois das mudanças (20 usuários virtuais, 60s)',
             fontsize=12, fontweight='bold', y=0.98)
fig.text(0.5, 0.02,
         'Barras mostram a mediana de 3 execuções; linhas de erro indicam mínimo e máximo.',
         ha='center', fontsize=8.5, color='#555555')

plt.tight_layout(rect=[0, 0.05, 1, 0.94])
output_path = os.path.join(os.path.dirname(__file__), 'img', 'p95-por-mudanca.png')
plt.savefig(output_path, dpi=300)
print("Salvo com sucesso:", output_path)
