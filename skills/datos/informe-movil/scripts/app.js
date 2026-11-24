/* Informe v2 · interacciones mínimas. Todo el contenido existe sin JS; esto solo mejora. */
(()=>{const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)],R=document.documentElement;
let st=null;try{st=window.localStorage}catch(e){}
const h=(location.hash||'').slice(1);let V=/^[ABC]/.test(h)?h[0]:($('.vista')||{id:'vista-A'}).id.slice(-1);
if(/-l$/.test(h))R.dataset.t='light';else{try{const t=st&&st.getItem('vd_t');if(t)R.dataset.t=t}catch(e){}}
function ver(l,noscroll){V=l;$$('.vista').forEach(v=>v.hidden=v.id!=='vista-'+l);$$('.seg button').forEach(b=>b.classList.toggle('on',b.dataset.v===l));document.body.dataset.v=l;$$('.fi-v').forEach(f=>f.hidden=f.dataset.v!==l);
 try{history.replaceState(null,'','#'+l+(R.dataset.t==='light'?'-l':''))}catch(e){}if(!noscroll)scrollTo(0,0);cuenta()}
$$('.seg button').forEach(b=>b.onclick=()=>ver(b.dataset.v));
const inf=$('#info'),fp=$('#fip');if(inf)inf.onclick=()=>{fp.hidden=!fp.hidden;inf.setAttribute('aria-expanded',String(!fp.hidden))};
const tb=$('#tema');function icono(){const u=tb&&$('use',tb);if(u)u.setAttribute('href',R.dataset.t==='light'?'#i-moon':'#i-sun')}
if(tb){icono();tb.onclick=()=>{const t=R.dataset.t==='light'?'dark':'light';R.dataset.t=t;try{st&&st.setItem('vd_t',t)}catch(e){}icono()}}
$$('[data-todo]').forEach(b=>b.onclick=()=>{const v=b.closest('.vista'),ab=b.dataset.on!=='1';$$('details.dt,details.cap',v).forEach(d=>d.open=ab);b.dataset.on=ab?'1':'0';b.querySelector('span').textContent=ab?'Plegar todo':'Abrir todo'});
document.addEventListener('click',e=>{const t=e.target.closest('[data-ir]');if(!t)return;const id=t.dataset.ir,el=document.getElementById(id);if(!el)return;
 const p=t.closest('.sheet');if(p)cerrar();const pg=el.closest('.pgs>section');if(pg)pagina(pg.id.split('-pg-')[1]);if(el.tagName==='DETAILS')el.open=true;el.scrollIntoView({behavior:'smooth',block:'start'})});
/* A · seguimiento de sección */
if('IntersectionObserver'in window){const io=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){const tab=x.target.dataset.tab;$$('#vista-A .bn button').forEach(b=>b.classList.toggle('on',b.dataset.tab===tab))}}),{rootMargin:'-35% 0px -60% 0px'});
 $$('#vista-A .cap[data-tab]').forEach(s=>io.observe(s))}
/* C · páginas */
function pagina(t){$$('#vista-C .pgs>section').forEach(s=>s.classList.toggle('on',s.id==='C-pg-'+t));$$('#vista-C .bn button').forEach(b=>b.classList.toggle('on',b.dataset.pg===t));scrollTo(0,0)}
$$('[data-pg]').forEach(b=>b.onclick=()=>pagina(b.dataset.pg));
/* B · hojas */
const sh=$('#hoja');let hi=-1,foco=null;
function abrir(i){const bs=$$('.shb',sh);if(i<0||i>=bs.length)return;hi=i;bs.forEach((b,k)=>b.hidden=k!==i);$('.pn h2',sh).textContent=bs[i].dataset.t;$('.bd',sh).scrollTop=0;const N=bs.length,pv=$('.prev',sh),nx=$('.next',sh);$('.pos',sh).textContent=(i+1)+' de '+N;pv.disabled=i===0;nx.disabled=i===N-1;$('b',pv).textContent=i>0?bs[i-1].dataset.t:'Es la primera';$('b',nx).textContent=i<N-1?bs[i+1].dataset.t:'Es la última';$('.nv',sh).hidden=N<2;
 if(!sh.classList.contains('on')){sh.classList.add('on');document.body.style.overflow='hidden';try{history.pushState({h:1},'')}catch(e){}foco=document.activeElement;const pn=$('.pn',sh);pn.setAttribute('tabindex','-1');pn.focus({preventScroll:true})}}
