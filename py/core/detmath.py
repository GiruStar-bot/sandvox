# DetMath in Python: the twin of sim/api/det_math.gd (the same formulas, constants as bit patterns, the same operation order).
# Started from tools/det_math/det_math_ref.py (which made test_det_math's FIXED table), with inv_normal added.
# Why not math.exp / log / pow: they are the platform's libm (glibc, the CRT), whose last bits differ (DET_MATH.md)
import struct, math
def F(b): return struct.unpack('<d', struct.pack('<q', b))[0]
def B(x): return struct.unpack('<q', struct.pack('<d', x))[0]
INVLN2=F(0x3FF71547652B82FE);LN2HI=F(0x3FE62E42FEE00000);LN2LO=F(0x3DEA39EF35793C76)
EXP_HI=F(0x40862E42FEFA39EF);EXP_LO=-F(0x40874910D52D3051)
P1=F(0x3FC555555555553E);P2=-F(0x3F66C16C16BEBD93);P3=F(0x3F11566AAF25DE2C);P4=-F(0x3EBBBD41C5D26BF1);P5=F(0x3E66376972BEA4D0)
TWO54=F(0x4350000000000000);MIN_NORMAL=F(0x0010000000000000);THIRD=F(0x3FD5555555555555)
LG=[None,F(0x3FE5555555555593),F(0x3FD999999997FA04),F(0x3FD2492494229359),F(0x3FCC71C51D8E78AF),F(0x3FC7466496CB03DE),F(0x3FC39A09D078C69F),F(0x3FC2F112DF3E5244)]
PIO4=F(0x3FE921FB54442D18);TWOM27=F(0x3E40000000000000);INVPIO2=F(0x3FE45F306DC9C883)
PIO2_1=F(0x3FF921FB54400000);PIO2_2=F(0x3DD0B4611A600000);PIO2_2T=F(0x3BA3198A2E037073);PIO2_3=F(0x3BA3198A2E000000);PIO2_3T=F(0x397B839A252049C1)
S1=-F(0x3FC5555555555549);S2=F(0x3F8111111110F8A6);S3=-F(0x3F2A01A019C161D5);S4=F(0x3EC71DE357B1FE7D);S5=-F(0x3E5AE5E68A2B9CEB);S6=F(0x3DE5D93A5ACFD57C)
C1=F(0x3FA555555555554C);C2=-F(0x3F56C16C16C15177);C3=F(0x3EFA01A019CB1590);C4=-F(0x3E927E4F809C52AD);C5=F(0x3E21EE9EBDB4B1C4);C6=-F(0x3DA8FAE9BE8838D4)
ATANHI=[F(0x3FDDAC670561BB4F),F(0x3FE921FB54442D18),F(0x3FEF730BD281F69B),F(0x3FF921FB54442D18)]
ATANLO=[F(0x3C7A2B7F222F65E2),F(0x3C81A62633145C07),F(0x3C7007887AF0CBBD),F(0x3C91A62633145C07)]
AT=[F(0x3FD555555555550D),-F(0x3FC999999998EBC4),F(0x3FC24924920083FF),-F(0x3FBC71C6FE231671),F(0x3FB745CDC54C206E),-F(0x3FB3B0F2AF749A6D),F(0x3FB10D66A0D03D51),-F(0x3FADDE2D52DEFD9A),F(0x3FA97B4B24760DEB),-F(0x3FA2B4442C6A6C2F),F(0x3F90AD3AE322DA11)]
PI_=F(0x400921FB54442D18);PI_LO=F(0x3CA1A62633145C07);TWO66=F(0x4410000000000000);TWO60=F(0x43B0000000000000);TWOM29=F(0x3E20000000000000)
INF=float('inf')
def p2(k): return F((1<<(k+1074)) if k< -1022 else ((k+1023)<<52))
def exp(x):
    if x!=x: return x
    if x>EXP_HI: return INF
    if x<EXP_LO: return 0.0
    dk=math.floor(x*INVLN2+0.5)*1.0
    hi=x-dk*LN2HI; lo=dk*LN2LO; r=hi-lo; t=r*r
    c=r-t*(P1+t*(P2+t*(P3+t*(P4+t*P5))))
    if dk==0.0: return 1.0-((r*c)/(c-2.0)-r)
    y=1.0-((lo-(r*c)/(2.0-c))-hi)
    k=int(dk)
    if k>1023: return (y*2.0)*p2(1023)
    if k< -1022: return (y*p2(k+1000))*p2(-1000)
    return y*p2(k)
