const {test}=require('node:test'),assert=require('node:assert/strict');
const fit=require('../truck-fit.js'),search=require('../search/search.js');
search.configure(require('../search/aliases.json'));
const row={dataset:{part:'Trucks',truckOffers:JSON.stringify([
 {key:'ace:55',fits:['8.5'],price:50,compare:100,available:true},
 {key:'ace:66',fits:['9.0'],price:150,compare:null,available:true},
 {key:'ace:66',fits:['9.0'],price:20,compare:100,available:false}
])}};
test('fit, native, stock and price must belong to the same offer',()=>{
 assert.equal(fit.options(row,{fits:['9.0']},{priceMax:60}).length,0);
 assert.equal(fit.options(row,{fits:['9.0'],native:['ace:55']}).length,0);
 assert.equal(fit.cheapest(row,{fits:['9.0']}).price,150);
 assert.equal(fit.options(row,{fits:['9.0']},{discountMin:1}).length,0);
 assert.equal(fit.cheapest(row,{fits:['8.5']},{discountMin:40}).price,50);
});
test('native truck queries and deck widths are distinct',()=>{
 assert.deepEqual(search.parseQuery('indy 159').filters.truckNatives,['independent:159']);
 assert.deepEqual(search.parseQuery('ace 66').filters.truckNatives,['ace:66']);
 const q=search.parseQuery('9.0 trucks').filters;
 assert.equal(q.truckFit,'9.0');assert.equal(q.width,undefined);
 assert.equal(search.rowAllows({...q,priceMax:60},row),false);
 assert.equal(search.rowAllows(q,row),true);
 assert.equal(search.parseQuery('8.5 decks').filters.width,8.5);
});
test('AF1 80 exact guidance remains separate from the broader group',()=>{
 const offer={key:'ace:80',native:'80',brand:'ace',guidance:[9.75,null],fits:['9.5+'],price:100};
 assert.equal(fit.range(offer),'owner guidance 9.75+″');
 assert.equal(fit.options({truckOffers:[offer]},{fits:['9.0']}).length,0);
 assert.equal(fit.options({truckOffers:[offer]},{fits:['9.5+']}).length,1);
});
