import test from 'node:test';
import assert from 'node:assert/strict';
import { createCatalogSearch, catalogCards, catalogRequest, CACHE_MS, CATALOG_ENDPOINT, TOKEN_ENDPOINT, AGENT_PROFILE } from '../src/catalog.js';
import worker, { handle } from '../src/index.js';
import { makeEnv, START } from './helpers.js';

const ORIGIN = 'https://shreddeals.com';
const price = amount => ({amount,currency:'USD'});
function variant(extra={}) {
  return {id:'v1',title:'Large',price:price(8000),list_price:price(10000),
    availability:{available:true},seller:{id:'shop-1',name:'Sample Shop',url:'https://shop.example'},
    url:'https://shop.example/bike?variant=1&shcgid=retain%2Fthis&shclid=keep#size',...extra};
}
function data(variants=[variant()]) {
  return {ucp:{capabilities:{'dev.shopify.catalog.global':[{version:'2026-04-08'}]}},products:[{
    id:'p1',title:'Example bike',media:[{type:'image',url:'https://images.example/bike.png'}],variants}]};
}
function setup(extra={}) {
  const env=makeEnv('mock',{CATALOG_SEARCH_ENABLED:'true',SHOPIFY_CATALOG_CLIENT_ID:'client-id',SHOPIFY_CATALOG_CLIENT_SECRET:'catalog-secret',...extra});
  const route=createCatalogSearch(),clock={now:START},calls=[];let payload=data(),mode='json',status=200,fail=false,tokenStatus=200;
  const fetcher=async (url,init)=>{
    calls.push({url,init});
    if(fail)throw new Error('private-secret-error');
    if(url===TOKEN_ENDPOINT)return new Response(JSON.stringify({access_token:'private-jwt',expires_in:3600}),{status:tokenStatus});
    assert.equal(url,CATALOG_ENDPOINT);
    const result={jsonrpc:'2.0',id:1,result:{structuredContent:payload}};
    if(mode==='text')result.result={content:[{type:'text',text:JSON.stringify(payload)}]};
    const raw=mode==='sse'?'event: message\ndata: '+JSON.stringify({jsonrpc:'2.0',method:'notifications/progress'})+'\n\nevent: message\ndata: '+JSON.stringify(result)+'\n\n':JSON.stringify(result);
    return new Response(raw,{status,headers:{'Content-Type':mode==='sse'?'text/event-stream':'application/json'}});
  };
  async function call(q='dirt jumper',sport='mtb',options={}) {
    const request=new Request(`https://api.example/v1/catalog-search?q=${encodeURIComponent(q)}&sport=${sport}`,
      {method:options.method||'GET',headers:{Origin:options.origin??ORIGIN,'CF-Connecting-IP':options.ip||'203.0.113.1'}});
    const response=await route(request,env,{fetch:fetcher,now:()=>clock.now});
    return {response,body:response.status===204?null:await response.json()};
  }
  return {env,clock,calls,call,fetcher,route,setPayload:x=>payload=x,setMode:x=>mode=x,setStatus:x=>status=x,setFail:x=>fail=x,setTokenStatus:x=>tokenStatus=x};
}

test('request matches Catalog protocol, US availability, profile and sport',()=>{
  const req=catalogRequest('forks','mtb');
  assert.equal(req.params.name,'search_catalog');assert.equal(req.params.arguments.catalog.query,'forks mtb');
  assert.equal(req.params.arguments.meta['ucp-agent'].profile,AGENT_PROFILE);
  assert.deepEqual(req.params.arguments.catalog.filters,{ships_to:{country:'US'},available:true});
  assert.deepEqual(req.params.arguments.catalog.pagination,{limit:50});
  assert.equal(catalogRequest('Sunday BMX bikes','bmx').params.arguments.catalog.query,'Sunday BMX bikes');
});

test('same-variant markdowns, exact 5% boundary, currencies, availability and safe links',()=>{
  const values=[variant({price:price(9500)}),variant({id:'v2',seller:{id:'shop-2',name:'Second Shop'},price:price(9501)}),
    variant({id:'v3',list_price:null}),variant({id:'v4',list_price:{amount:10000,currency:'EUR'}}),
    variant({id:'v5',availability:{available:false}}),variant({id:'v6',url:'javascript:alert(1)'}),
    variant({id:'v7',price:{amount:'8000',currency:'USD'}})];
  const mapped=catalogCards(data(values));assert.equal(mapped.length,1);
  assert.equal(mapped[0].title,'Example bike — Large');assert.equal(mapped[0].discount,5);
  assert.equal(mapped[0].price.amount,9500);assert.equal(mapped[0].image,'https://images.example/bike.png');
  assert.equal(mapped[0].url,values[0].url);assert.deepEqual(mapped[0].seller,{name:'Sample Shop',domain:'shop.example'});
  assert.deepEqual(catalogCards({products:data().products}),[],'unnegotiated global filters fail closed');
  assert.deepEqual(catalogCards(data([variant({price:price(10000)})])),[]);
  assert.equal(catalogCards(data([variant({url:undefined,checkout_url:'https://shop.example/cart/1:1?shclid=checkout'})]))[0].url,
    'https://shop.example/cart/1:1?shclid=checkout');
});

