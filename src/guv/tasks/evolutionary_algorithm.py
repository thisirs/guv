import numpy as np

def generate_variants(partitions, num_variants=10, num_permutations=3):
    """
    Génère des variantes d'un vecteur en ajoutant une petite perturbation aléatoire.
    """

    variants = np.tile(partitions, (num_variants - 1, 1))
    n_rows, n_cols = variants.shape

    # Générer des indices aléatoires uniques pour chaque ligne
    indices = np.stack([np.random.choice(n_cols, size=num_permutations, replace=False) for _ in range(n_rows)])

    # Extraire les valeurs correspondant aux indices sélectionnés
    valeurs = np.take_along_axis(variants, indices, axis=1)

    # Générer une permutation aléatoire de ces indices par ligne
    shuffled_indices = np.apply_along_axis(np.random.permutation, 1, indices)

    # Remettre les valeurs permutées dans le tableau original
    np.put_along_axis(variants, shuffled_indices, valeurs, axis=1)

    arr = np.concatenate([partitions, variants], axis=0)
    np.random.shuffle(arr)

    return arr


def evaluate(partitions, penalty):
    """
    Fonction d'évaluation qui attribue un score à un vecteur (à définir selon le problème).
    """

    coocurrences = (partitions[:, None, :] == partitions[:, :, None]).astype(int)
    return np.sum(coocurrences * penalty, axis=(1, 2))


def evolutionary_algorithm(initial_partition, penalty, optimal_score, max_variants=1000, num_variants=10, num_permutations=4, top_k=3):
    """
    Algorithme évolutif qui génère et sélectionne les meilleurs vecteurs sur plusieurs générations.
    """
    current_partitions = initial_partition[None, :]
    current_num_variants = 0

    while current_num_variants < max_variants:
        # Génération des variantes
        new_partitions = generate_variants(current_partitions, num_variants=num_variants, num_permutations=num_permutations)

        # Évaluation et sélection
        scored_partitions = evaluate(new_partitions, penalty)
        best_indexes = scored_partitions.argsort()[:top_k]
        current_num_variants += new_partitions.shape[0]

        # Sélection des meilleurs
        current_partitions = new_partitions[best_indexes, :]
        current_scores = scored_partitions[best_indexes]

        if current_scores[0] == optimal_score:
            return current_num_variants, optimal_score, current_partitions[0, :]

    return current_num_variants, current_scores[0], current_partitions[0, :]
