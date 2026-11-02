/* Optional, configured technical facets. Existing page.js owns filtering/history.
 * Each field is a Skate-style chip section (sports/facets.py): tap several
 * values to match any of them; "All" clears the field. Values are matched per
 * variant offer, so a picked size shows that size's price. */
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
        function list(value){
            if(Array.isArray(value))return value.map(String);
            if(value===undefined||value===null||value==='')return [];
            return String(value).split(',').map(v=>v.trim()).filter(Boolean);
        }
        function clean(value){
            const result={};
            fields.forEach(f=>{
                const picked=list(value&&value[f.key]).filter(v=>f.values.includes(v));
                if(picked.length)result[f.key]=Array.from(new Set(picked));
            });
            return result;
        }
        function paint(){
            if(!doc||typeof doc.querySelectorAll!=='function')return;
            doc.querySelectorAll('.tech-chip').forEach(chip=>{
                const picked=selected[chip.dataset.techKey]||[];
                const on=chip.dataset.value===''?!picked.length:picked.includes(chip.dataset.value);
                chip.classList.toggle('active',on);
                chip.setAttribute('aria-pressed',String(on));
            });
        }
        function restore(value){selected=clean(value);paint();}
        function applies(field,part){return !(field.categories||[]).length||field.categories.includes(part);}
        function active(url){const item=(config.items||{})[url];return fields.filter(f=>selected[f.key]&&(!item||applies(f,item.part)));}
        function options(url){const item=(config.items||{})[url];return item?(item.offers||[]).filter(offer=>
            offer.available!==false&&active(url).every(f=>((offer.specs||{})[f.key]||[]).some(v=>selected[f.key].includes(v)))):[];}
        function sync(part){if(doc)fields.forEach(f=>{const node=doc.querySelector('[data-technical-field="'+f.key+'"]');
            if(node){node.hidden=part!=='all'&&!applies(f,part);node.style.display=node.hidden?'none':'';}});}
        return {
            // One value reads back as a string (older links and callers), several as a list.
            capture(){const out={};Object.keys(selected).forEach(k=>{out[k]=selected[k].length===1?selected[k][0]:[...selected[k]];});return out;},
            restore,
            clear(){restore({});},
            decode(params){const result={};fields.forEach(f=>{const v=params.get(f.param);if(v)result[f.key]=v;});return clean(result);},
            encode(params,value){const result=clean(value);fields.forEach(f=>{if(result[f.key])params.set(f.param,result[f.key].join(','));});},
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
            mount(document){
                doc=document;restore(selected);sync((doc.getElementById("partSelect")||{}).value||"all");
                if(typeof doc.addEventListener==='function')doc.addEventListener('click',event=>{
                    const chip=event.target.closest&&event.target.closest('.tech-chip');
                    if(!chip)return;
                    const key=chip.dataset.techKey;
                    const picked=new Set(selected[key]||[]);
                    if(chip.dataset.value==='')picked.clear();
                    else if(picked.has(chip.dataset.value))picked.delete(chip.dataset.value);
                    else picked.add(chip.dataset.value);
                    const next={...selected};
                    if(picked.size)next[key]=Array.from(picked);else delete next[key];
                    selected=clean(next);paint();
                    if(typeof applyFilters==='function')applyFilters();
                });
            }
        };
    };
});