test('never mix product ranges with variant list prices; dedupe per product and seller; at most 12',()=>{
  const raw=data([variant({price:null}),variant({id:'second',title:'Small'}),variant({id:'third'})]);
  raw.products[0].price_range={min:price(100)};
  assert.equal(catalogCards(raw).length,1);assert.equal(catalogCards(raw)[0].price.amount,8000);
  raw.products=Array.from({length:20},(_,i)=>({...raw.products[0],id:'p'+i}));assert.equal(catalogCards(raw).length,12);
  raw.products[0].variants[0].seller.secret='private';assert(!JSON.stringify(catalogCards(raw)).includes('private'));
});

test('auth, thin response, attribution and no-store; disabled Catalog independent of email settings',async()=>{
  const app=setup();const {response,body}=await app.call();assert.equal(response.status,200);
  assert.equal(response.headers.get('Access-Control-Allow-Origin'),ORIGIN);assert.equal(response.headers.get('Cache-Control'),'no-store');
  assert.equal(body.items.length,1);assert.equal(body.expires_at,START*1000+CACHE_MS);assert.equal(body.max_age_ms,CACHE_MS);
  assert.equal(app.calls[0].url,TOKEN_ENDPOINT);
  assert.deepEqual(JSON.parse(app.calls[0].init.body),{grant_type:'client_credentials',client_id:'client-id',client_secret:'catalog-secret'});
  assert.equal(app.calls[1].init.headers.Authorization,'Bearer private-jwt');
  assert(!JSON.stringify(body).includes('private'));assert(!JSON.stringify(body).includes('catalog-secret'));
  const rows=await app.env.DB.prepare('SELECT bucket FROM rate_limits').all();assert.equal(rows.results.length,2);
  assert(rows.results.every(r=>!r.bucket.includes('203.0.113.1')&&!r.bucket.includes('dirt')));
  const off=setup({CATALOG_SEARCH_ENABLED:'false'});assert.deepEqual((await off.call()).body,{items:[]});assert.equal(off.calls.length,0);
  const env={...app.env,DB:app.env.DB,MODE:undefined,RESEND_API_KEY:undefined};
  const req=new Request('https://api.example/v1/catalog-search?q=bikes&sport=bmx',{headers:{Origin:ORIGIN,'CF-Connecting-IP':'203.0.113.2'}});
  app.clock.now+=1;const routed=await handle(req,env,{fetch:app.fetcher,now:()=>app.clock.now});assert.equal((await routed.json()).items.length,1);
});

test('normalized query cache expires at ten minutes, never returns stale on error; token reuse/refresh',async()=>{
  const app=setup();await app.call(' DIRT   Jumper ');await app.call('dirt jumper');assert.equal(app.calls.length,2);
  app.clock.now+=1;await app.call('forks');assert.equal(app.calls.filter(c=>c.url===TOKEN_ENDPOINT).length,1);
  app.clock.now+=599;await app.call('dirt jumper');assert.equal(app.calls.filter(c=>c.url===CATALOG_ENDPOINT).length,3);
  app.clock.now+=CACHE_MS/1000;app.setFail(true);assert.deepEqual((await app.call('dirt jumper')).body,{items:[]});
  app.setFail(false);app.clock.now=START+3541;await app.call('new query');assert.equal(app.calls.filter(c=>c.url===TOKEN_ENDPOINT).length,2);
});

test('cross-sport cache isolation, SSE and text MCP responses',async()=>{
  const app=setup();app.setMode('sse');assert.equal((await app.call()).body.items.length,1);
  app.clock.now+=1;app.setMode('text');assert.equal((await app.call('dirt jumper','bmx')).body.items.length,1);
  assert.equal(app.calls.filter(c=>c.url===CATALOG_ENDPOINT).length,2);
});

test('CORS, method, query bounds and missing configuration fail closed',async()=>{
  const app=setup();assert.equal((await app.call('bike','bmx',{origin:'https://evil.example'})).response.status,403);
  assert.equal((await app.call('bike','bmx',{method:'OPTIONS'})).response.status,204);
  assert.equal((await app.call('bike','bmx',{method:'POST'})).response.status,405);
  for(const [q,sport]of[['ab','bmx'],['x'.repeat(201),'ski'],['bikes','snow']])assert.deepEqual((await app.call(q,sport)).body,{items:[]});
  assert.equal(app.calls.length,0);
  for(const missing of ['DB','TOKEN_PEPPER','SHOPIFY_CATALOG_CLIENT_ID','SHOPIFY_CATALOG_CLIENT_SECRET']){
    const off=setup({[missing]:undefined});assert.deepEqual((await off.call()).body,{items:[]});assert.equal(off.calls.length,0);
  }
});

