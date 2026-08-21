"""Classification automatique catégorie + priorité (FR011, BR010 partiel).

Approche hybride :
1. **Score lexical** : dictionnaire pondéré de mots-clés métier banque/assurance UEMOA
2. **Apprentissage par voisinage** : si des dossiers similaires existent et sont
   déjà qualifiés, on récupère leur catégorie/priorité majoritaire (similarité Jaccard)

Pas de dépendance externe (LLM/API) — démontrable hors-ligne.
On peut remplacer par un appel Claude/GPT dans `_score_lexical` si désiré.
"""
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models


# Dictionnaires pondérés — poids = importance dans la décision.
MOTS_CATEGORIE: dict[str, dict[str, int]] = {
    "FINANCIERE": {
        "débit": 5, "debit": 5, "prélèvement": 4, "prelevement": 4,
        "virement": 5, "transfert": 4, "compte": 3, "solde": 3,
        "frais": 5, "commission": 5, "agios": 5, "interets": 3, "intérêts": 3,
        "montant": 3, "fcfa": 3, "remboursement": 5, "sinistre": 5,
        "crédit": 3, "credit": 3, "decouvert": 3, "découvert": 3,
        "non autorisé": 6, "non-autorise": 6, "contesté": 5, "conteste": 5,
        "erroné": 4, "errone": 4, "mauvais": 2, "double": 4,
    },
    "FRAUDE": {
        "fraude": 8, "frauduleux": 7, "frauduleuse": 7,
        "usurpation": 8, "usurpé": 7, "usurpe": 7,
        "phishing": 7, "hameconnage": 7, "hameçonnage": 7,
        "arnaque": 6, "escroquerie": 7, "vol": 5, "voleur": 4,
        "carte volée": 7, "carte perdue": 5,
        "piratage": 6, "piraté": 6, "pirate": 6,
        "code pin": 5, "mot de passe": 4,
        "faux site": 6, "faux sms": 6, "faux appel": 6,
    },
    "SERVICE": {
        "agence": 3, "guichet": 4, "agent": 3, "personnel": 3,
        "accueil": 4, "attente": 5, "délai": 5, "delai": 5,
        "comportement": 6, "impoli": 7, "discrimination": 8,
        "indisponible": 5, "indisponibilité": 5, "panne": 5, "ferme": 3,
        "dab": 5, "distributeur": 5, "application": 4, "appli": 4,
        "site": 3, "site web": 4, "lent": 3, "bug": 4,
        "rendez-vous": 4, "rdv": 4,
    },
    "CONTRACTUELLE": {
        "contrat": 6, "clause": 6, "condition": 4, "engagement": 5,
        "souscription": 5, "résiliation": 6, "resiliation": 6,
        "renouvellement": 5, "tarif": 4, "tarification": 5,
        "garantie": 5, "couverture": 5, "police": 6, "assurance": 4,
        "présentation": 3, "information": 3, "promesse": 4,
        "modification unilatérale": 7,
    },
}

# Mots qui élèvent la priorité (au-delà du standard)
MOTS_PRIORITE: dict[str, dict[str, int]] = {
    "CRITIQUE": {
        "urgent": 4, "urgence": 4, "immédiat": 5, "immediat": 5,
        "fraude": 6, "usurpation": 6, "vol": 5, "piratage": 6,
        "perdu": 3, "volé": 5, "vole": 5,
        "média": 5, "media": 5, "facebook": 4, "twitter": 4,
        "huissier": 6, "tribunal": 7, "avocat": 5, "plainte": 5,
        "menace": 6, "scandale": 5, "presse": 5,
        "danger": 5, "grave": 4,
        "100000": 3, "200000": 4, "500000": 5, "1000000": 6,  # gros montants
    },
    "URGENT": {
        "rapidement": 3, "vite": 3, "demain": 3, "aujourd'hui": 4,
        "bloqué": 4, "bloque": 4, "blocage": 4,
        "carte": 3, "retrait impossible": 5, "transaction": 3,
        "voyage": 4, "déplacement": 4, "deplacement": 4,
    },
}


def _tokens(texte: str) -> list[str]:
    if not texte:
        return []
    texte = texte.lower()
    # Garde uniquement lettres + chiffres + accents
    sortie = []
    mot = []
    for ch in texte:
        if ch.isalnum() or ch in "àâäéèêëîïôöùûüç-'":
            mot.append(ch)
        else:
            if mot:
                sortie.append("".join(mot))
                mot = []
    if mot:
        sortie.append("".join(mot))
    return sortie


def _bigrammes(toks: list[str]) -> set[str]:
    return {f"{toks[i]} {toks[i+1]}" for i in range(len(toks) - 1)}


