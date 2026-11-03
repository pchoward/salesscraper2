// Installed only in explicitly built review catalogs.
(() => {
    const app = window.parent !== window && window.parent.shredApp;
    if (!app) return;
    const links = document.querySelector('.topnav-links');
    if (!links || links.querySelector('#navExplore')) return;
    const current = app.state();
    const config = JSON.parse(window.parent.document.getElementById('sportConfig').textContent);
    const scope = (config.exploreScopes || []).find(item => item.sport === current.sport.id);
    if (!scope) return;
    const button = document.createElement('button');
    button.id = 'navExplore'; button.type = 'button'; button.textContent = 'Explore';
    button.onclick = () => app.chooseView(scope.id);
    links.append(button);
})();
