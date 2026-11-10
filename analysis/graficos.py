# -*- coding: utf-8 -*-
import sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd, numpy as np
from scipy import stats
csv = sys.argv[1]; out = sys.argv[2]
import os; os.makedirs(out, exist_ok=True)
df = pd.read_csv(csv)
A = ["ETL","ELT","Cognitivo"]; NOME={"ETL":"ETL","ELT":"ELT","Cognitivo":"Mapeador\ncognitivo"}
C = {"ETL":"#4C72B0","ELT":"#DD8452","Cognitivo":"#55A868"}
plt.rcParams.update({"font.size":11,"axes.grid":True,"grid.alpha":0.3,"axes.axisbelow":True})
def br(x,d=0):
    s=f"{x:,.{d}f}".replace(",","X").replace(".",",").replace("X","."); return s
fmt=lambda d: FuncFormatter(lambda v,p: br(v,d))
def ic(x):
    x=np.asarray(x,float); return stats.sem(x)*stats.t.ppf(0.975,len(x)-1)
def barras(ax,col,titulo,unid,d,ylim=None,nota=None):
    m=[df.loc[df.arquitetura==a,col].mean() for a in A]; e=[ic(df.loc[df.arquitetura==a,col]) for a in A]
    ax.bar([NOME[a] for a in A],m,yerr=e,capsize=6,color=[C[a] for a in A],edgecolor="black",linewidth=.6)
    top=max(mi+ei for mi,ei in zip(m,e)); 
    for i,(mi,ei) in enumerate(zip(m,e)): ax.text(i,mi+ei+0.015*top,br(mi,d),ha="center",va="bottom",fontsize=9.5)
    ax.set_title(titulo); ax.set_ylabel(unid); ax.yaxis.set_major_formatter(fmt(2 if col=="tempo_execucao_s" else 0))
    ax.set_ylim(*(ylim if ylim else (0,top*1.12)))
    if nota: ax.text(0.5,0.5,nota,transform=ax.transAxes,ha="center",va="center",fontsize=8.5,bbox=dict(boxstyle="round",fc="white",ec="gray",alpha=.9))
# 5.3
fig,ax=plt.subplots(1,3,figsize=(14,4.6))
barras(ax[0],"tempo_execucao_s","Tempo médio de execução","s",3)
barras(ax[1],"latencia_ms","Latência média","ms",2)
barras(ax[2],"throughput_rps","Throughput","registros/s",0)
plt.tight_layout(); plt.savefig(out+"/Figura_5.3_desempenho.png",dpi=200); plt.close()
# 5.4
fig,ax=plt.subplots(1,2,figsize=(10,4.6))
barras(ax[0],"taxa_sucesso_pct","Taxa de sucesso das integrações","%",2,(0,110))
barras(ax[1],"precisao_mapeamento_pct","Precisão do mapeamento","%",2,(0,110))
for a_ in ax: a_.text(0.5,0.02,"ETL e ELT idênticos por construção",transform=a_.transAxes,ha="center",fontsize=8.5,color="#444",va="bottom") if False else None
plt.tight_layout(); plt.savefig(out+"/Figura_5.4_qualidade.png",dpi=200); plt.close()
# 5.5
fig,ax=plt.subplots(1,2,figsize=(10,4.6))
barras(ax[0],"cpu_medio_pct","Utilização média de CPU","%",2)
barras(ax[1],"memoria_pico_mb","Pico de memória do processo","MB",1,(0,205),"Pico saturado (≈163,8 MB):\nnão discrimina as arquiteturas")
plt.tight_layout(); plt.savefig(out+"/Figura_5.5_recursos.png",dpi=200); plt.close()
# 5.6
fig,ax=plt.subplots(2,3,figsize=(14,8.4))
mets=[("tempo_execucao_s","Tempo de execução (s)",2),("latencia_ms","Latência (ms)",0),("throughput_rps","Throughput (registros/s)",0),
      ("cpu_medio_pct","Utilização de CPU (%)",0),("taxa_sucesso_pct","Taxa de sucesso (%)",0),("precisao_mapeamento_pct","Precisão do mapeamento (%)",0)]
for a_,(c,t,d) in zip(ax.flat,mets):
    bp=a_.boxplot([df.loc[df.arquitetura==a,c] for a in A],tick_labels=[NOME[a] for a in A],patch_artist=True,medianprops=dict(color="black",lw=1.6))
    for p,a in zip(bp["boxes"],A): p.set_facecolor(C[a]); p.set_alpha(.65)
    a_.set_title(t); a_.yaxis.set_major_formatter(fmt(d))
plt.tight_layout(); plt.savefig(out+"/Figura_5.6_boxplots.png",dpi=200); plt.close()
# 5.7
fig,ax=plt.subplots(1,2,figsize=(13,4.8))
for a in A:
    s=df[df.arquitetura==a].sort_values("run_id")
    ax[0].plot(s.run_id,s.tempo_execucao_s,marker="o",ms=4,color=C[a],label=NOME[a].replace("\n"," "))
ax[0].set_ylabel("Tempo de execução (s)"); ax[0].yaxis.set_major_formatter(fmt(2)); ax[0].legend()
s=df[df.arquitetura=="ETL"].sort_values("run_id"); ax[1].plot(s.run_id,s.taxa_sucesso_pct,marker="o",ms=4,color="#7B6BA8",label="ETL e ELT (idênticos)")
s=df[df.arquitetura=="Cognitivo"].sort_values("run_id"); ax[1].plot(s.run_id,s.taxa_sucesso_pct,marker="o",ms=4,color=C["Cognitivo"],label="Mapeador cognitivo")
ax[1].set_ylabel("Taxa de sucesso (%)"); ax[1].set_ylim(0,105); ax[1].legend(loc="lower left")
for a_ in ax:
    a_.set_xlabel("Rodada (severidade crescente: drift de 0,15 a 0,65 e ruído de 0,10 a 0,50)",fontsize=9.5); a_.set_xlim(0.5,25.5); a_.set_xticks([1,5,10,15,20,25])
plt.tight_layout(); plt.savefig(out+"/Figura_5.7_evolucao.png",dpi=200); plt.close()
