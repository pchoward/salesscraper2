// Bounded suite groups on independent CI VMs; only navigation runs two at once.
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const {PLAN,CONCURRENCY}=require('./browser_plan.cjs');
async function runTask(task,site,out,{cwd=__dirname,timeoutMs=15*60*1000}={}){
 const started=Date.now();let timedOut=false;
 const result=await new Promise(resolve=>{
  const child=spawn(process.execPath,[path.resolve(cwd,task.script),site,path.join(out,task.output),...task.args],{
   env:{...process.env,...task.env},stdio:'inherit',detached:process.platform!=='win32'});
  let killTimer;
  const kill=signal=>{try{if(process.platform==='win32')child.kill(signal);else process.kill(-child.pid,signal);}catch(_){}};
  const timer=setTimeout(()=>{timedOut=true;kill('SIGTERM');killTimer=setTimeout(()=>kill('SIGKILL'),3000);},timeoutMs);
  child.on('error',error=>{clearTimeout(timer);clearTimeout(killTimer);resolve({code:null,error:error.message});});
  child.on('close',(code,signal)=>{clearTimeout(timer);clearTimeout(killTimer);resolve({code,signal});});
 });
 return {id:task.id,status:result.code===0&&!timedOut?'pass':'fail',duration_ms:Date.now()-started,timed_out:timedOut,...result};
}
async function runShard(name,site,out,fixtures,options={}){
 const tasks=options.tasks||PLAN[name];if(!tasks)throw new Error('Unknown browser shard: '+name);
 fs.mkdirSync(path.join(out,'timings'),{recursive:true});
 if(fixtures){
  if(tasks.some(task=>task.script==='audit_sports.cjs'))fs.cpSync(path.join(fixtures,'audit-fixtures'),path.join(site,'audit-fixtures'),{recursive:true});
  if(tasks.some(task=>task.script==='check_truck_fit.cjs'))fs.copyFileSync(path.join(fixtures,'truck-fixtures.html'),path.join(site,'truck-fixtures.html'));
 }
 const started=Date.now();
 const report={shard:name,started_at:new Date(started).toISOString(),tasks:tasks.map(task=>({id:task.id,status:'pending',code:null,duration_ms:0}))};
 const write=()=>fs.writeFileSync(path.join(out,'timings',name+'.json'),JSON.stringify(report,null,2)+'\n');
 write();
 let next=0;
 async function worker(){
  for(;;){
   const index=next++;if(index>=tasks.length)return;const task=tasks[index];
   // Navigation's two independent width sets have separate output directories.
   console.log(`Starting ${task.id}`);
   const result=await runTask(task,site,out,options);report.tasks[index]=result;write();
   console.log(`${task.id}: ${result.status} (${(result.duration_ms/1000).toFixed(1)}s)`);
  }
 }
 const concurrency=Math.min(tasks.length,options.concurrency||CONCURRENCY[name]||1);
 await Promise.all(Array.from({length:concurrency},worker));
 report.duration_ms=Date.now()-started;write();
 return report;
}
if(require.main===module){
 const [name,site,out,fixtures]=process.argv.slice(2);
 runShard(name,path.resolve(site),path.resolve(out),fixtures&&path.resolve(fixtures)).then(report=>{
  if(report.tasks.some(t=>t.status!=='pass'))process.exitCode=1;
 }).catch(error=>{console.error(error);process.exitCode=1;});
}
module.exports={runTask,runShard};
