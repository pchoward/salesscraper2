"""Store placeholder images are dropped (owner, 2026-11-18)."""

import unittest

import notify
import product_images

HOUSE = ("https://www.the-house.com/dw/image/v2/BCJK_PRD/on/demandware.static/Sites-TheHouse-Site/-/default/"
         "dwe7fdba59/images/noimage-hou.png?sw=400&sh=400")
ZUMIEZ_FLAG = ("https://www.zumiez.com/static/frontend/scandipwa/zumiez/en_US/Magento_Theme/static/media/"
               "product-flag-store-app.008fd16a.png")
FANATIK = ("https://cdn.shopify.com/s/files/1/0904/4132/files/ibis-ripley-v3_green_side_placeholder_"
           "ba99f77e-781e-4198-95fe-9179b54065de.jpg?v=1720558577")


class ProductImageTests(unittest.TestCase):
    def test_placeholders(self):
        self.assertTrue(product_images.is_placeholder(HOUSE))
        self.assertTrue(product_images.is_placeholder(ZUMIEZ_FLAG))
        self.assertFalse(product_images.is_placeholder(FANATIK))
        self.assertFalse(product_images.is_placeholder("https://scene7.zumiez.com/is/image/zumiez/409840-US"))

    def test_next_real_image_or_none(self):
        zumiez = {"image": ZUMIEZ_FLAG, "images": [ZUMIEZ_FLAG, "https://scene7.zumiez.com/is/image/zumiez/409840-US"]}
        house = {"image": HOUSE, "name": "Scott Sports Faze II Goggle"}
        fanatik = {"image": FANATIK, "images": [FANATIK]}
        data = {"Zumiez_Decks": [zumiez], "The House_Goggles": [house], "Fanatik_Bikes": [fanatik]}
        self.assertEqual(product_images.clean_items(data), 2)
        self.assertEqual(zumiez["image"], "https://scene7.zumiez.com/is/image/zumiez/409840-US")
        self.assertEqual(zumiez["images"], ["https://scene7.zumiez.com/is/image/zumiez/409840-US"])
        self.assertNotIn("image", house)
        self.assertEqual(fanatik["image"], FANATIK)

    def test_email_skips_placeholder_top_deal(self):
        house = {"name": "Scott Sports Faze II Goggle", "image": HOUSE, "price_new": "90", "price_old": "180",
                 "url": "https://the-house/scott", "store": "The House"}
        anon = {"name": "Anon Raider 3 Helmet", "image": "https://the-house/anon.jpg", "price_new": "69.95",
                "price_old": "99.93", "url": "https://the-house/anon", "store": "The House"}
        self.assertIs(notify.top_deal([house, anon]), anon)
        self.assertNotIn("noimage", notify._html_new_row(house))
        self.assertEqual(house["image"], HOUSE)  # the email doesn't change the listing


if __name__ == "__main__":
    unittest.main()