def log(x):
    if not x>0.0: return -INF if x==0.0 else float('nan')
    if x==INF: return x
    k=0
    if x<MIN_NORMAL: x*=TWO54; k=-54
    hx=B(x)>>32
    ex=(hx>>20)-1023; hx&=0xfffff
    i=(hx+0x95f64)&0x100000
    ex+=i>>20; k+=ex
    f=x*p2(-ex)-1.0
    if ((hx+2)&0xfffff)<3:
        if f==0.0:
            if k==0: return 0.0
            dk=float(k); return dk*LN2HI+dk*LN2LO
        R=f*f*(0.5-THIRD*f)
        if k==0: return f-R
        dk=float(k); return dk*LN2HI-((R-dk*LN2LO)-f)
    s=f/(2.0+f); dk=float(k); z=s*s; w=z*z
    t1=w*(LG[2]+w*(LG[4]+w*LG[6])); t2=z*(LG[1]+w*(LG[3]+w*(LG[5]+w*LG[7]))); R=t2+t1
    if ((hx-0x6147a)|(0x6b851-hx))>0:
        hfsq=0.5*f*f
        if k==0: return f-(hfsq-s*(hfsq+R))
        return dk*LN2HI-((hfsq-(s*(hfsq+R)+dk*LN2LO))-f)
    if k==0: return f-s*(f-R)
    return dk*LN2HI-((s*(f-R)-dk*LN2LO)-f)
def pow(x,y):
    if y==0.0 or x==1.0: return 1.0
    if y==1.0: return x
    if y==2.0: return x*x
    if y==0.5 and x>0.0 and x<INF: return math.sqrt(x)
    if x!=x or y!=y: return float('nan')
    if math.floor(y)==y and abs(y)<=64.0:
        n=int(abs(y)); acc=1.0; b=x
        while True:
            if n&1: acc*=b
            n>>=1
            if n==0: break
            b*=b
        return 1.0/acc if y<0 else acc
    neg=False; ax=x
    if x<0.0:
        if math.floor(y)!=y: return float('nan')
        ax=-x; neg = abs(y)<TWO54 and math.floor(y*0.5)!=y*0.5
    if ax==0.0: r=0.0 if y>0 else INF
    elif ax==INF: r=INF if y>0 else 0.0
    else: r=exp(y*log(ax))
    return -r if neg else r
def rem(x):
    fn=math.floor(x*INVPIO2+0.5)*1.0
    t=x-fn*PIO2_1; w=fn*PIO2_2; r=t-w; w=fn*PIO2_2T-((t-r)-w)
    t=r; w=fn*PIO2_3; r=t-w; w=fn*PIO2_3T-((t-r)-w)
    y0=r-w; y1=(r-y0)-w
    return int(fn),y0,y1
def ksin(x,y):
    z=x*x; w=z*z; r=S2+z*(S3+z*S4)+z*w*(S5+z*S6); v=z*x
    return x-((z*(0.5*y-v*r)-y)-v*S1)
def kcos(x,y):
    z=x*x; w=z*z; r=z*(C1+z*(C2+z*C3))+w*w*(C4+z*(C5+z*C6)); hz=0.5*z; w=1.0-hz
    return w+(((1.0-w)-hz)+(z*r-x*y))
def sin(x):
    ax=abs(x)
    if ax<=PIO4: return x if ax<TWOM27 else ksin(x,0.0)
    n,a,b=rem(x); n&=3
    return [ksin(a,b),kcos(a,b),-ksin(a,b),-kcos(a,b)][n]
def cos(x):
    ax=abs(x)
    if ax<=PIO4: return 1.0 if ax<TWOM27 else kcos(x,0.0)
    n,a,b=rem(x); n&=3
    return [kcos(a,b),-ksin(a,b),-kcos(a,b),ksin(a,b)][n]
def atan(x):
    ax=abs(x); neg=x<0
    if ax>=TWO66: return ATANHI[3]+ATANLO[3] if x>0 else -ATANHI[3]-ATANLO[3]
    id=-1
    if ax<0.4375:
        if ax<TWOM29: return x
    else:
        x=ax
        if ax<1.1875:
            if ax<0.6875: id=0; x=(2.0*x-1.0)/(2.0+x)
            else: id=1; x=(x-1.0)/(x+1.0)
        elif ax<2.4375: id=2; x=(x-1.5)/(1.0+1.5*x)
        else: id=3; x=-1.0/x
    z=x*x; w=z*z
    s1=z*(AT[0]+w*(AT[2]+w*(AT[4]+w*(AT[6]+w*(AT[8]+w*AT[10])))))
    s2=w*(AT[1]+w*(AT[3]+w*(AT[5]+w*(AT[7]+w*AT[9]))))
    if id<0: return x-x*(s1+s2)
    zz=ATANHI[id]-((x*(s1+s2)-ATANLO[id])-x)
    return -zz if neg else zz
