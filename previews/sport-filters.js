/* Optional, configured technical facets. Existing page.js owns filtering/history. */
(function(root,factory){
    const create=factory();
    if(typeof module==='object'&&module.exports)module.exports=create;
    else {
        const node=document.getElementById('technicalCatalog');
        if(node){root.SportSpecFilters=create(JSON.parse(node.textContent));
            document.addEventListener('DOMContentLoaded',()=>root.SportSpecFilters.mount(document));}
    }
})(typeof window==='undefined'?this:window,function(){
    'use strict';
    return function(config){
        const fields=config.fields||[];
        let selected={};
        let doc=null;
        function clean(value){
            const result={};
            fields.forEach(f=>{if(value&&f.values.includes(String(value[f.key]||'')))result[f.key]=String(value[f.key]);});
            return result;
        }
        function restore(value){selected=clean(value);if(doc)fields.forEach(f=>{const n=doc.getElementById('tech-'+f.key);if(n)n.value=selected[f.key]||'';});}
        function applies(field,part){return !(field.categories||[]).length||field.categories.includes(part);}
        function active(url){const item=(config.items||{})[url];return fields.filter(f=>selected[f.key]&&(!item||applies(f,item.part)));}
        function options(url){const item=(config.items||{})[url];return item?(item.offers||[]).filter(offer=>
            offer.available!==false&&active(url).every(f=>((offer.specs||{})[f.key]||[]).includes(selected[f.key]))):[];}
        function sync(part){if(doc)fields.forEach(f=>{const node=doc.querySelector('[data-technical-field="'+f.key+'"]');
            if(node){node.hidden=part!=='all'&&!applies(f,part);node.style.display=node.hidden?'none':'';}});}
        return {
            capture(){return {...selected};},
            restore,
            clear(){restore({});},
            decode(params){const result={};fields.forEach(f=>{const v=params.get(f.param);if(v)result[f.key]=v;});return clean(result);},
            encode(params,value){const result=clean(value);fields.forEach(f=>{if(result[f.key])params.set(f.param,result[f.key]);});},
            allows(url,part){
                const applicable=fields.some(f=>selected[f.key]&&applies(f,part===undefined?((config.items||{})[url]||{}).part:part));
                return !applicable||options(url).length>0;
            },
            sync,
            price(url){
                if(!active(url).length)return null;
                const offers=options(url).filter(o=>Number.isFinite(Number(o.price))&&Number(o.price)>0&&Number(o.compare)>Number(o.price));
                if(!offers.length)return null;
                const best=offers.reduce((a,b)=>Number(a.price)<=Number(b.price)?a:b);
                return {price:Number(best.price),compare:Number(best.compare)};
            },
            paintCompare(node,offer){
                if(node.dataset.techCompareBase===undefined)node.dataset.techCompareBase=node.dataset.original||'';
                node.dataset.original=offer&&Number.isFinite(offer.compare)?String(offer.compare):node.dataset.techCompareBase;
                const was=node.querySelector('.avg-price');
                if(!was||!/^Was\s/.test(was.dataset.techBaseText||was.textContent))return;
                if(!was.dataset.techBaseText)was.dataset.techBaseText=was.textContent;
                const symbol=was.dataset.techBaseText.includes('€')?'€':'$';
                was.textContent=offer&&Number.isFinite(offer.compare)?'Was '+symbol+offer.compare.toFixed(2):was.dataset.techBaseText;
            },
            mount(document){doc=document;restore(selected);sync((doc.getElementById("partSelect")||{}).value||"all");fields.forEach(f=>{const n=doc.getElementById('tech-'+f.key);if(n)n.addEventListener('change',()=>{
                const next={...selected};if(n.value)next[f.key]=n.value;else delete next[f.key];selected=clean(next);
                if(typeof applyFilters==='function')applyFilters();
            });});}
        };
    };
});
