import {claims,certificates,customers} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {status} from '../components/common/status.js';
import {esc,fmt,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {ClaimKind,CertStatus} from '../constants/enums.js';
const TABS=[['pending','待核发'],['issued','已核发'],['reissue','待补发']];
const COLS={pending:[{key:'id',label:'声明'},{key:'cert_no',label:'凭证号'},{key:'line_code',label:'线体'},{key:'customer_name',label:'客户'},{key:'month',label:'归属月'},{key:'kwh',label:'电量 kWh'},{key:'kind',label:'类型'},{key:'created_at',label:'提交时间'}],
issued:[{key:'id',label:'声明'},{key:'cert_no',label:'凭证号'},{key:'line_code',label:'线体'},{key:'customer_name',label:'客户'},{key:'month',label:'归属月'},{key:'kwh',label:'电量 kWh'},{key:'kind',label:'类型'},{key:'issued_at',label:'核发时间'}],
reissue:[{key:'id',label:'原声明'},{key:'cert_no',label:'原凭证（已撤销）'},{key:'line_code',label:'线体'},{key:'customer_name',label:'客户'},{key:'month',label:'归属月'},{key:'kwh',label:'失效份额 kWh'},{key:'reissue_state',label:'补发状态'}]};
function rowsOf(list,view){
 return list.map(c=>({...c,kind:ClaimKind[c.kind]||c.kind,created_at:c.created_at?date(c.created_at):'—',issued_at:c.issued_at?date(c.issued_at):'—'}));
}
function grid(list,view){
 if(!list.length)return '<div class="empty">该队列暂无声明。</div>';
 return '<div class="table-wrap"><table><thead><tr>'+COLS[view].map(c=>'<th>'+c.label+'</th>').join('')+'</tr></thead><tbody>'+rowsOf(list,view).map(c=>'<tr data-claim="'+c.id+'" class="clickable">'+COLS[view].map(col=>'<td>'+esc(fmt(c[col.key]))+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
}
export async function claimsPage(id){
 if(id&&!TABS.some(t=>t[0]===id))return claimDetail(Number(id));
 const tab=TABS.some(t=>t[0]===id)?id:'pending';
 const [list,certs,custs]=await Promise.all([claims.list(tab),certificates.list(),customers.list()]);
 workspace.certificates=certs;workspace.customers=custs;
 const active=certs.filter(c=>c.status==='active'&&c.remaining_kwh>0);
 if(!workspace.idempotencyKey)workspace.idempotencyKey='web-'+Date.now()+'-'+Math.random().toString(36).slice(2,10);
 const lineOptions=custs.map(cu=>'<optgroup label="'+esc(cu.name)+'">'+cu.lines.map(l=>'<option value="'+l.id+'">'+esc(l.code)+' · '+esc(l.name)+'</option>').join('')+'</optgroup>').join('');
 return heading('04 / ISSUANCE','核发中心','提交核发声明：同月凭证、同线当月实测双重校验，凭证与线体当月电量都不能超领。后台队列核发，重试不会重复占量。')
 +'<div class="workbench-grid"><section class="panel"><div class="section-title"><h2>新建核发声明</h2></div><form id="claim-form"><label>绿电凭证（仅显示有效且有剩余）<select name="certificate_id" required>'+active.map(c=>'<option value="'+c.id+'">'+esc(c.cert_no)+' · '+esc(c.month)+' · 剩余 '+fmt(c.remaining_kwh)+' kWh</option>').join('')+'</select></label><label>用电线体<select name="line_id" required>'+lineOptions+'</select></label><div class="parameter-grid"><label>核发电量 kWh<input name="kwh" type="number" step="any" min="0.001" required placeholder="10000"></label><label>备注<input name="note" maxlength="300" placeholder="例如：10 月月度核发"></label></div><input type="hidden" name="idempotency_key" value="'+workspace.idempotencyKey+'"><button type="submit" class="primary" '+(session.user.role==='viewer'||!active.length?'disabled':'')+'>提交核发声明 ↗</button><p class="hint">声明归属月与凭证一致；提交即占用凭证与线体当月份额，后台按队列核发。重复提交同一表单不会重复占量。</p></form></section>'
 +'<section class="panel"><div class="section-title"><h2>核发队列</h2><span>点击行追溯凭证与用电记录</span></div><div class="tabs">'+TABS.map(t=>'<a class="tab '+(tab===t[0]?'active':'')+'" href="#/claims/'+t[0]+'">'+t[1]+'</a>').join('')+'</div>'+grid(list,tab)+'</section></div>';
}
async function claimDetail(id){
 const c=await claims.get(id);
 const certs=await certificates.list();workspace.certificates=certs;
 const chain=c.chain||[],isTip=c.status==='invalidated'&&!chain.some(n=>n.replaces_id===c.id&&['pending','issued','invalidated'].includes(n.status));
 const replacements=certs.filter(x=>x.status==='active'&&x.month===c.month&&x.remaining_kwh>=c.kwh);
 const usageCols=[{key:'day',label:'日期'},{key:'kwh',label:'实测日电耗 kWh'}];
 const chainCols=[{key:'id',label:'声明'},{key:'kind',label:'类型'},{key:'cert_no',label:'凭证号'},{key:'kwh',label:'电量 kWh'},{key:'status',label:'状态'},{key:'created_at',label:'提交时间'}];
 const chainRows=chain.map(n=>({...n,kind:ClaimKind[n.kind]||n.kind,created_at:date(n.created_at)}));
 return heading('04 / ISSUANCE','核发声明 #'+c.id,'追溯到凭证、补发链与线体当月每一条实测日耗。','<a class="button" href="#/claims">返回核发中心 ↗</a>')
 +'<section class="result-lead"><p class="eyebrow">CLAIM</p><h2>'+esc(c.line_code)+' · '+esc(c.month)+' · '+fmt(c.kwh)+' kWh '+status(c.status)+'</h2><div class="metrics">'
 +[['类型',ClaimKind[c.kind]||c.kind],['客户',c.customer_name],['凭证',c.cert_no],['提交',date(c.created_at)],['核发',c.issued_at?date(c.issued_at):'—']].map(([k,v])=>'<div><span>'+k+'</span><strong class="metric-text">'+esc(fmt(v))+'</strong></div>').join('')+'</div>'
 +(c.note?'<p class="hint">备注：'+esc(c.note)+'</p>':'')+'</section>'
 +(isTip?'<section class="panel"><div class="section-title"><h2>换证补发</h2><span>只补失效份额 '+fmt(c.kwh)+' kWh</span></div><form id="reissue-form" class="reissue-form"><label>换发凭证（同月、有效、余量充足）<select name="certificate_id" required>'+replacements.map(x=>'<option value="'+x.id+'">'+esc(x.cert_no)+' · 剩余 '+fmt(x.remaining_kwh)+' kWh</option>').join('')+'</select></label><button type="submit" class="primary" '+(session.user.role==='viewer'||!replacements.length?'disabled':'')+'>补发失效份额（'+fmt(c.kwh)+' kWh）↗</button><p class="hint">补发金额固定为失效份额；同一失效份额最多一个在途补发，重试不重复占量。</p></form></section>':'')
 +'<div class="two-columns"><section class="panel"><div class="section-title"><h2>凭证台账</h2></div>'+(c.certificate?'<div class="kv-grid">'+[['凭证号',c.certificate.cert_no],['核发机构',c.certificate.issuer],['归属月',c.certificate.month],['总量 kWh',fmt(c.certificate.total_kwh)],['已核发 kWh',fmt(c.certificate.issued_kwh)],['核发中 kWh',fmt(c.certificate.reserved_kwh)],['剩余 kWh',fmt(c.certificate.remaining_kwh)],['状态',CertStatus[c.certificate.status]||c.certificate.status]].map(([k,v])=>'<div><span>'+k+'</span><strong>'+esc(fmt(v))+'</strong></div>').join('')+'</div>':'')+'<div class="section-title"><h2>补发链</h2><span>同一失效份额沿链下移</span></div>'+table(chainCols,chainRows)+'</section>'
 +'<section class="panel"><div class="section-title"><h2>'+esc(c.line_code)+' · '+esc(c.month)+' 实测日耗</h2><span>'+(c.usage_records||[]).length+' 天 · 台账：实测 '+fmt(c.line_month?.usage_kwh)+' / 核发中 '+fmt(c.line_month?.reserved_kwh)+' / 已核发 '+fmt(c.line_month?.issued_kwh)+' kWh</span></div>'+table(usageCols,c.usage_records||[])+'</section></div>';
}
export function bindClaims(refresh){
 const form=document.querySelector('#claim-form');
 if(form)submit(form,async f=>{const c=await claims.create({certificate_id:Number(f.get('certificate_id')),line_id:Number(f.get('line_id')),kwh:Number(f.get('kwh')),note:f.get('note')||'',idempotency_key:f.get('idempotency_key')});workspace.idempotencyKey=null;notify('声明 #'+(c.id)+' 已提交，后台核发中');if(location.hash==='#/claims/pending')await refresh();else location.hash='#/claims/pending';});
 const reissue=document.querySelector('#reissue-form');
 if(reissue)submit(reissue,async f=>{const id=location.hash.split('/').pop();const c=await claims.reissue(Number(id),Number(f.get('certificate_id')));notify('补发声明 #'+c.id+' 已提交，只补失效份额');await refresh();});
 document.querySelectorAll('[data-claim]').forEach(row=>row.onclick=()=>{location.hash='#/claims/'+row.dataset.claim;});
}