function cerrar(){if(!sh||!sh.classList.contains('on'))return;sh.classList.remove('on');document.body.style.overflow='';hi=-1;if(foco)foco.focus()}
if(sh){$$('[data-sh]').forEach(b=>b.onclick=()=>abrir(+b.dataset.sh));$$('.cierra,.bk',sh).forEach(b=>b.onclick=()=>{cerrar();try{if(history.state&&history.state.h)history.back()}catch(e){}});
 $('.prev',sh).onclick=()=>abrir(hi-1);$('.next',sh).onclick=()=>abrir(hi+1);addEventListener('keydown',e=>{if(e.key==='Escape')cerrar()});addEventListener('popstate',cerrar)}
/* decisiones */
const cmp=$('#cmp');
function cuenta(){const v=$('#vista-'+V);if(!v||!cmp)return;const ds=$$('.dc',v).filter(d=>$('.op',d)),n=ds.filter(d=>$('.op.sel',d)).length;cmp.hidden=!(ds.length&&n);if(n)$('span',cmp).textContent='Copiar respuestas ('+n+' de '+ds.length+')'}
function texto(){const v=$('#vista-'+V),t=[document.title];$$('.dc',v).forEach(d=>{const o=$('.op.sel',d);if(o)t.push(d.dataset.d+': '+o.dataset.r)});return t.join('\n')}
document.addEventListener('click',e=>{const o=e.target.closest('.op');if(!o)return;const d=o.dataset.d,k=o.dataset.o;
 $$('.op[data-d="'+d+'"]').forEach(x=>x.classList.toggle('sel',x.dataset.o===k));$$('.dc[data-d="'+d+'"]').forEach(c=>{c.classList.add('hasr');$('.rsp',c).textContent='Se enviará: '+o.dataset.r});cuenta()});
/* copiar: primero la vía síncrona (la que iOS y los archivos locales aceptan dentro del toque), luego la moderna, y si ambas fallan, cuadro con COPIAR */
function viejo(txt,el){const t=el||Object.assign(document.createElement('textarea'),{value:txt});
 if(!el){t.setAttribute('readonly','');t.style.cssText='position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;font-size:16px';document.body.appendChild(t)}
 let ok=false;try{const r=document.createRange();r.selectNodeContents(t);const s=getSelection();s.removeAllRanges();s.addRange(r);t.focus({preventScroll:true});t.select();t.setSelectionRange(0,t.value.length);ok=document.execCommand('copy')}catch(e){}
 if(!el)t.remove();return ok}
function moderno(txt){try{return navigator.clipboard.writeText(txt).then(()=>true,()=>false)}catch(e){return Promise.resolve(false)}}
function marca(b,t){const s=$('span',b)||b;if(!s.dataset.o)s.dataset.o=s.textContent;s.textContent=t;clearTimeout(b._t);b._t=setTimeout(()=>{s.textContent=s.dataset.o;delete s.dataset.o},1800)}
const mod=$('#mod');
function abrirMod(txt,tit){mod._txt=txt;const ta=$('textarea',mod);ta.value=txt;$('.bt',mod).textContent=tit||'Copiar texto';$('.mfail',mod).hidden=true;const c=$('#modc');if(c.firstElementChild){delete c.firstElementChild.dataset.o;c.firstElementChild.textContent='COPIAR'}
 mod.classList.add('on');try{ta.focus({preventScroll:true});ta.select()}catch(e){}}
