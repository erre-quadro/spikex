def test_categories(wikigraph):
    categories = wikigraph.get_categories("Category:Apples")
    assert categories == ["Category:Fruits", "Category:Amygdaloideae"]


def test_neighbors(wikigraph):
    neighbors = wikigraph.get_neighbors("Category:Apples")
    assert neighbors == [
        "McIntosh_(apple)",
        "Jazz_(apple)",
        "Caramel_apple",
        "Category:Fruits",
        "Apple",
        "Jonagold",
        "Category:Apple_products",
        "Baldwin_apple",
        "Braeburn",
        "Category:Amygdaloideae",
        "Aport",
        "Granny_Smith",
        "Gala",
        "Gala_(apple)",
        "Malus",
        "Apples_and_oranges",
        "Winesap",
        "Honeycrisp",
    ]
