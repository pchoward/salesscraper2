// Fail closed on absent/incomplete groups; retain timings for future balancing.
const fs=require('node:fs'),path=require('node:path'),{PLAN}=require('./browser_plan.cjs');
function summarize(root){
 const lines=['| Browser group | Duration | Result |','| --- | ---: | --- |'];let failed=false,total=0,longest=0;
 for(const [name,tasks]of Object.entries(PLAN)){
  let report;try{report=JSON.parse(fs.readFileSync(path.join(root,'timings',name+'.json')));}catch(_){}
  const complete=report?.shard===name&&Array.isArray(report.tasks)&&report.tasks.length===tasks.length&&
   tasks.every((task,i)=>report.tasks[i]?.id===task.id&&report.tasks[i]?.status==='pass'&&report.tasks[i]?.code===0);
  const serial=report?.tasks?.reduce((sum,t)=>sum+(Number(t?.duration_ms)||0),0)||0;
  const duration=Number(report?.duration_ms)||serial;
  failed||=!complete;total+=serial;longest=Math.max(longest,duration);
  lines.push(`| ${name} | ${(duration/1000).toFixed(1)}s | ${complete?'Pass':'Fail / incomplete'} |`);
 }
 lines.push('',`Measured suite time: ${(total/1000).toFixed(1)}s serial; longest parallel group: ${(longest/1000).toFixed(1)}s. Runner setup/build/artifact time is additional.`);
 return {failed,text:lines.join('\n')+'\n',serial_ms:total,longest_ms:longest};
}
if(require.main===module){
 const result=summarize(process.argv[2]);console.log(result.text);
 if(process.env.GITHUB_STEP_SUMMARY)fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY,result.text);
 if(result.failed)process.exitCode=1;
}
module.exports={summarize};
