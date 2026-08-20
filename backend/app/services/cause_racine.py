"""Analyse de cause racine par clustering NLP léger (BR010 + FR054).

Algorithme : clustering hiérarchique single-link sur similarité Jaccard
des descriptions, fusion si sim >= seuil. Retourne des grappes avec
un libellé représentatif (mots les plus distinctifs).

Pas de dépendance externe (pas de scikit-learn) — fonctionne sur des
volumes < 10000 dossiers ce qui couvre largement les besoins MVP.
"""
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models

# Mots-vides (stop-words) français — on les exclut du clustering
STOPWORDS = {
    "alors", "auquel", "aussi", "autre", "autres", "avec", "avoir", "bien", "bon",
    "cela", "celui", "cette", "cettes", "ceux", "comme", "comment", "dans", "deja",
    "depuis", "donc", "dont", "elle", "elles", "encore", "essai", "etre", "fait",
    "faire", "fois", "font", "hors", "jour", "leur", "leurs", "mais", "même",
    "mes", "mien", "moins", "mon", "nous", "notre", "nos", "ont", "par", "parce",
    "pas", "peut", "pour", "pourquoi", "quand", "que", "quel", "quelle", "qui",
    "sans", "ses", "ses", "son", "sont", "sous", "sur", "tous", "tout", "trop",
    "très", "tres", "une", "vos", "votre", "vous", "était", "était", "été",
    "monsieur", "madame", "bonjour", "merci", "cordialement", "salutations",
    "votre", "client", "service", "agence",
}


def _tokens(texte: str) -> set[str]:
    if not texte:
        return set()
    texte = texte.lower()
    res = set()
    mot = []
    for ch in texte:
        if ch.isalnum() or ch in "àâäéèêëîïôöùûüç-'":
            mot.append(ch)
        else:
            if mot:
                m = "".join(mot)
                if len(m) >= 4 and m not in STOPWORDS:
                    res.add(m)
                mot = []
    if mot:
        m = "".join(mot)
        if len(m) >= 4 and m not in STOPWORDS:
            res.add(m)
    return res


def _sim(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def analyser(db: Session, mois: int = 6, seuil_similarite: float = 0.35) -> dict:
    """Cluster les dossiers récents et retourne les top causes racines."""
    debut = datetime.utcnow() - timedelta(days=30 * mois)
    dossiers = list(db.scalars(
        select(models.Reclamation)
        .where(models.Reclamation.date_reception >= debut)
        .where(models.Reclamation.statut != "REJETE")
    ))
    if not dossiers:
        return {"clusters": [], "total_dossiers": 0, "periode_mois": mois}

    items = [(d, _tokens(d.description)) for d in dossiers]

    # Single-link agglomeratif simple
    clusters: list[list[int]] = [[i] for i in range(len(items))]
    fusionner = True
    iteration = 0
    while fusionner and iteration < 50:
        fusionner = False
        iteration += 1
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                # Représentant = union des tokens des membres
                tok_i = set().union(*(items[k][1] for k in clusters[i]))
                tok_j = set().union(*(items[k][1] for k in clusters[j]))
                if _sim(tok_i, tok_j) >= seuil_similarite:
                    clusters[i].extend(clusters[j])
                    clusters.pop(j)
                    fusionner = True
                    break
            if fusionner:
                break

    # On ne garde que les clusters de >= 2 dossiers (vrai pattern de récurrence)
    resultats = []
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        membres = [items[k][0] for k in cluster]
        tous_tokens = []
        for k in cluster:
            tous_tokens.extend(items[k][1])
        compte_tokens = Counter(tous_tokens)
        # Mots représentatifs = ceux qui apparaissent dans plusieurs dossiers du cluster
        mots_cles = [m for m, n in compte_tokens.most_common(8) if n >= 2][:6]

        categories = Counter(d.categorie for d in membres).most_common(1)[0][0]
        priorites = Counter(d.priorite for d in membres).most_common(1)[0][0]

        resultats.append({
            "id_cluster": len(resultats) + 1,
            "nb_dossiers": len(membres),
            "mots_cles": mots_cles,
            "categorie_dominante": categories,
            "priorite_dominante": priorites,
            "codes_exemples": [d.code for d in membres[:5]],
            "premiere_occurrence": min(d.date_reception for d in membres).isoformat(),
            "derniere_occurrence": max(d.date_reception for d in membres).isoformat(),
        })

    resultats.sort(key=lambda x: x["nb_dossiers"], reverse=True)

    return {
        "clusters": resultats[:15],
        "total_dossiers": len(dossiers),
        "periode_mois": mois,
        "nb_clusters_detectes": len(resultats),
    }
