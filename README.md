
# Coinami

Coinami est une implémentation minimaliste et fonctionnelle d'une blockchain. Ce projet a été développé dans le cadre de la Nexa Digital School et vise à démontrer les concepts fondamentaux des registres distribués. Dans l'idéal, ce réseau a vocation à s'intégrer avec un projet de scraping de petites annonces (réparti sur deux dépôts).

## 🚀 Installation et Démarrage

### Prérequis

* Python 3.8+
* `pip` et `venv`

### Installation

1. Cloner le dépôt et créer un environnement virtuel :

```bash
   git clone <ton-repo-url>
   cd coinami
   python -m venv venv
   source venv/bin/activate  # Sur Windows : venv\Scripts\activate

```

1. Installer les dépendances :

```bash
pip install -r requirements.txt

```

### Lancement multi-nœuds (Démonstration P2P)

Le réseau local de démonstration fonctionne avec 3 nœuds.

1. Lancer le Nœud A (Port 5000) : `python src/p2p/node.py --port 5000 --difficulty 1`
2. Lancer le Nœud B (Port 5001) : `python src/p2p/node.py --port 5001 --difficulty 1`
3. Lancer le Nœud C (Port 5002) : `python src/p2p/node.py --port 5002 --difficulty 1`

### Test d'interaction entre nœuds

Pour tester l'interaction entre les nœuds de la blockchain :

```bash
python test_nodes_interaction.py
```

Ce script valide que les nœuds peuvent communiquer, synchroniser les transactions et les blocs correctement.

## 🏗️ Architecture et Modèle de Données

Le projet est structuré autour de 4 modules principaux dans le dossier `src/` :

* **`crypto/`** : Gestion des clés, signatures et fonctions de hachage.
* **`core/`** : Le cœur de la blockchain comprenant :
* `Transaction` : Définit l'expéditeur, le destinataire, le montant, le nonce et le payload.
* `BlockHeader` & `Block` : Contient le hash du bloc précédent (`prev_hash`), la racine Merkle (`merkle_root`), le timestamp et le nonce.
* `Chain` : Gère la liste des blocs, la difficulté de minage et les transactions en attente.

* **`p2p/`** : L'infrastructure réseau avec la classe `Node` qui maintient sa propre `Chain`, son `State` et son `mempool`.
* **`contracts/`** : Moteur d'exécution déterministe (`State`) mettant à jour les soldes (`balances`) et les contrats (`escrow`).

## 🔐 Cryptographie, Hashing et Intégrité

* **Wallets et Identités** : Les utilisateurs génèrent une paire de clés (publique/privée) à partir de laquelle dérive leur adresse.
* **Signatures de transactions** : Les transactions sont signées côté client (via la classe `Wallet` et la méthode `sign_tx`) et vérifiées par les nœuds via `is_valid()`. Un système de `nonce` prévient les attaques par rejeu.
* **Validation** : La chaîne assure l'intégrité via le hachage des transactions, le calcul d'un arbre de Merkle simplifié et le chaînage strict (le bloc N contient le hash du bloc N-1).

## 🌐 Réseau P2P Minimal

Le réseau permet la découverte de pairs et la diffusion des transactions et des blocs.

* Chaque transaction injectée est vérifiée, ajoutée au mempool puis diffusée (broadcast) si elle est valide.
* Un mécanisme d'anti-boucle basé sur l'ID des messages empêche l'engorgement du réseau.
* Le consensus appliqué est un Proof of Work (PoW) simplifié.

## 📜 Smart Contracts (Escrow)

Coinami intègre un moteur de contrats minimalistes permettant l'exécution déterministe de modifications d'état.
Le contrat d'**Escrow** (séquestre) fonctionne selon la machine d'état suivante :

1. **Created** : Les fonds sont envoyés au contrat et stockés dans `state.escrow[id]`.
2. **Locked** : En attente de validation.
3. L'état évolue ensuite vers **Released** (fonds transférés au destinataire) ou **Refunded** (fonds renvoyés à l'expéditeur en cas de litige ou d'expiration).

## 🧪 Tests

Les tests automatisés sont situés dans le dossier `tests/`.
Pour exécuter la suite complète (signatures, intégrité, validation, contrats) :

```bash
pytest tests/
```