test('per-IP throttle applies even to cached replies and spans handler instances',async()=>{
  const app=setup();for(let i=0;i<10;i++)assert.equal((await app.call()).body.items.length,1);
  assert.deepEqual((await app.call()).body,{items:[]});assert.equal(app.calls.length,2);
  const req=new Request('https://api.example/v1/catalog-search?q=bikes&sport=bmx',{headers:{Origin:ORIGIN,'CF-Connecting-IP':'203.0.113.1'}});
  const second=createCatalogSearch();assert.deepEqual(await(await second(req,app.env,{fetch:app.fetcher,now:()=>app.clock.now})).json(),{items:[]});
  app.clock.now+=60;assert.equal((await app.call()).body.items.length,1);
});

test('global gate spans isolates and prevents bursts across second boundaries',async()=>{
  const app=setup();for(let i=0;i<4;i++){app.clock.now=START+i*.3;await app.call('query '+i,'mtb',{ip:'203.0.113.'+(i+1)});}
  assert.equal(app.calls.filter(c=>c.url===CATALOG_ENDPOINT).length,4);
  app.clock.now=START+.99;const req=new Request('https://api.example/v1/catalog-search?q=bikes&sport=bmx',{headers:{Origin:ORIGIN,'CF-Connecting-IP':'203.0.113.99'}});
  const isolated=createCatalogSearch();assert.deepEqual(await(await isolated(req,app.env,{fetch:app.fetcher,now:()=>app.clock.now})).json(),{items:[]});
  app.clock.now=START+1.01;assert.deepEqual((await app.call('another query','mtb',{ip:'203.0.113.100'})).body,{items:[]});
  assert.equal(app.calls.filter(c=>c.url===CATALOG_ENDPOINT).length,4);
});

test('upstream network/auth/HTTP failures expose no error details or secrets',async()=>{
  for(const kind of ['network','auth','http']){
    const app=setup();if(kind==='network')app.setFail(true);if(kind==='auth')app.setTokenStatus(401);if(kind==='http')app.setStatus(503);
    assert.deepEqual((await app.call()).body,{items:[]});
  }
});

test('concurrent identical shopper searches share one upstream request',async()=>{
  const app=setup();const replies=await Promise.all([app.call(),app.call(),app.call()]);
  assert(replies.every(r=>r.body.items.length===1));assert.equal(app.calls.length,2);
});

test('global admission is checked after slow authentication, not before it',async()=>{
  const app=setup();let release;const ready=new Promise(resolve=>release=resolve);let started;
  const seen=new Promise(resolve=>started=resolve);
  const fetcher=async(url,init)=>{if(url===TOKEN_ENDPOINT){started();await ready;}return app.fetcher(url,init);};
  const request=q=>new Request(`https://api.example/v1/catalog-search?q=${q}&sport=mtb`,{headers:{Origin:ORIGIN,'CF-Connecting-IP':'203.0.113.'+q}});
  const a=app.route(request('first'),app.env,{fetch:fetcher,now:()=>app.clock.now});await seen;
  const b=app.route(request('second'),app.env,{fetch:fetcher,now:()=>app.clock.now});
  app.clock.now+=10;release();const replies=await Promise.all([a,b]);
  assert.equal(app.calls.filter(c=>c.url===CATALOG_ENDPOINT).length,1);
  assert.equal((await replies[0].json()).items.length+(await replies[1].json()).items.length,1);
});


test('cached responses advertise remaining lifetime rather than a fresh ten minutes',async()=>{
  const app=setup();await app.call();app.clock.now+=100;
  assert.equal((await app.call()).body.max_age_ms,500000);assert.equal(app.calls.length,2);
});


test('Catalog-only deployment prunes old rate counters through the existing cron',async()=>{
  const app=setup();await app.env.DB.prepare("INSERT INTO rate_limits VALUES ('catalogIp:old',1,0),('catalogGlobal:old',1,0),('alerts:unrelated',1,0)").run();
  const promises=[];await worker.scheduled({}, {...app.env,MODE:undefined}, {waitUntil:p=>promises.push(p)});
  await Promise.all(promises);assert.equal(promises.length,1);
  const {results}=await app.env.DB.prepare('SELECT bucket FROM rate_limits').all();
  assert.deepEqual(results,[{bucket:'alerts:unrelated'}]);
});
