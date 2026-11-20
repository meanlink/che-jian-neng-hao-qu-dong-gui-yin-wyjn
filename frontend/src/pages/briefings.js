import {briefings,customers} from '../api/entities.js';
import {download} from '../api/client.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {esc,fmt,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
export async function briefingsPage(){
 const [plans,deliveries,custs]=await Promise.all([briefings.plans(),briefings.deliveries(),customers.list()]);
 workspace.customers=custs;
 const m=workspace.meta;
 return heading('05 / MONTHLY BRIEFING','月度核验与简报归档','按月核验各线绿电：绿电=有效已核发，未匹配部分为普通用电，撤销凭证只扣失效份额。简报由后台 worker 生成快照并留档。','<button class="button" id="refresh-briefings">刷新收件箱 ↻</button>')
 +'<div class="report-grid"><section class="panel"><div class="section-title"><h2>按月核验</h2></div><form id="verify-form"><label>客户<select name="customer_id">'+custs.map(c=>'<option value="'+c.id+'">'+esc(c.name)+'</option>').join('')+'</select></label><label>归属月<input name="month" type="month" value="2026-10" required></label><button type="submit" class="primary">核验该月绿电 ↗</button></form><div id="verify-result"></div>'
 +(session.user.role==='admin'?'<div class="section-title"><h2>创建简报计划</h2></div><form id="plan-form"><label>简报名称<input name="name" required minlength="2" value="月度绿电核验简报"></label><label>客户<select name="customer_id">'+custs.map(c=>'<option value="'+c.id+'">'+esc(c.name)+'</option>').join('')+'</select></label><label>归属月<input name="month" type="month" value="2026-10" required></label><label>业务接收组<input name="destination" value="客户能源部 · 本地收件箱" required></label><div class="parameter-grid"><label>分发周期<select name="interval_seconds"><option value="86400">每日</option><option value="604800">每周</option><option value="60">每分钟（验收）</option></select></label><label>首次执行<select name="delay_seconds"><option value="0">立即</option><option value="60">1 分钟后</option><option value="3600">1 小时后</option></select></label></div><button type="submit" class="primary">保存简报计划</button><p class="hint">由后台 worker 按到期时间生成快照文件；仅负责人可创建或暂停。</p></form>':'<p class="hint">简报计划由业务负责人维护。</p>')+'</section>'
 +'<section><div class="section-title"><h2>运行中的计划</h2><span>'+plans.filter(p=>p.enabled).length+' 条已启用</span></div><div class="schedule-list">'+plans.map(p=>'<article><div><strong>'+esc(p.name)+'</strong><p>'+esc(p.customer_name)+' · '+esc(p.month)+' → '+esc(p.destination)+'</p><small>下次 '+date(p.next_run)+' · 周期 '+p.interval_seconds+' 秒</small></div><button class="button small" data-toggle="'+p.id+'" '+(session.user.role!=='admin'?'disabled':'')+'>'+(p.enabled?'暂停':'启用')+'</button></article>').join('')+'</div>'
 +'<section class="panel inbox"><div class="section-title"><h2>本地收件箱</h2><span>'+deliveries.length+' 份归档</span></div>'+deliveries.map(d=>'<div class="delivery"><div><strong>'+esc(d.filename)+'</strong><p>'+esc(d.destination)+' · '+date(d.created_at)+'</p><small>SHA256 '+esc(d.checksum.slice(0,24))+'…</small></div><div><button class="text-button" data-download="'+d.id+'" data-format="csv">CSV ↓</button><button class="text-button" data-download="'+d.id+'" data-format="json">JSON ↓</button></div></div>').join('')+(!deliveries.length?'<p class="empty">计划执行后，简报文件会出现在此处。等待片刻后刷新。</p>':'')+'</section></section></div>';
}
function renderVerification(v){
 const m=workspace.meta;
 const certRows=v.certificates.map(c=>({cert_no:c.cert_no,issuer:c.issuer,kwh:c.kwh}));
 const certCols=[{key:'cert_no',label:'凭证号'},{key:'issuer',label:'核发机构'},{key:'kwh',label:'有效核发 kWh'}];
 const t=v.totals;
 return '<div class="section-title"><h2>'+esc(v.customer.name)+' · '+esc(v.month)+'</h2><span>绿电占比 '+(t.usage_kwh?Math.round(t.green_kwh/t.usage_kwh*1000)/10:0)+'%</span></div>'
 +table(m.verification_columns,v.lines,'该客户当月无用电记录。')
 +'<p class="hint">合计：实测 '+fmt(t.usage_kwh)+' / 绿电 '+fmt(t.green_kwh)+' / 普通 '+fmt(t.regular_kwh)+' / 核发中 '+fmt(t.reserved_kwh)+' / 失效扣减 '+fmt(t.invalidated_kwh)+' kWh。简报只扣失效份额，已补发份额重新计入绿电。</p>'
 +'<div class="section-title"><h2>涉及凭证</h2></div>'+table(certCols,certRows,'当月无有效核发凭证。');
}
export function bindBriefings(refresh){
 document.querySelector('#refresh-briefings').onclick=refresh;
 submit(document.querySelector('#verify-form'),async f=>{const v=await briefings.verification(Number(f.get('customer_id')),f.get('month'));document.querySelector('#verify-result').innerHTML=renderVerification(v);});
 const planForm=document.querySelector('#plan-form');
 if(planForm)submit(planForm,async f=>{await briefings.create({name:f.get('name'),customer_id:Number(f.get('customer_id')),month:f.get('month'),destination:f.get('destination'),interval_seconds:Number(f.get('interval_seconds')),delay_seconds:Number(f.get('delay_seconds'))});notify('简报计划已保存，后台将按到期时间归档');await refresh();});
 document.querySelectorAll('[data-toggle]').forEach(b=>b.onclick=async()=>{try{await briefings.toggle(b.dataset.toggle);await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-download]').forEach(b=>b.onclick=()=>download(b.dataset.download,b.dataset.format).catch(e=>notify(e.message,true)));
}
