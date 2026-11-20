"""Ganho do filtro medido no Dranetz (.ddbx): saída do inversor (canal A) × saída do filtro (canal B), harmônica a harmônica.
Usa o leitor qee/dranetz_ddb.py da Plataforma de Estudos – rodar SEMPRE numa cópia separada (não na pasta da Plataforma)."""
import sys, numpy as np
sys.path.insert(0,'/home/claude/qee_copia')
from qee import dranetz_ddb as D
def capturas(f):
    o=D.ondas(f, log=lambda *a: None)
    t=o['t'].values.astype('datetime64[ns]').astype(np.int64)
    gaps=np.where(np.diff(t)>2e6)[0]
    for s in np.split(np.arange(len(t)), gaps+1):
        if len(s)<2048: continue
        dt=np.median(np.diff(t[s]))/1e9
        yield str(o['t'].iloc[s[0]])[:19], dt, {c:o[c].values[s].astype(float) for c in o.columns if c!='t'}
def espectro(y,dt,f1g=None):
    y=y[~np.isnan(y)]
    Y=np.abs(np.fft.rfft((y-y.mean())*np.hanning(len(y)))); fr=np.fft.rfftfreq(len(y),dt)
    m=(fr>20)&(fr<80); f1=fr[m][np.argmax(Y[m])] if f1g is None else f1g
    nper=1/(f1*dt); nc=int(len(y)/nper); N=int(round(nc*nper)); yy=y[:N]
    C=np.fft.rfft(yy)/N*2
    return f1, nc, C, N
def ganhos(f, ca, cb, hs=(5,7,11,13,17,19,23,25)):
    out=[]
    for tt,dt,ch in capturas(f):
        a,b=ch[ca],ch[cb]
        if np.nanstd(a)<20 or np.nanstd(b)<20: continue
        f1,nc,A,N=espectro(a,dt); _,_,B,_=espectro(b,dt,f1)
        row=dict(t=tt,f1=round(f1,1),Va=round(abs(A[nc])/np.sqrt(2),1),Vb=round(abs(B[nc])/np.sqrt(2),1))
        for h in hs:
            if nc*h<len(A): row[h]=(round(100*abs(A[nc*h])/abs(A[nc]),2),round(100*abs(B[nc*h])/abs(B[nc]),2),round(abs(B[nc*h])/max(abs(A[nc*h]),1e-9),2))
        # switching band
        fr=np.fft.rfftfreq(N,dt)
        row['thd_b_ate50']=round(100*np.sqrt(sum(abs(B[nc*h])**2 for h in range(2,51) if nc*h<len(B)))/abs(B[nc]),2)
        out.append(row)
    return out
if __name__=='__main__':
    f,ca,cb=sys.argv[1],sys.argv[2],sys.argv[3]
    for r in ganhos(f,ca,cb): print(r)
