const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {PLAN,CONCURRENCY}=require('./browser_plan.cjs'),{runShard,runTask}=require('./run_browser_shard.cjs'),{summarize}=require('./summarize_browser_runs.cjs');
test('every suite remains scheduled, with the exact audit widths and fixtures once',()=>{
 const tasks=Object.values(PLAN).flat();
 const scripts=tasks.map(t=>t.script);
 assert.deepEqual([...new Set(scripts)].sort(),['smoke.mjs','check_category_navigation.cjs','check_sport_menus.cjs','check_sidebar.cjs','check_my_stuff.cjs','check_truck_fit.cjs','check_multi_store.cjs','check_phone_filters.cjs','check_catalog_search.cjs','check_header_search.cjs','check_explore.cjs','audit_sports.cjs'].sort());
 for(const script of scripts.filter(s=>!['audit_sports.cjs','check_category_navigation.cjs'].includes(s)))assert.equal(scripts.filter(s=>s===script).length,1);
 const audits=tasks.filter(t=>t.script==='audit_sports.cjs');assert.equal(audits.length,2);
 assert.deepEqual(audits.flatMap(t=>t.env.AUDIT_WIDTHS.split(',')).sort(),['1440','1024','768','430','390'].sort());
 assert.equal(audits.filter(t=>t.env.AUDIT_FIXTURES!=='off').length,1);
 const categories=tasks.filter(t=>t.script==='check_category_navigation.cjs');assert.equal(categories.length,2);
 assert.deepEqual(categories.flatMap(t=>t.env.CATEGORY_WIDTHS.split(',')).sort(),['1440','1024','768','430','390','320'].sort());
 assert.equal(CONCURRENCY.navigation,2);
 for(const task of tasks.filter(t=>!['audit_sports.cjs','check_category_navigation.cjs'].includes(t.script)))assert.deepEqual(task.env,{},'all other original viewport defaults remain in effect');
});
test('runner records failure, still runs the next suite, and kills a hanging child',async()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'browser-runner-'));
 try{
  fs.writeFileSync(path.join(tmp,'fail.cjs'),'process.exit(4)');
  fs.writeFileSync(path.join(tmp,'pass.cjs'),`require('node:fs').writeFileSync(${JSON.stringify(path.join(tmp,'ran'))},'yes')`);
  fs.writeFileSync(path.join(tmp,'hang.cjs'),'setInterval(()=>{},1000)');
  const task=(id,script)=>({id,script,output:id,env:{},args:[]});
  const report=await runShard('unit','site',path.join(tmp,'out'),null,{cwd:tmp,timeoutMs:5000,tasks:[task('bad','fail.cjs'),task('next','pass.cjs')]});
  assert.deepEqual(report.tasks.map(t=>t.status),['fail','pass']);assert.equal(report.tasks[0].code,4);assert(fs.existsSync(path.join(tmp,'ran')));
  assert.equal(JSON.parse(fs.readFileSync(path.join(tmp,'out/timings/unit.json'))).tasks.length,2);
  const hung=await runTask(task('hung','hang.cjs'),'site',tmp,{cwd:tmp,timeoutMs:100});assert.equal(hung.status,'fail');assert.equal(hung.timed_out,true);
 }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('gate rejects absent, failed and incomplete reports instead of hiding a group failure',()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'browser-summary-'));fs.mkdirSync(path.join(tmp,'timings'));
 const write=(name,tasks)=>fs.writeFileSync(path.join(tmp,'timings',name+'.json'),JSON.stringify({shard:name,tasks}));
 const passing=name=>PLAN[name].map(t=>({id:t.id,status:'pass',code:0,duration_ms:100}));
 try{
  assert.equal(summarize(tmp).failed,true);
  for(const name of Object.keys(PLAN))write(name,passing(name));assert.equal(summarize(tmp).failed,false);
  write('filters',passing('filters').slice(1));assert.equal(summarize(tmp).failed,true);
  write('filters',passing('filters').map(t=>({...t,status:'fail',code:1})));assert.equal(summarize(tmp).failed,true);
  write('filters',passing('filters'));fs.unlinkSync(path.join(tmp,'timings/navigation.json'));assert.equal(summarize(tmp).failed,true);
 }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});

test('bounded parallel tasks can rendezvous while retaining plan order',async()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'browser-pool-'));
 try{
  for(const [name,other]of [['a','b'],['b','a']])fs.writeFileSync(path.join(tmp,name+'.cjs'),
   `const fs=require('node:fs');fs.writeFileSync(${JSON.stringify(path.join(tmp,name))},'started');const timer=setInterval(()=>{if(fs.existsSync(${JSON.stringify(path.join(tmp,other))})){clearInterval(timer);}},10);`);
  const tasks=['a','b'].map(id=>({id,script:id+'.cjs',output:id,env:{},args:[]}));
  const report=await runShard('unit','site',path.join(tmp,'out'),null,{cwd:tmp,tasks,concurrency:2,timeoutMs:5000});
  assert.deepEqual(report.tasks.map(t=>[t.id,t.status]),[['a','pass'],['b','pass']]);
  assert(report.duration_ms<report.tasks.reduce((sum,t)=>sum+t.duration_ms,0));
 }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