def atan2(y,x):
    if x==1.0: return atan(y)
    m=(2 if (x<0 or (x==0 and math.copysign(1,x)<0)) else 0)+(1 if (y<0 or (y==0 and math.copysign(1,y)<0)) else 0)
    if y==0.0:
        if m<2: return y
        return PI_ if m==2 else -PI_
    if x==0.0: return -ATANHI[3]-ATANLO[3] if y<0 else ATANHI[3]+ATANLO[3]
    ay=abs(y); ax=abs(x)
    if ay>ax*TWO60: z=ATANHI[3]+0.5*PI_LO
    elif x<0 and ay*TWO60<ax: z=0.0
    else: z=atan(ay/ax)
    return [z,-z,PI_-(z-PI_LO),(z-PI_LO)-PI_][m]


PPND_A = [F(0x400B18D91E9EEF75), F(0x4060A4888B1A436E), F(0x409ECE5D2213C0CC), F(0x40CAD1D8CD4EE71D), F(0x40E66C3E869B752A), F(0x40F06C1C55B78F20), F(0x40E052D26B2E45E4), F(0x40A39A296F7D925E)]
PPND_B = [F(0x3FF0000000000000), F(0x4045281B386E1AB5), F(0x4085797EFDC8B3F7), F(0x40B512322E75C89F), F(0x40D4B772D5D65266), F(0x40E3317CAA64F4BE), F(0x40DC0E457CB1AE76), F(0x40B46A7ECA984B69)]
PPND_C = [F(0x3FF6C665FDE9526A), F(0x4012857748CAB19B), F(0x401713F71462256A), F(0x400D2ECB1A3D02C4), F(0x3FF453CC085375B2), F(0x3FCEF2ABB9B85C37), F(0x3F9744EB6C45EC67), F(0x3F49615AC0B7ACE9)]
PPND_D = [F(0x3FF0000000000000), F(0x40006CEFBB46A449), F(0x3FFAD278E6526633), F(0x3FE61292F23385C9), F(0x3FC2F5123394F040), F(0x3F8F207A7EAB17BF), F(0x3F41F18CBFDF2728), F(0x3E120D3F686439E4)]
PPND_E = [F(0x401AA1B1C13EE526), F(0x4015DAEA6E875003), F(0x3FFC8EA6461FA445), F(0x3FD2FAD9315255CF), F(0x3F9B2B41193B4EE7), F(0x3F545C1908425345), F(0x3EFC6EC6CC59E02A), F(0x3E8AFB74D693BF93)]
PPND_F = [F(0x3FF0000000000000), F(0x3FE331D34FC7D77F), F(0x3FC186EB183443FB), F(0x3F8E76F93215462A), F(0x3F49C8BC979DC5D7), F(0x3EF35C2C496374BF), F(0x3E831446F740B9E0), F(0x3CE269BFF1F8C190)]
PPND_Q = F(0x3FDB333333333333)
PPND_R = F(0x3FC71EB851EB851F)
PPND_S = F(0x3FF999999999999A)
PPND_LO = F(0x3C90000000000000)
PPND_HI = F(0x3FEFFFFFFFFFFFFF)


def _poly8(c, x):
    r = c[7]
    for k in range(6, -1, -1):
        r = r * x + c[k]
    return r


def inv_normal(p):
    pc = PPND_LO if p <= 0.0 else (PPND_HI if p >= 1.0 else p)
    q = pc - 0.5
    if abs(q) <= PPND_Q:
        r = PPND_R - q * q
        return q * _poly8(PPND_A, r) / _poly8(PPND_B, r)
    t = pc if q < 0.0 else 1.0 - pc
    t = math.sqrt(-log(t))
    if t <= 5.0:
        t -= PPND_S
        v = _poly8(PPND_C, t) / _poly8(PPND_D, t)
    else:
        t -= 5.0
        v = _poly8(PPND_E, t) / _poly8(PPND_F, t)
    return -v if q < 0.0 else v
