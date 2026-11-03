"""Deterministic SAMPLE inventory only. No network or retailer state."""
from explore.engine import capture


def fixture(sport):
    scope = dict(demo=True, id=sport + '-review', sport=sport, category='bikes' if sport == 'mtb' else 'skis',
                 discipline='dirt-jump' if sport == 'mtb' else 'park',
                 label='Dirt Jump complete bikes' if sport == 'mtb' else 'Park skis · fixture scope',
                 sources=[dict(id='Example retailer', base='https://example.com', collection='fixture', market='US',
                               currency='USD', approved=False, product_types=['Complete Bike' if sport == 'mtb' else 'Skis'],
                               spec_options={'size': 'size'}, max_pages=2)])
    products = []
    for i in range(1, 7):
        title = ('Example dirt jump complete' if sport == 'mtb' else 'Example park ski') + ' ' + str(i)
        products.append(dict(id=i, handle='fixture-' + str(i), title=title, vendor='Demo Cycles' if i % 2 else 'Example Co',
                             product_type=scope['sources'][0]['product_types'][0], options=[{'name': 'Size', 'position': 1}],
                             variants=[dict(id=i*10, price=str(800 + i*50) + '.00', compare_at_price=None, available=True,
                                            option1='Small' if sport == 'mtb' else '168 cm'),
                                       dict(id=i*10+1, price=str(1000 + i*50) + '.00', compare_at_price='1500.00', available=True,
                                            option1='Large' if sport == 'mtb' else '178 cm'),
                                       dict(id=i*10+2, price='500.00', compare_at_price='1000.00', available=False,
                                            option1='Medium' if sport == 'mtb' else '188 cm')]))
    state = capture(scope, lambda *_: {'products': products}, '2026-11-02T12:00:00Z')
    return scope, state
