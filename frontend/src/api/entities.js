import {api} from './client.js';
export const usage={batches:()=>api('/usage/batches'),get:id=>api('/usage/batches/'+id),create:data=>api('/usage/batches',{method:'POST',body:JSON.stringify(data)}),summary:()=>api('/usage/summary')};
export const certificates={list:()=>api('/certificates'),get:id=>api('/certificates/'+id),create:data=>api('/certificates',{method:'POST',body:JSON.stringify(data)}),revoke:(id,effective_at)=>api('/certificates/'+id+'/revoke',{method:'POST',body:JSON.stringify({effective_at})})};
export const claims={list:view=>api('/claims?view='+view),get:id=>api('/claims/'+id),create:data=>api('/claims',{method:'POST',body:JSON.stringify(data)}),reissue:(id,certificate_id)=>api('/claims/'+id+'/reissue',{method:'POST',body:JSON.stringify({certificate_id})})};
export const briefings={plans:()=>api('/briefings/plans'),create:data=>api('/briefings/plans',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/briefings/plans/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/briefings/deliveries'),verification:(customer_id,month)=>api('/verification?customer_id='+customer_id+'&month='+month)};
export const customers={list:()=>api('/customers')};
