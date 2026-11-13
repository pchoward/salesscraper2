// Every existing suite and viewport remains covered. Audit fixtures run once.
const task=(id,script,output,env={},args=[])=>({id,script,output,env,args});
const PLAN={
 navigation:[task('categories-wide','check_category_navigation.cjs','category-navigation-results/wide',{CATEGORY_WIDTHS:'1440,1024,768'}),
  task('categories-phone','check_category_navigation.cjs','category-navigation-results/phone',{CATEGORY_WIDTHS:'430,390,320'})],
 controls:[task('smoke','smoke.mjs','shots'),task('sport-menus','check_sport_menus.cjs','category-navigation-results/sport-menus'),
  task('sidebar','check_sidebar.cjs','category-navigation-results/sidebar'),task('my-stuff','check_my_stuff.cjs','category-navigation-results/my-stuff'),
  task('explore','check_explore.cjs','public-explore-results',{},['--public'])],
 filters:[task('truck-fit','check_truck_fit.cjs','category-navigation-results/truck-fit'),
  task('multi-store','check_multi_store.cjs','category-navigation-results/multi-store'),
  task('phone-filters','check_phone_filters.cjs','category-navigation-results/phone-filters')],
 search:[task('catalog-search','check_catalog_search.cjs','category-navigation-results/live-catalog'),
  task('header-search','check_header_search.cjs','header-search-results')],
 'audit-wide':[task('audit-wide','audit_sports.cjs','four-sport-results/wide',{AUDIT_WIDTHS:'1440,1024,768',AUDIT_FIXTURES:'off'})],
 'audit-phone':[task('audit-phone','audit_sports.cjs','four-sport-results/phone',{AUDIT_WIDTHS:'430,390'})],
};
const CONCURRENCY={navigation:2};
module.exports={PLAN,CONCURRENCY};
