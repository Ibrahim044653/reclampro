"""E2E — Filtres avancés + pagination sur la liste des réclamations."""


def test_filtre_par_priorite_critique(admin_page, live_server):
    admin_page.goto(f"{live_server}/reclamations.html")
    admin_page.wait_for_selector("#f_priorite")
    admin_page.select_option("#f_priorite", "CRITIQUE")
    admin_page.click("#f_appliquer")
    admin_page.wait_for_load_state("networkidle")
    # L'URL contient le filtre
    assert "priorite=CRITIQUE" in admin_page.url
    # Le select reste sur CRITIQUE
    assert admin_page.locator("#f_priorite").input_value() == "CRITIQUE"


def test_filtre_recherche_texte(admin_page, live_server):
    admin_page.goto(f"{live_server}/reclamations.html")
    admin_page.fill("#f_q", "fraude")
    admin_page.click("#f_appliquer")
    admin_page.wait_for_load_state("networkidle")
    # L'URL contient le filtre
    assert "q=fraude" in admin_page.url


def test_reset_filtres(admin_page, live_server):
    admin_page.goto(f"{live_server}/reclamations.html?priorite=CRITIQUE&statut=NOUVEAU")
    admin_page.wait_for_selector("#f_reset")
    admin_page.click("#f_reset")
    admin_page.wait_for_load_state("networkidle")
    assert "priorite" not in admin_page.url
    assert "statut" not in admin_page.url


def test_pagination_limite_lignes(admin_page, live_server):
    admin_page.goto(f"{live_server}/reclamations.html?limit=5")
    admin_page.wait_for_selector("table.tbl tbody tr")
    nb_lignes = admin_page.locator("table.tbl tbody tr").count()
    assert nb_lignes <= 5


def test_pagination_navigation_page_suivante(admin_page, live_server):
    admin_page.goto(f"{live_server}/reclamations.html?limit=5&skip=0")
    admin_page.wait_for_selector("#page_next")
    if not admin_page.locator("#page_next").is_disabled():
        admin_page.click("#page_next")
        admin_page.wait_for_load_state("networkidle")
        # Le paramètre skip a changé
        assert "skip=5" in admin_page.url


def test_filtre_via_url_directement(admin_page, live_server):
    """Un filtre passé en URL doit être appliqué sans interaction."""
    admin_page.goto(f"{live_server}/reclamations.html?canal=EMAIL")
    admin_page.wait_for_selector("table.tbl tbody tr, .empty")
    # Le select doit refléter le filtre
    valeur_select = admin_page.locator("#f_canal").input_value()
    assert valeur_select == "EMAIL"
