/* Phone-only presentation and transient-sheet history. The catalog still owns
 * every filter, count, URL parameter and saved-view value. */
(function(root,factory){
    const api=factory();
    if(typeof module==='object'&&module.exports)module.exports=api;
    else root.ShredPhoneFilters=api;
})(typeof window==='undefined'?globalThis:window,function(){
    'use strict';
    function topBrands(rows, limit=8){
        return rows.filter(row=>row.count>0).sort((a,b)=>b.count-a.count||a.order-b.order).slice(0,limit).map(row=>row.key);
    }
    function mount(win, hooks){
        const doc=win.document, drawer=doc.getElementById('filterDrawer');
        if(!drawer)return null;
        const media=win.matchMedia('(max-width: 640px)');
        const head=drawer.querySelector('.drawer-head'), close=doc.getElementById('filtersClose');
        const clear=doc.getElementById('clearAll'), clearHome=clear.parentNode;
        const show=drawer.querySelector('.show-results'), filters=doc.getElementById('filtersOpen');
        const filterHome={parent:filters.parentNode,next:filters.nextSibling};
        const body=doc.createElement('div');body.className='phone-filter-body';
        [...drawer.children].filter(node=>node!==head&&node!==show).forEach(node=>body.appendChild(node));
        const footer=doc.createElement('div');footer.className='phone-filter-footer';
        const hint=doc.createElement('p');hint.id='phoneFilterHint';hint.hidden=true;
        hint.textContent='No deals match. Clear a filter or use Clear all.';hint.setAttribute('role','status');
        show.setAttribute('aria-describedby',hint.id);footer.append(hint,show);drawer.append(body,footer);
        const brands=doc.getElementById('brandList'), search=doc.getElementById('brandSearch');
        const originalBrands=[...brands.querySelectorAll('.facet-value')];
        const more=doc.createElement('button');more.type='button';more.className='phone-brands-more';more.hidden=true;
        more.setAttribute('aria-controls','brandList');more.setAttribute('aria-expanded','false');brands.after(more);
        let expanded=false, opened=false, closing=false, savedY=0, originalPosition='', originalTop='', originalWidth='';
        let sectionState=[], inertState=[], titleState=new Map();
        let host=null;
        try{if(win.parent!==win&&win.parent.location.origin===win.location.origin)host=win.parent.shredApp;}catch(_){}
        function activeSection(section){
            return [...section.querySelectorAll('[aria-pressed="true"]')].some(node=>{
                const value=node.dataset.value??node.dataset.brand??node.dataset.store??node.dataset.kind??node.dataset.interval;
                return value!==''&&value!=='all';
            })||[...section.querySelectorAll('input[type=number],select')].some(node=>node.value!==''&&node.value!=='all');
        }
        function inertBackground(on){
            if(on){let node=drawer;
                while(node.parentElement&&node.parentElement!==doc.documentElement){
                    [...node.parentElement.children].filter(sibling=>sibling!==node&&sibling.tagName!=='SCRIPT').forEach(sibling=>{
                        inertState.push([sibling,sibling.inert]);sibling.inert=true;
                    });node=node.parentElement;
                }
            }else{inertState.forEach(([node,value])=>node.inert=value);inertState=[];}
        }
        function rankBrands(){
            const phone=media.matches, query=(search.value||'').trim();
            const rows=originalBrands.filter(n=>n.dataset.brand!=='all').map((node,order)=>({key:node.dataset.brand,count:Number(node.dataset.count)||0,order,node}));
            const top=new Set(topBrands(rows));let hidden=0;
            rows.forEach(({node,key,count})=>{
                const active=node.getAttribute('aria-pressed')==='true';
                const collapse=phone&&!expanded&&!query&&!top.has(key)&&!active&&count>0;
                node.classList.toggle('phone-brand-hidden',collapse);
                // Keep a selected brand visible even while its name is not the search.
                if(phone&&active){node.classList.remove('is-search-hide');const note=brands.querySelector('.filter-empty');if(note){note.hidden=true;note.style.display='none';}}
                if(collapse)hidden++;
            });
            const ordered=phone?[originalBrands.find(n=>n.dataset.brand==='all'),...rows.sort((a,b)=>b.count-a.count||a.order-b.order).map(r=>r.node)].filter(Boolean):originalBrands;
            const focus=doc.activeElement;
            ordered.forEach((node,index)=>{if(brands.querySelectorAll('.facet-value')[index]!==node)brands.insertBefore(node,brands.querySelectorAll('.facet-value')[index]||null);});
            if(focus?.isConnected&&focus!==doc.activeElement&&brands.contains(focus))focus.focus({preventScroll:true});
            more.hidden=!phone||!!query||(!hidden&&!expanded);
            more.textContent=expanded?'Fewer brands −':'More brands ('+hidden+') +';
            more.setAttribute('aria-expanded',String(expanded));
        }
        function sync(){
            const phone=media.matches;
            if(!phone&&opened&&!closing)requestClose(false);
            if(phone){
                if(clear.parentNode!==head)head.appendChild(clear);
                close.textContent='←';
                const tools=doc.querySelector('.tool-display');if(tools&&filters.parentNode!==tools)tools.appendChild(filters);
                const count=hooks.count();show.textContent='Show '+count+' '+(count===1?'deal':'deals');
                show.disabled=count===0;hint.hidden=count!==0;
                doc.querySelectorAll('.deal-card .card-store-link').forEach(link=>{
                    if(!titleState.has(link))titleState.set(link,link.getAttribute('title'));
                    link.title=link.closest('.deal-card').dataset.name||link.textContent.trim();
                });
            }else{
                if(clear.parentNode!==clearHome)clearHome.appendChild(clear);
                close.textContent='×';more.hidden=true;show.disabled=false;show.textContent='Show results';hint.hidden=true;
                if(filters.parentNode!==filterHome.parent)filterHome.parent.insertBefore(filters,filterHome.next?.parentNode===filterHome.parent?filterHome.next:null);
                titleState.forEach((title,link)=>{if(title===null)link.removeAttribute('title');else link.setAttribute('title',title);});titleState.clear();
            }
            rankBrands();
        }
        function openVisual(){
            if(opened||!media.matches)return;
            opened=true;closing=false;savedY=win.scrollY;
            originalPosition=doc.body.style.position;originalTop=doc.body.style.top;originalWidth=doc.body.style.width;
            doc.body.style.position='fixed';doc.body.style.top=-savedY+'px';doc.body.style.width='100%';
            doc.body.classList.add('filters-open','phone-filters-open');drawer.classList.add('is-open');
            drawer.setAttribute('role','dialog');drawer.setAttribute('aria-modal','true');drawer.setAttribute('aria-label','Filters');
            sectionState=[...drawer.querySelectorAll('.filter-section')].map(node=>[node,node.classList.contains('is-open')]);
            const visible=sectionState.filter(([node])=>!node.hidden&&!node.classList.contains('is-type-hidden')&&node.style.display!=='none'&&node.getClientRects().length);
            sectionState.forEach(([node])=>hooks.section(node,visible.slice(0,2).some(([n])=>n===node)||activeSection(node)));
            inertBackground(true);sync();close.focus({preventScroll:true});
        }
        function closeVisual(scroll){
            if(!opened)return;
            opened=false;closing=false;drawer.classList.remove('is-open');doc.body.classList.remove('filters-open','phone-filters-open');
            drawer.removeAttribute('role');drawer.removeAttribute('aria-modal');drawer.removeAttribute('aria-label');
            inertBackground(false);sectionState.forEach(([node,value])=>hooks.section(node,value));sectionState=[];
            doc.body.style.position=originalPosition;doc.body.style.top=originalTop;doc.body.style.width=originalWidth;
            win.requestAnimationFrame(()=>{win.scrollTo(0,savedY);if(scroll)hooks.results();else filters.focus({preventScroll:true});});
        }
        function open(){
            if(opened)return;
            if(host?.openPhoneFilters)host.openPhoneFilters();
            else win.history.pushState({...win.history.state,phoneFilters:1},'',win.location.href);
            openVisual();
        }
        function requestClose(scroll=false){
            if(!opened||closing)return;closing=true;
            if(host?.closePhoneFilters)host.closePhoneFilters(scroll);
            else {pendingScroll=scroll;win.history.back();}
        }
        let pendingScroll=false;
        function pop(event){
            if(host)return false; // The shell owns embedded history.
            if(opened){const query=hooks.query();closeVisual(pendingScroll);pendingScroll=false;
                const target=new URL(win.location.href);target.search=query;
                win.history.replaceState({view:query},'',target);return true;}
            if(event?.state?.phoneFilters&&media.matches){hooks.restore();openVisual();return true;}
            return false;
        }
        more.addEventListener('click',()=>{expanded=!expanded;rankBrands();});
        search.addEventListener('input',()=>win.queueMicrotask(sync));
        doc.addEventListener('keydown',event=>{
            if(!opened)return;
            if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();requestClose();}
            if(event.key==='Tab'){
                const stops=[...drawer.querySelectorAll('button,input,select,[tabindex="0"]')].filter(n=>!n.disabled&&n.getClientRects().length);
                if(event.shiftKey&&doc.activeElement===stops[0]){event.preventDefault();stops[stops.length-1]?.focus();}
                else if(!event.shiftKey&&doc.activeElement===stops[stops.length-1]){event.preventDefault();stops[0]?.focus();}
            }
        },true);
        win.addEventListener('phonefiltersclose',event=>closeVisual(!!event.detail?.scroll));
        win.addEventListener('phonefiltersopen',openVisual);
        media.addEventListener('change',sync);
        const count=doc.getElementById('statusCounts');if(count)new MutationObserver(sync).observe(count,{childList:true,subtree:true,characterData:true});
        sync();
        return {open,close:requestClose,pop,isOpen:()=>opened,isPhone:()=>media.matches,sync};
    }
    return {topBrands,mount};
});
