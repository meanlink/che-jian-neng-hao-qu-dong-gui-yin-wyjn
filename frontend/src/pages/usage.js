import {usage} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {esc,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {parseCSV} from '../utils/csv.js';
const SUMMARY_COLS=[{key:'month',label:'归属月'},{key:'line_code',label:'线体'},{key:'customer',label:'客户'},{key:'usage_kwh',label:'实测 kWh'},{key:'reserved_kwh',label:'核发中 kWh'},{key:'issued_kwh',label:'已核发绿电 kWh'},{key:'regular_kwh',label:'普通用电 kWh'}];
export async function usagePage(){
 const [batches,summary]=await Promise.all([usage.batches(),usage.summary()]);
 workspace.batches=batches;
 let selected=batches[0]?await usage.get(batches[0].id):null,m=workspace.meta;
 return heading('02 / METER INTAKE','用电数据接入','导入各线体实测日耗。同一线体同一天只能入库一次；批次保留来源与内容指纹，核发声明可追溯到每一条用电记录。')
 +'<div class="dataset-grid"><section class="panel"><div class="section-title"><h2>用电批次</h2><span>'+batches.length+' 批</span></div><div class="batch-list">'+batches.map(b=>'<button class="batch-item" data-batch="'+b.id+'"><strong>'+esc(b.name)+'</strong><span>'+b.rows+' 条 · '+esc(b.source)+'</span><small>SHA256 '+esc(b.checksum.slice(0,18))+'…</small></button>').join('')+'</div>'
 +'<div class="section-title"><h2>接入新数据</h2></div><form id="usage-form"><label>批次名称<input name="name" required minlength="2" placeholder="例如：11 月上旬抄表批次"></label><label>上传 CSV 或 JSON<input type="file" id="file-input" accept=".json,.csv"></label><label>记录 JSON<textarea name="records" rows="6" placeholder=\'[{"day":"2026-11-01","line":"P01","kwh":3720.5}]\' required></textarea></label><p class="hint">字段：day / line / kwh。线体编码须已存在，日线耗 0–10 亿 kWh。</p><button type="submit" class="primary" '+(session.user.role==='viewer'?'disabled':'')+'>校验并接入批次</button></form></section>'
 +'<section class="panel"><div class="section-title"><h2 id="preview-name">'+esc(selected?.name||'尚无批次')+'</h2><span>预览前 30 条</span></div><div id="data-preview">'+table(m.usage_columns,selected?.records.slice(0,30)||[])+'</div><div class="section-title"><h2>线体月度台账</h2><span>核发占用与绿电口径</span></div>'+table(SUMMARY_COLS,summary)+'</section></div>';
}
export function bindUsage(refresh){
 let source='manual.json';
 document.querySelector('#file-input').addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file)return;source=file.name;const text=await file.text(),records=file.name.endsWith('.csv')?parseCSV(text):JSON.parse(text);document.querySelector('[name=records]').value=JSON.stringify(records,null,2);}catch(error){notify(error.message,true);}});
 document.querySelectorAll('[data-batch]').forEach(button=>button.onclick=async()=>{try{const b=await usage.get(button.dataset.batch);document.querySelector('#preview-name').textContent=b.name;document.querySelector('#data-preview').innerHTML=table(workspace.meta.usage_columns,b.records.slice(0,30));}catch(error){notify(error.message,true);}});
 submit(document.querySelector('#usage-form'),async f=>{await usage.create({name:f.get('name'),source,records:JSON.parse(f.get('records'))});notify('用电数据已接入，月度台账已更新');await refresh();});
}
