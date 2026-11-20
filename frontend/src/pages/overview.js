import {api} from '../api/client.js';
import {workspace} from '../stores/workspace.js';
import {heading} from '../components/common/shell.js';
import {chart} from '../components/common/chart.js';
import {esc,fmt,date} from '../utils/dom.js';
export async function overview(){
 const [o,audits]=await Promise.all([api('/overview'),api('/audits')]),m=workspace.meta;
 const t=o.totals||{},pct=t.usage_kwh?Math.round(t.green_kwh/t.usage_kwh*1000)/10:0;
 const summary=o.latest_month?o.latest_month+' 三家客户实测 '+fmt(t.usage_kwh)+' kWh，已核发绿电 '+fmt(t.green_kwh)+' kWh（'+pct+'%），其余按普通用电入账。':'先导入线体实测日耗，再登记同月绿电凭证核发声明。';
 const bar=o.per_line?.length?{type:'bar',labels:o.per_line.map(l=>l.line_code),series:[{name:'绿电 kWh',values:o.per_line.map(l=>l.green_kwh)},{name:'普通用电 kWh',values:o.per_line.map(l=>l.regular_kwh)}]}:null;
 return heading('01 / MONTHLY CHECK',m.name,m.workflow,'<a class="button primary" href="#/claims">'+esc('前往核发中心')+' ↗</a>')
 +'<section class="overview-hero"><div class="narrative"><p class="eyebrow">当月核验口径</p><h2>'+esc(summary)+'</h2><p>'+esc(m.upstream)+' → '+esc(m.downstream)+'</p><a href="#/briefings" class="text-link">查看月度核验与简报归档 ↗</a></div><div class="numbers">'+[['用电记录',o.usage_records],['有效凭证',o.certificates],['待核发声明',o.claims_pending],['待补发份额',o.reissue_pending]].map(([k,v])=>'<div><span>'+k+'</span><strong>'+v+'</strong></div>').join('')+'</div></section>'
 +'<section class="panel"><div class="section-title"><h2>'+esc(o.latest_month||'')+' 各线绿电与普通用电</h2><span>绿电=有效已核发 · 失效份额已扣减</span></div>'+chart(bar)+'</section>'
 +'<div class="two-columns"><section class="panel"><div class="section-title"><h2>今天需要回答</h2></div><ol class="questions">'+m.pains.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ol></section><section class="panel"><div class="section-title"><h2>最近动作</h2><span>可追溯记录</span></div><ul class="timeline">'+audits.slice(0,5).map(a=>'<li><strong>'+esc(a.action)+'</strong><span>'+esc(a.actor)+' · '+date(a.at)+'</span></li>').join('')+'</ul></section></div>';
}
