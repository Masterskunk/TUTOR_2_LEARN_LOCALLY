#!/usr/bin/env python3
"""tutor.py - Local, offline AI tutor (main app).

Runs against a local Ollama model. Teaches one concept at a time from
curso/curso.json. Two study modes, chosen at startup / menu:
  MODE A - guided: teaches the current module from the course content.
  MODE B - ask anything: vector RAG over a selectable memory
           (vectorial = indice_vectorial.json, or wiki = indice_wiki.json).
Also: multiple-choice exams (banco.json), scoring + live HTML report,
and a personalized student profile (student_profile.py).
User-facing text is Spanish on purpose (that is what the learner reads);
code comments are in English.
"""
import json, os, re, csv, html, datetime, urllib.request, urllib.parse, webbrowser, random
import rag             # vector search (rag.py)
import student_profile  # student memory / profile (student_profile.py)

HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=HERE
PROG=os.path.join(ROOT,"progreso","progreso.json"); CSVF=os.path.join(ROOT,"progreso","puntajes.csv")
PROMPT=os.path.join(HERE,"tutor_prompt.md"); BANCO=os.path.join(HERE,"banco.json")
CURSOF=os.path.join(HERE,"curso","curso.json"); REPORTE=os.path.join(ROOT,"reporte.html")
INDICE_VEC=os.path.join(HERE,"indice_vectorial.json"); INDICE_WIKI=os.path.join(HERE,"indice_wiki.json")
HOST=os.environ.get("OLLAMA_HOST","http://localhost:11434")
MODEL=os.environ.get("OLLAMA_MODEL","qwen3:14b")
MODO="A"; MEM="vectorial"
C_T="\033[1;96m";C_U="\033[1;93m";C_S="\033[1;92m";C_H="\033[1;95m";C_R="\033[1;91m";C_0="\033[0m"

