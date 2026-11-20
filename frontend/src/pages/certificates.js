import {certificates} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {status} from '../components/common/status.js';
import {esc,fmt,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {ClaimStatus,ClaimKind} from '../constants/enums.js';
const CERT_COLS=[{key:'cert_no',label:'凭证号'},{key:'issuer',label:'核发机构'},{key:'month',label:'归属月'},{key:'total_kwh',label:'总量 kWh'},{key:'reserved_kwh',label:'核发中'},{key:'issued_kwh',label:'已核发'},{key:'remaining_kwh',label:'剩余可核发'}];
const CLAIM_COLS=[{key:'id',label:'声明'},{key:'line_code',label:'线体'},{key:'customer_name',label:'客户'},{key:'kwh',label:'电量 kWh'},{key:'kind',label:'类型'},{key:'status',label:'状态'}];
export async function certificates(){
 const list=await certificates.list();workspace.certificates=list;
 const active=list.filter(c=>c.status==='active');
 return heading('03 / CERTIFICATES','绿电凭证管理','登记同月绿电凭证，一张凭证可拆给多家客户。撤销生效后立即停止核发：在途声明取消，已核发份额失效留档。')
 +'<div class="workbench-grid"><section class="panel"><div class="section-title"><h2>登记凭证</h2></div><form id="cert-form"><label>凭证号<input name="cert_no" required minlength="4" placeholder="GE-2026-11-X001"></label><label>核发机构<input name="issuer" required minlength="2" placeholder="华东绿色电力交易中心"></label><div class="parameter-grid"><label>归属月<input name="month" type="month" required></label><label>总量 kWh<input name="total_kwh" type="number" step="any" min="1" required placeholder="100000"></label></div><button type="submit" class="primary" '+(session.user.role==='viewer'?'disabled':'')+'>登记绿电凭证</button></form>'
 +(session.user.role==='admin'?'<div class="section-title"><h2>撤销凭证</h2></div><form id="revoke-form"><label>待撤销凭证<select name="certificate_id" required>'+active.map(c=>'<option value="'+c.id+'">'+esc(c.cert_no)+' · 剩余 '+fmt(c.remaining_kwh)+' kWh</option>').join('')+'</select></label><label>撤销生效日<input name="effective_at" type="date" required></label><button type="submit" class="primary" '+(active.length?'':'disabled')+'>提交撤销（生效后停止核发）</button><p class="hint">生效日 00:00 起停止核发；在途声明取消并释放占用，已核发份额失效，旧声明全部留档。</p></form>':'<p class="hint">撤销凭证需业务负责人操作。</p>')+'</section>'
 +'<section class="panel"><div class="section-title"><h2>凭证台账</h2><span>'+list.length+' 张 · 点击行查看核发明细</span></div><div class="table-wrap"><table><thead><tr>'+CERT_COLS.map(c=>'<th>'+c.label+'</th>').join('')+'<th>状态</th></tr></thead><tbody>'+list.map(c=>'<tr data-cert="'+c.id+'" class="clickable">'+CERT_COLS.map(col=>'<td>'+esc(fmt(c[col.key]))+'</td>').join('')+'<td>'+status(c.status)+(c.revoke_effective_at?'<br><small>'+(c.status==='revoked'?'生效 ':'待生效 ')+date(c.revoke_effective_at)+'</small>':'')+'</td></tr>').join('')+'</tbody></table></div><div id="cert-detail"></div></section></div>';
}
async function showCert(id){
 const c=await certificates.get(id);
 const rows=c.claims.map(cl=>({...cl,kind:ClaimKind[cl.kind]||cl.kind,status:ClaimStatus[cl.status]||cl.status}));
 document.querySelector('#cert-detail').innerHTML='<div class="section-title"><h2>'+esc(c.cert_no)+' 的核发明细</h2><span>'+c.claims.length+' 条声明 · 剩余 '+fmt(c.remaining_kwh)+' kWh</span></div>'+table(CLAIM_COLS,rows,'该凭证尚无核发声明。');
}
export function bindCertificates(refresh){
 submit(document.querySelector('#cert-form'),async f=>{await certificates.create({cert_no:f.get('cert_no'),issuer:f.get('issuer'),month:f.get('month'),total_kwh:Number(f.get('total_kwh'))});notify('凭证已登记，可前往核发中心申领');await refresh();});
 const revokeForm=document.querySelector('#revoke-form');
 if(revokeForm)submit(revokeForm,async f=>{await certificates.revoke(Number(f.get('certificate_id')),f.get('effective_at'));notify('撤销已提交，生效后停止核发');await refresh();});
 document.querySelectorAll('[data-cert]').forEach(row=>row.onclick=()=>showCert(row.dataset.cert).catch(e=>notify(e.message,true)));
}
