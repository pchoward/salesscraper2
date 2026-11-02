(() => {
    'use strict';
    const {scope, state} = JSON.parse(document.getElementById('exploreData').textContent);
    const $ = id => document.getElementById(id);
    const rows = state.offers.filter(offer => offer.available === true);
    const controls = ['category', 'store', 'brand', 'query', 'size', 'sale', 'sort', 'view'];
    function options(id, values) {
        $(id).replaceChildren(...['', ...new Set(values)].map(value => {
            const option = document.createElement('option'); option.value = value; option.textContent = value || 'All'; return option;
        }));
    }
    options('category', rows.map(row => row.category));
    options('store', rows.map(row => row.store)); options('brand', rows.map(row => row.brand));
    const axes = [...new Set(rows.flatMap(row => Object.keys(row.specs)))];
    const sizeLabel = $('size').parentElement;
    sizeLabel.remove(); controls.splice(controls.indexOf('size'), 1);
    for (const axis of axes) {
        const id = axis === 'size' ? 'size' : 'spec_' + axis;
        const label = document.createElement('label'); label.textContent = axis.replaceAll('_', ' ');
        const select = document.createElement('select'); select.id = id; label.append(select);
        $('filters').insertBefore(label, $('sale').parentElement);
        controls.push(id); options(id, rows.map(row => row.specs[axis]).filter(Boolean));
    }
    const verified = state.manifest.filter(item => item.complete).length;
    $('coverage').textContent = `${scope.label} · ${verified}/${state.manifest.length} configured sources completed · ${state.stale ? 'STALE — last good inventory' : 'snapshot complete for configured sources only'} · last success ${state.last_success || 'none'}`;
    function node(tag, text, className) {
        const result = document.createElement(tag); result.textContent = text;
        if (className) result.className = className; return result;
    }
    function retailer(offer) {
        const link = node('a', offer.title); const url = new URL(offer.url);
        if (url.protocol === 'https:') link.href = url.href;
        link.target = '_blank'; link.rel = 'noopener noreferrer'; return link;
    }
    function price(offer) {
        const result = node('div', ''); result.append(node('span', `${offer.currency} ${offer.price}`, 'offer-price'));
        result.append(node('p', offer.compare_at ? `${Math.round((1 - Number(offer.price)/Number(offer.compare_at))*100)}% off retailer compare-at ${offer.compare_at}` : 'Regular price · no reference price', 'muted'));
        return result;
    }
    function quick(offer) {
        const body = $('quickContent'); body.replaceChildren(node('h2', offer.title), price(offer), node('p', `${offer.brand} · ${offer.store} · ${JSON.stringify(offer.specs)}`));
        const points = state.history[offer.id]?.points || [];
        body.append(node('h3', 'Observed price history'));
        if (!points.length) body.append(node('p', 'No verified in-stock observations yet.'));
        for (const point of points) body.append(node('p', `${point.day} · ${offer.currency} ${point.price}`));
        body.append(node('p', 'Retailer compare-at is a reference, not an observed historical price.', 'muted'), retailer(offer));
        $('quick').showModal();
    }
    function render() {
        const params = new URL(location.href).searchParams;
        for (const id of controls) $(id).value = params.get('ex_' + id) || (id === 'sort' ? 'title' : id === 'view' ? 'cards' : '');
        const filtered = rows.filter(offer => {
            return (!$('category').value || offer.category === $('category').value) &&
                (!$('store').value || offer.store === $('store').value) && (!$('brand').value || offer.brand === $('brand').value) &&
                axes.every(axis => { const value = $(axis === 'size' ? 'size' : 'spec_' + axis).value; return !value || offer.specs[axis] === value; }) &&
                (!$('sale').value || Boolean(offer.compare_at) === ($('sale').value === 'sale')) &&
                `${offer.title} ${offer.brand}`.toLowerCase().includes($('query').value.toLowerCase());
        });
        filtered.sort((a,b) => $('sort').value === 'price' ? a.currency.localeCompare(b.currency) || Number(a.price)-Number(b.price) : a.title.localeCompare(b.title));
        $('count').textContent = `${filtered.length} available variants · prices are for the shown size`;
        $('inventory').className = $('view').value === 'table' ? 'table' : 'cards';
        $('inventory').replaceChildren(...filtered.map(offer => {
            const card = node('article', '', 'inventory-card'); card.dataset.variant = offer.variant_id;
            const heading = node('h2', ''); heading.append(retailer(offer)); card.append(heading, node('p', `${offer.brand} · ${offer.store}`), price(offer), node('p', Object.entries(offer.specs).map(([key,value]) => `${key}: ${value}`).join(' · ') || 'Specifications not provided'));
            const button = node('button', 'Quick View'); button.type = 'button'; button.onclick = () => quick(offer); card.append(button); return card;
        }));
        if (!filtered.length) $('inventory').append(node('p', 'No matching verified in-stock variants. Clear filters to broaden your search.'));
    }
    $('filters').onsubmit = event => event.preventDefault();
    function update() {
        const url = new URL(location.href);
        for (const id of controls) { url.searchParams.delete('ex_' + id); if ($(id).value) url.searchParams.set('ex_' + id, $(id).value); }
        history.pushState({}, '', url); render();
    }
    for (const id of controls) $(id).addEventListener(id === 'query' ? 'input' : 'change', update);
    $('filters').onreset = event => {
        event.preventDefault(); const url = new URL(location.href);
        controls.forEach(id => url.searchParams.delete('ex_' + id)); history.pushState({}, '', url); render();
    };
    $('closeQuick').onclick = () => $('quick').close();
    $('navDeals').onclick = () => {
        if (window.parent !== window && window.parent.shredApp) window.parent.shredApp.chooseView(null);
        else location.href = '../../index.html?sport=' + scope.sport;
    };
    addEventListener('popstate', render); render();
})();