def _score_lexical(description: str) -> dict:
    """Calcule le score par catégorie et par priorité pour un texte donné."""
    toks = _tokens(description)
    toks_set = set(toks)
    bigs = _bigrammes(toks)

    scores_cat: dict[str, int] = {c: 0 for c in MOTS_CATEGORIE}
    for cat, mots in MOTS_CATEGORIE.items():
        for mot, poids in mots.items():
            if mot in toks_set or mot in bigs:
                scores_cat[cat] += poids

    scores_prio: dict[str, int] = {p: 0 for p in MOTS_PRIORITE}
    for prio, mots in MOTS_PRIORITE.items():
        for mot, poids in mots.items():
            if mot in toks_set or mot in bigs:
                scores_prio[prio] += poids

    return {"categorie": scores_cat, "priorite": scores_prio}


def _voisinage(db: Session, description: str, k: int = 5) -> list[models.Reclamation]:
    """Retourne les k dossiers les plus proches (similarité Jaccard sur tokens >= 4 char)."""
    toks_req = {t for t in _tokens(description) if len(t) >= 4}
    if not toks_req:
        return []
    candidats = list(db.scalars(
        select(models.Reclamation)
        .where(models.Reclamation.statut != "REJETE")
        .order_by(models.Reclamation.date_reception.desc())
        .limit(200)
    ))
    scored = []
    for r in candidats:
        toks_r = {t for t in _tokens(r.description) if len(t) >= 4}
        if not toks_r:
            continue
        inter = len(toks_req & toks_r)
        union = len(toks_req | toks_r)
        sim = inter / union if union else 0
        if sim > 0.1:
            scored.append((sim, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:k]]


def suggerer(db: Session, description: str) -> dict:
    """Suggère catégorie + priorité + confiance pour un texte donné.

    Retourne un dict :
    {
      "categorie_suggeree": "FRAUDE", "score_categorie": 0.85,
      "priorite_suggeree": "CRITIQUE", "score_priorite": 0.72,
      "explication": "Mots-clés détectés : ...",
      "voisins_similaires": [{"code": "...", "categorie": "...", "similarite": 0.6}, ...],
    }
    """
    scores = _score_lexical(description)
    cat_scores = scores["categorie"]
    prio_scores = scores["priorite"]

    # Apprentissage par voisinage
    voisins = _voisinage(db, description, k=5)
    if voisins:
        # On boost les scores selon les voisins
        cats_voisins = Counter(v.categorie for v in voisins)
        prios_voisins = Counter(v.priorite for v in voisins)
        for cat, n in cats_voisins.items():
            cat_scores[cat] = cat_scores.get(cat, 0) + n * 2  # poids 2 par voisin
        for prio, n in prios_voisins.items():
            prio_scores[prio] = prio_scores.get(prio, 0) + n

    # Choix catégorie
    cat_top = max(cat_scores.items(), key=lambda x: x[1]) if cat_scores else ("SERVICE", 0)
    cat_total = sum(cat_scores.values()) or 1
    cat_confiance = round(cat_top[1] / cat_total, 2) if cat_top[1] > 0 else 0.0
    # Fallback SERVICE si rien ne match
    if cat_top[1] == 0:
        cat_top = ("SERVICE", 0)
        cat_confiance = 0.25

    # Priorité : CRITIQUE > URGENT > STANDARD. Critique gagne si score >= 5.
    if prio_scores.get("CRITIQUE", 0) >= 5:
        prio_top = ("CRITIQUE", prio_scores["CRITIQUE"])
    elif prio_scores.get("URGENT", 0) >= 3:
        prio_top = ("URGENT", prio_scores["URGENT"])
    else:
        prio_top = ("STANDARD", 0)
    prio_total = sum(prio_scores.values()) or 1
    prio_confiance = round(prio_top[1] / prio_total, 2) if prio_top[1] > 0 else 0.6

    # Mots détectés (explication)
    toks_set = set(_tokens(description))
    bigs = _bigrammes(_tokens(description))
    detectes = []
    for mot in MOTS_CATEGORIE.get(cat_top[0], {}):
        if mot in toks_set or mot in bigs:
            detectes.append(mot)

    return {
        "categorie_suggeree": cat_top[0],
        "score_categorie": cat_confiance,
        "priorite_suggeree": prio_top[0],
        "score_priorite": prio_confiance,
        "explication": f"Mots-clés catégorie détectés : {', '.join(detectes[:6]) if detectes else 'aucun — fallback'}",
        "voisins_similaires": [
            {
                "code": v.code, "categorie": v.categorie, "priorite": v.priorite,
                "sous_categorie": v.sous_categorie,
            }
            for v in voisins[:3]
        ],
        "scores_bruts": {"categorie": cat_scores, "priorite": prio_scores},
    }