def load_prog(): return json.load(open(PROG,encoding="utf-8"))
def save_prog(d): json.dump(d,open(PROG,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
def load_curso(): return json.load(open(CURSOF,encoding="utf-8"))

def ensure_progreso():
    """Create progreso/ and progreso.json from the course modules if missing,
    and add any new modules (e.g. after ingesting a PDF)."""
    os.makedirs(os.path.join(ROOT,"progreso"),exist_ok=True)
    curso=load_curso(); ks=list(curso.keys())
    if not os.path.exists(PROG):
        mods={k:{"titulo":curso[k].get("titulo",k),
                 "estado":"pendiente" if i==0 else "bloqueado",
                 "mejor_puntaje":0,"intentos":0} for i,k in enumerate(ks)}
        save_prog({"alumno":"","idioma":"es+en","ultima_sesion":None,
                   "modulo_actual":ks[0] if ks else "","modulos":mods}); return
    d=load_prog(); changed=False
    for k in ks:
        if k not in d["modulos"]:
            d["modulos"][k]={"titulo":curso[k].get("titulo",k),"estado":"bloqueado","mejor_puntaje":0,"intentos":0}; changed=True
    if changed: save_prog(d)

def log_score(mod,ej,punt,nota=""):
    nuevo=not os.path.exists(CSVF)
    with open(CSVF,"a",encoding="utf-8",newline="") as f:
        w=csv.writer(f)
        if nuevo: w.writerow(["fecha","modulo","ejercicio","puntaje","notas"])
        w.writerow([datetime.date.today().isoformat(),mod,ej,punt,nota])
    autoreporte()

def mastered(mod,score):
    d=load_prog();m=d["modulos"]
    if mod in m:
        m[mod]["estado"]="completado"; m[mod]["mejor_puntaje"]=max(int(m[mod].get("mejor_puntaje",0)),int(score))
        m[mod]["intentos"]=int(m[mod].get("intentos",0))+1
        ks=list(m.keys());i=ks.index(mod)
        if i+1<len(ks) and m[ks[i+1]]["estado"]=="bloqueado":
            m[ks[i+1]]["estado"]="pendiente"; d["modulo_actual"]=ks[i+1]
    d["ultima_sesion"]=datetime.date.today().isoformat(); save_prog(d)

def avance_txt():
    d=load_prog();out=[]
    for k,v in d["modulos"].items():
        mk={"completado":"[x]","pendiente":"[>]","bloqueado":"[ ]"}.get(v["estado"],"[ ]")
        out.append(f"  {mk} {k}: {v['titulo']}  (mejor {v['mejor_puntaje']})")
    return "Modulo actual: %s\n%s"%(d["modulo_actual"],"\n".join(out))

def material_modulo(mod):
    c=load_curso().get(mod,{})
    if not c: return ""
    t=[f"MODULO {mod}: {c['titulo']}", f"Por que importa: {c.get('porque_importa','')}"]
    for l in c["lecciones"]:
        t.append(f"- {l['concepto']}: {l['texto']} Ejemplo: {l.get('ejemplo','')}")
    if c.get("glosario"):
        t.append("Glosario ES<->EN: "+"; ".join(f"{k}={v}" for k,v in c["glosario"].items()))
    return "\n".join(t)

# ---------- Ollama ----------
def ollama(msgs):
    print(f"{C_S}(pensando...){C_0}",flush=True)
    body=json.dumps({"model":MODEL,"messages":msgs,"stream":False,"think":False}).encode()
    req=urllib.request.Request(HOST+"/api/chat",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=600) as r: return json.loads(r.read())["message"]["content"]

def process(text):
    text=re.sub(r"<think>.*?</think>","",text,flags=re.S)
    text=re.sub(r"<think>.*$","",text,flags=re.S).strip()
    for mod,ej,pu,nota in re.findall(r"\[\[SCORE\s+(\S+)\s+(\S+)\s+(\d+)\s*([^\]]*)\]\]",text): log_score(mod,ej,pu,nota.strip())
    for mod,pu in re.findall(r"\[\[MASTERED\s+(\S+)\s+(\d+)\]\]",text): mastered(mod,pu)
    return re.sub(r"\[\[(SCORE|MASTERED)[^\]]*\]\]","",text).strip()

def turno(msgs,user):
    msgs.append({"role":"user","content":user}); limpio=process(ollama(msgs))
    if not limpio:
        limpio=process(ollama(msgs+[{"role":"user","content":"Responde directo en espanol, solo la leccion, una idea, sin etiquetas ni razonamiento."}]))
    if not limpio: limpio="(No obtuve respuesta del modelo. Escribe de nuevo o 'menu'.)"
    msgs.append({"role":"assistant","content":limpio}); return limpio

# ---------- MODE A: guided, one module at a time ----------
def leccion_A(mod=None,avanzar_nota=""):
    d=load_prog(); mod=mod or d["modulo_actual"]
    base=open(PROMPT,encoding="utf-8").read()
    mat=material_modulo(mod)
    perfil_txt=student_profile.leer_perfil()
    pz=f"\n\nPERFIL DEL ALUMNO (personaliza: insiste en lo debil, no repitas lo dominado):\n{perfil_txt}" if perfil_txt else ""
    sysmsg=base+f"\n\nMATERIAL DE ESTE MODULO (ensena SOLO con esto, un concepto por turno, y genera ejercicios de este material):\n{mat}{pz}\n\n{avanzar_nota}"
    msgs=[{"role":"system","content":sysmsg}]
    print(f"\n{C_S}Modo A (guiado) - {mod}: {d['modulos'][mod]['titulo']}. Escribe para responder. ('menu'=volver){C_0}")
    try: print(f"\n{C_T}Tutor:{C_0} {turno(msgs,'Hola, empecemos este modulo. Primer concepto, por favor.')}\n")
    except Exception as e:
        print(f"{C_R}No conecto con Ollama ({e}). Arranca: ollama serve ; baja: ollama pull {MODEL}{C_0}"); return
    while True:
        try: u=input(f"{C_U}Tu:{C_0} ").strip()
        except (EOFError,KeyboardInterrupt): print(); return
        if not u: continue
        if u.lower() in ("menu","/menu"): return
        try: print(f"\n{C_T}Tutor:{C_0} {turno(msgs,u)}\n")
        except Exception as e: print(f"{C_R}Error con Ollama: {e}{C_0}\n")

# ---------- MODE B: vector RAG (ask anything) ----------
def leccion_B():
    indice=INDICE_WIKI if MEM=="wiki" else INDICE_VEC
    if not rag.hay_indice(indice):
        falta="generate_wiki.py" if MEM=="wiki" else "build_index.py"
        print(f"{C_R}Falta la memoria '{MEM}'. Corre primero:  python3 {falta}{C_0}"); return
    umbral=float(os.environ.get("RAG_MIN_SCORE","0.6"))   # similitud minima para considerar "esta en el curso"
    print(f"\n{C_S}Modo B (preguntale lo que sea) - memoria: {MEM}. Si no esta en el material, busco en linea. ('menu'=volver){C_0}")
    while True:
        try: q=input(f"\n{C_U}Tu pregunta:{C_0} ").strip()
        except (EOFError,KeyboardInterrupt): print(); return
        if not q: continue
        if q.lower() in ("menu","/menu"): return
        try: scored=rag.buscar_scored(q,k=4,indice=indice)
        except Exception as e:
            print(f"{C_R}Error en la busqueda vectorial: {e}{C_0}"); continue
        top=scored[0][0] if scored else 0.0
        if top>=umbral:
            # La respuesta esta en el contenido del curso.
            chunks=[c for _,c in scored]
            ctx="\n".join(f"[{c['modulo']}] {c['texto']}" for c in chunks)
            print(f"{C_S}(fuentes del curso: {', '.join(c['modulo'] for c in chunks)}){C_0}")
            msgs=[{"role":"system","content":"Eres un tutor de economia bilingue ES/EN. Responde en espanol, claro y breve, usando SOLO el contexto dado. Da el termino en ingles al lado de los conceptos clave."},
                  {"role":"user","content":f"CONTEXTO DEL CURSO:\n{ctx}\n\nPREGUNTA: {q}"}]
            try: print(f"\n{C_T}Tutor:{C_0} {process(ollama(msgs))}\n")
            except Exception as e: print(f"{C_R}Error con Ollama: {e}{C_0}\n")
        else:
            # No esta en el curso -> avisar y buscar en linea, citando el enlace.
            print(f"{C_S}Eso no esta en el material del curso (similitud {top:.2f}). Voy a buscarlo en linea...{C_0}")
            res=ddg_resultados(q,3)
            if not res:
                print(f"{C_R}No pude buscar en linea (sin internet o sin resultados).{C_0}\n"); continue
            ctx="\n".join(f"- {r['title']}: {r['snippet']} (fuente: {r['url']})" for r in res)
            msgs=[{"role":"system","content":"Responde en espanol, claro y breve, usando estos resultados de internet. Aclara que la respuesta viene de la web, no del curso. Termino clave en ingles al lado."},
                  {"role":"user","content":f"RESULTADOS WEB:\n{ctx}\n\nPREGUNTA: {q}"}]
            try: ans=process(ollama(msgs))
            except Exception as e: print(f"{C_R}Error con Ollama: {e}{C_0}\n"); continue
            print(f"\n{C_T}Tutor (web):{C_0} {ans}")
            print(f"{C_S}Referencias:{C_0}")
            for r in res: print(f"  - {r['title']}: {r['url']}")
            print()

# ---------- multiple-choice exam ----------
def examen(mod=None,avanzar=True):
    d=load_prog(); mod=mod or d["modulo_actual"]
    qs=json.load(open(BANCO,encoding="utf-8")).get(mod)
    if not qs: print(f"{C_S}Aun no hay examen para {mod}.{C_0}"); return
    print(f"\n{C_H}== Examen {mod}: {d['modulos'][mod]['titulo']} =={C_0}\n{C_S}Responde a, b, c o d. ('x'=salir){C_0}\n")
    ac=0;tot=len(qs)
    for i,it in enumerate(qs,1):
        print(f"{C_U}{i}. {it['q']}{C_0}")
        # Shuffle the options each time so the correct answer is not always 'a'.
        letras=["a","b","c","d"]
        items=[(k,it["op"][k]) for k in letras if k in it["op"]]
        random.shuffle(items)
        opts={}; correcta=None
        for idx,(orig,txt) in enumerate(items):
            nl=letras[idx]; opts[nl]=txt
            if orig==it["ok"]: correcta=nl     # track where the right answer landed
        for nl in letras:
            if nl in opts: print(f"   {nl}) {opts[nl]}")
        try: r=input(f"{C_U}Tu respuesta:{C_0} ").strip().lower()
        except (EOFError,KeyboardInterrupt): print(); return
        if r=="x": return
        ok=(r==correcta)
        print((f"{C_S}  Correcto. " if ok else f"{C_R}  La correcta era {correcta}) {opts[correcta]}. ")+it['exp']+C_0+"\n")
        log_score(mod,f"quiz-q{i}",100 if ok else 0,"examen" if avanzar else "repaso"); ac+=1 if ok else 0
    pct=round(100*ac/tot); niv=("Novato" if pct<60 else "Aprendiz" if pct<80 else "Competente" if pct<90 else "Dominio")
    print(f"{C_H}Resultado {mod}: {ac}/{tot} = {pct}% -> {niv}{C_0}")
    if avanzar and pct>=80: print(f"{C_S}Aprobado. Desbloqueo el siguiente.{C_0}"); mastered(mod,pct)
    elif avanzar: print(f"{C_S}Necesitas 80% para avanzar.{C_0}")
    else: print(f"{C_S}(Repaso: no cambia tu avance.){C_0}")

# ---------- HTML progress report ----------
def reporte_html(abrir=True):
    d=load_prog();filas="";comp=0
    for k,v in d["modulos"].items():
        est=v["estado"];col={"completado":"#39ff14","pendiente":"#ffd400","bloqueado":"#5a6472"}.get(est,"#5a6472")
        if est=="completado":comp+=1
        filas+=f"<tr><td>{k}</td><td>{html.escape(v['titulo'])}</td><td style='color:{col};font-weight:bold'>{est}</td><td style='text-align:right'>{v['mejor_puntaje']}</td></tr>"
    pct=round(100*comp/len(d["modulos"]));hist=""
    if os.path.exists(CSVF):
        for r in reversed(list(csv.reader(open(CSVF,encoding="utf-8")))[1:][-15:]):
            if len(r)>=4:
                c="#39ff14" if r[3]=="100" else "#ff5c5c" if r[3]=="0" else "#ffd400"
                hist+=f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{html.escape(r[2])}</td><td style='color:{c};text-align:right'>{r[3]}</td></tr>"
    page=f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="8">
<title>Mi avance</title><style>body{{background:#0b0f14;color:#e8f0ff;font-family:system-ui,Arial;margin:0;padding:24px}}
h1{{color:#39d0ff}}h2{{color:#ffd400;margin-top:28px}}.bar{{background:#1a2230;border-radius:10px;height:26px;overflow:hidden;max-width:640px}}
.fill{{background:#39ff14;height:100%;width:{pct}%;color:#07120a;font-weight:bold;text-align:center;line-height:26px}}
table{{border-collapse:collapse;width:100%;max-width:760px;margin-top:10px}}td,th{{border-bottom:1px solid #223;padding:8px 10px;font-size:15px}}th{{color:#9ad;text-align:left}}small{{color:#8aa}}</style></head><body>
<h1>Mi avance — Economia con matematicas</h1>
<small>Alumno: {html.escape(d.get('alumno','Carlos'))} · Ultima sesion: {d.get('ultima_sesion') or '—'} · Modulo actual: {d['modulo_actual']} · <i>se refresca solo cada 8s</i></small>
<h2>Progreso: {comp}/{len(d['modulos'])} modulos</h2><div class="bar"><div class="fill">{pct}%</div></div>
<h2>Modulos</h2><table><tr><th>Mod</th><th>Tema</th><th>Estado</th><th>Mejor</th></tr>{filas}</table>
<h2>Ultimos ejercicios</h2><table><tr><th>Fecha</th><th>Mod</th><th>Ejercicio</th><th>Puntaje</th></tr>{hist or '<tr><td colspan=4><small>sin registros</small></td></tr>'}</table>
</body></html>"""
    open(REPORTE,"w",encoding="utf-8").write(page)
    if abrir:
        print(f"{C_S}Reporte: {REPORTE}{C_0}")
        try: webbrowser.open("file://"+REPORTE)
        except Exception: pass

def autoreporte():
    if os.path.exists(REPORTE):
        try: reporte_html(abrir=False)
        except Exception: pass

# ---------- DuckDuckGo web search (manual) ----------
def _real_url(href):
    """DuckDuckGo wraps result links in a redirect; pull out the real URL."""
    if href.startswith("//"): href="https:"+href
    pr=urllib.parse.urlparse(href); qs=urllib.parse.parse_qs(pr.query)
    return urllib.parse.unquote(qs["uddg"][0]) if "uddg" in qs else href

def ddg_resultados(query,n=3):
    """Return web results as [{title, snippet, url}] (empty list if offline/none)."""
    req=urllib.request.Request("https://html.duckduckgo.com/html/?q="+urllib.parse.quote(query),headers={"User-Agent":"Mozilla/5.0 tutor-local"})
    try: page=urllib.request.urlopen(req,timeout=20).read().decode("utf-8","ignore")
    except Exception: return []
    clean=lambda s: html.unescape(re.sub("<.*?>","",s)).strip()
    pares=re.findall(r'result__a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',page,re.S)
    sn=re.findall(r'result__snippet[^>]*>(.*?)</a>',page,re.S)
    out=[]
    for i,(href,title) in enumerate(pares[:n]):
        t=clean(title)
        if t: out.append({"title":t,"snippet":clean(sn[i]) if i<len(sn) else "","url":_real_url(href)})
    return out

def ddg(query,n=5):
    res=ddg_resultados(query,n)
    if not res: return "(sin internet o sin resultados)"
    return "\n".join(f"{i+1}. {r['title']}\n   {r['snippet']}\n   {r['url']}" for i,r in enumerate(res))

def elegir_modulo():
    d=load_prog();ks=list(d["modulos"].keys())
    print(f"\n{C_H}Elige el modulo:{C_0}")
    for i,k in enumerate(ks,1): print(f"  {C_U}{i:>2}){C_0} {k}: {d['modulos'][k]['titulo']} ({d['modulos'][k]['estado']})")
    try: s=input(f"{C_U}Numero (vacio=cancelar):{C_0} ").strip()
    except (EOFError,KeyboardInterrupt): return None
    return ks[int(s)-1] if s.isdigit() and 1<=int(s)<=len(ks) else None

def repetir():
    mod=elegir_modulo()
    if not mod: return
    print(f"\n{C_H}Repasar {mod}{C_0}  {C_U}1){C_0} Leccion guiada (A)  {C_U}2){C_0} Examen (repaso)")
    o=input(f"{C_U}Elige:{C_0} ").strip()
    if o=="1": leccion_A(mod=mod,avanzar_nota="Es un REPASO; no cambies el avance.")
    elif o=="2": examen(mod=mod,avanzar=False)

def elegir_modo():
    global MODO
    print(f"\n{C_H}¿Como quieres estudiar?{C_0}")
    print(f"  {C_U}A){C_0} Guiado por modulo (lecciones paso a paso, en orden)")
    print(f"  {C_U}B){C_0} Preguntale lo que sea (RAG vectorial sobre todo el curso)")
    s=input(f"{C_U}Elige A o B:{C_0} ").strip().upper()
    MODO="B" if s=="B" else "A"
    print(f"{C_S}Modo: {MODO}{C_0}")

def elegir_memoria():
    global MEM
    print(f"\n{C_H}Tipo de memoria (para el modo B):{C_0}")
    print(f"  {C_U}1){C_0} Vectorial  (pedazos de curso.json)")
    print(f"  {C_U}2){C_0} Wiki LLM   (paginas enlazadas; corre antes: python3 generate_wiki.py)")
    s=input(f"{C_U}Elige 1 o 2:{C_0} ").strip()
    MEM="wiki" if s=="2" else "vectorial"
    print(f"{C_S}Memoria: {MEM}{C_0}")

def menu():
    print(f"\n{C_H}========================================{C_0}")
    print(f"{C_H}   TUTOR DE ECONOMIA  (local) - modo {MODO}{C_0}")
    print(f"{C_H}========================================{C_0}")
    etq="Leccion guiada" if MODO=="A" else "Preguntale lo que sea"
    for n,t in [("1",f"{etq}  (modo {MODO}"+(f", memoria {MEM}" if MODO=="B" else "")+")"),
                ("2","Repetir una leccion o modulo"),("3","Examen de opcion multiple"),
                ("4","Ver mi avance y perfil"),("5","Generar / abrir reporte HTML"),
                ("6","Buscar en internet (DuckDuckGo)"),("7",f"Cambiar modo de estudio (ahora: {MODO})"),
                ("8",f"Cambiar tipo de memoria (ahora: {MEM})"),("9",f"Cambiar modelo ({MODEL})"),("10","Salir")]:
        print(f"  {C_U}{n}){C_0} {t}")
    print(f"{C_H}----------------------------------------{C_0}")

def main():
    global MODEL,MODO
    ensure_progreso()
    print(f"{C_S}Ollama: {HOST}   Modelo: {MODEL}{C_0}")
    elegir_modo()
    while True:
        menu()
        try: op=input(f"{C_U}Elige un numero:{C_0} ").strip()
        except (EOFError,KeyboardInterrupt): op="10"
        if op=="1": leccion_A() if MODO=="A" else leccion_B()
        elif op=="2": repetir()
        elif op=="3": examen()
        elif op=="4":
            print(f"\n{C_S}{avance_txt()}{C_0}")
            student_profile.actualizar_perfil(); print(f"\n{C_T}{student_profile.leer_perfil()}{C_0}")
        elif op=="5": reporte_html(abrir=True)
        elif op=="6":
            q=input(f"{C_U}Que buscar?:{C_0} ").strip()
            if q: print(f"\n{C_S}{ddg(q)}{C_0}")
        elif op=="7": elegir_modo()
        elif op=="8": elegir_memoria()
        elif op=="9":
            nm=input(f"{C_U}Modelo:{C_0} ").strip()
            if nm: MODEL=nm; print(f"{C_S}Modelo -> {MODEL}{C_0}")
        elif op=="10":
            student_profile.actualizar_perfil()
            d=load_prog();d["ultima_sesion"]=datetime.date.today().isoformat();save_prog(d)
            print(f"{C_S}Sesion guardada. Hasta la proxima, Carlos.{C_0}"); break
        else: print(f"{C_R}Escribe un numero del 1 al 10.{C_0}")

if __name__=="__main__": main()
