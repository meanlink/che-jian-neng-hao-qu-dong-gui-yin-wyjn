/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} UsageBatch */
/** @typedef {{id:number,cert_no:string,issuer:string,month:string,total_kwh:number,reserved_kwh:number,issued_kwh:number,remaining_kwh:number,status:string}} Certificate */
/** @typedef {{id:number,cert_no:string,line_code:string,month:string,kwh:number,kind:string,status:string,replaces_id:number|null,root_id:number}} Claim */
/** @typedef {{id:number,name:string,customer_id:number,month:string,destination:string,next_run:number,enabled:boolean}} BriefingPlan */
export {};
