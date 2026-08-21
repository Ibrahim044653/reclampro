"""E2E — Multi-langue FR/EN et navigation."""


def test_menu_par_defaut_en_francais(admin_page, live_server):
    assert admin_page.get_by_role("link", name="Tableau de bord").is_visible()
    assert admin_page.get_by_role("link", name="Réclamations").is_visible()


def test_basculer_en_anglais(admin_page, live_server):
    admin_page.click('#btn_lang_en')
    # reload automatique → on attend que le menu soit en anglais
    admin_page.wait_for_load_state("networkidle")
    assert admin_page.get_by_role("link", name="Dashboard").is_visible()
    assert admin_page.get_by_role("link", name="Complaints").is_visible()
    assert admin_page.get_by_role("link", name="New case").is_visible()


def test_revenir_en_francais(admin_page, live_server):
    admin_page.click('#btn_lang_en')
    admin_page.wait_for_load_state("networkidle")
    admin_page.click('#btn_lang_fr')
    admin_page.wait_for_load_state("networkidle")
    assert admin_page.get_by_role("link", name="Tableau de bord").is_visible()


def test_choix_langue_persiste(admin_page, live_server):
    admin_page.click('#btn_lang_en')
    admin_page.wait_for_load_state("networkidle")
    # Naviguer vers une autre page → toujours en anglais
    admin_page.goto(f"{live_server}/reclamations.html")
    admin_page.wait_for_load_state("networkidle")
    assert admin_page.get_by_role("link", name="Complaints").is_visible()