function cerrarMod(){mod.classList.remove('on')}
function copiar(txt,b,tit){if(viejo(txt)){marca(b,'Copiado');return}moderno(txt).then(ok=>ok?marca(b,'Copiado'):abrirMod(txt,tit))}
if(cmp)$('button',cmp).onclick=e=>copiar(texto(),e.currentTarget,'Copiar respuestas');
if(mod){const c=$('#modc');c.onclick=()=>{const ta=$('textarea',mod);if(viejo(mod._txt,ta))marca(c,'COPIADO ✓');else moderno(mod._txt).then(ok=>{if(ok)marca(c,'COPIADO ✓');else $('.mfail',mod).hidden=false})};
 $('.mx',mod).onclick=cerrarMod;mod.addEventListener('click',e=>{if(e.target===mod)cerrarMod()});addEventListener('keydown',e=>{if(e.key==='Escape')cerrarMod()})}
$$('[data-copia]').forEach(b=>b.onclick=()=>copiar(b.dataset.copia,b,'Copiar texto'));
$$('[data-cp]').forEach(b=>b.onclick=()=>{const bx=b.closest('.cpb,.arf'),el=$('pre,code.rp',bx);if(el)copiar(el.textContent.trim(),b,'Copiar texto')});
$$('code.rp').forEach(c=>c.onclick=()=>c.classList.toggle('ab'));
$$('.cpb pre').forEach(p=>p.onclick=()=>{const r=document.createRange();r.selectNodeContents(p);const s=getSelection();s.removeAllRanges();s.addRange(r)});
$$('.abw input').forEach(i=>i.oninput=()=>{const w=i.parentElement;$('.abd',w).style.clipPath='inset(0 0 0 '+i.value+'%)';w.style.setProperty('--x',i.value+'%')});
/* tablas ordenables */
$$('.tw th[data-s]').forEach(th=>th.onclick=()=>{const t=th.closest('table'),i=[...th.parentNode.children].indexOf(th),asc=th.dataset.d!=='a',tb=t.tBodies[0],n=s=>{const x=parseFloat(s.replace(/\./g,'').replace(',','.').replace(/[^0-9.\-]/g,''));return isNaN(x)?s:x};
 [...tb.rows].sort((a,b)=>{const x=n(a.cells[i].textContent),y=n(b.cells[i].textContent);return(typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y),'es'))*(asc?1:-1)}).forEach(r=>tb.appendChild(r));
 $$('th',t).forEach(o=>delete o.dataset.d);th.dataset.d=asc?'a':'d'});
/* v2.2 · medios: suena uno a la vez, minutos que saltan al punto y A/B en el mismo punto */
document.addEventListener('play',e=>{$$('audio,video').forEach(m=>{if(m!==e.target)m.pause()})},true);
function irA(m,t,seguir){const go=()=>{try{m.currentTime=t}catch(e){}if(seguir){const p=m.play();if(p&&p.catch)p.catch(()=>{})}};m.readyState>=1?go():(m.addEventListener('loadedmetadata',go,{once:true}),m.load())}
$$('[data-seek]').forEach(b=>b.onclick=()=>{const g=b.closest('.mdx'),m=(g&&$('.mdp.on audio,.mdp.on video',g))||document.getElementById(b.dataset.para)||(g&&$('audio,video',g));if(m)irA(m,+b.dataset.seek,true)});
function quien(p){const e=$('.mdh b',p);return e?e.textContent:'otra pista'}
$$('[data-ab-sw]').forEach(b=>b.onclick=()=>{const g=b.closest('.mdx'),ps=$$('.mdp',g),i=Math.max(0,ps.findIndex(p=>p.classList.contains('on'))),k=(i+1)%ps.length,a=$('audio,video',ps[i]),n=$('audio,video',ps[k]);if(!a||!n)return;
 const t=a.currentTime,sonaba=!a.paused;a.pause();ps[i].classList.remove('on');ps[k].classList.add('on');const st=$('[data-ab-st]',g);if(st)st.textContent='Suena: '+quien(ps[k]);irA(n,t,sonaba)});
$$('[data-ab]').forEach(g=>{const st=$('[data-ab-st]',g),p=$('.mdp.on',g);if(st&&p)st.textContent='Suena: '+quien(p)});
ver(V,true);if(V==='C')pagina((window.__c0)||'resumen');
})();
