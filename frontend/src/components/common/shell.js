import {session} from '../../stores/session.js';
import {workspace} from '../../stores/workspace.js';
import {Role} from '../../constants/enums.js';
import {esc} from '../../utils/dom.js';
export function shell(page,content){
 const m=workspace.meta,nav=[['overview','业务总览'],['usage','用电数据'],['certificates','凭证管理'],['claims','核发中心'],['briefings','月度核验']];
 return '<div class="shell"><aside><a class="brand" href="#/overview"><span class="brand-symbol">'+esc(m.short.split('-').map(s=>s[0]).join('').toUpperCase())+'</span><span>'+esc(m.name)+'</span></a><div class="edition">GREEN LEDGER / 2026</div><nav>'+nav.map((n,i)=>'<a class="'+(page===n[0]?'active':'')+'" href="#/'+n[0]+'"><small>0'+(i+1)+'</small>'+esc(n[1])+'</a>').join('')+'</nav><div class="aside-note"><span>业务现场</span><p>'+esc(m.client)+'</p><span>模拟场景 · 全程留痕</span></div><div class="account"><strong>'+esc(session.user.name)+'</strong><span>'+Role[session.user.role]+'</span><button id="logout" class="text-button">退出登录 ↗</button></div></aside><div class="stage"><header><span>'+esc(m.tagline)+'</span><span class="live-dot">台账与核发队列已连接</span></header><main>'+content+'</main><footer>'+esc(m.short.toUpperCase())+'<span>用电接入 → 凭证核发 → 撤销补发 → 月度核验</span></footer></div></div>';
}
export const heading=(over,title,description,action='')=>'<div class="page-heading"><div><p class="eyebrow">'+esc(over)+'</p><h1>'+esc(title)+'</h1><p class="description">'+esc(description)+'</p></div>'+action+'</div>';
