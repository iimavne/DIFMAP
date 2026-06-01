/* Structure de la liste libre */
typedef struct {
    void *pool;           /* Grand bloc alloué une seule fois */
    size_t node_size;     /* Taille d'un nœud */
    void *free_list;      /* Chaîne des nœuds disponibles */
    int allocated;        /* Nombre de nœuds en utilisation */
} FreeList;

/* Initialisation : allouer un grand bloc une seule fois */
FreeList *new_freelist(size_t node_size, int num_nodes) {
    FreeList *fl = (FreeList *) malloc(sizeof(FreeList));
    fl->pool = (void *) malloc(node_size * num_nodes);
    fl->node_size = node_size;
    fl->free_list = fl->pool;  /* Tous les nœuds sont libres au départ */
    fl->allocated = 0;
    
    /* Chaîner les nœuds ensemble */
    char *ptr = (char *) fl->pool;
    for(int i = 0; i < num_nodes - 1; i++) {
        *(void **) ptr = ptr + node_size;  /* Pointeur vers le nœud suivant */
        ptr += node_size;
    }
    *(void **) ptr = NULL;  /* Dernier nœud pointe sur NULL */
    
    return fl;
}

/* Allocation rapide : prendre un nœud de la liste libre */
void *freelist_alloc(FreeList *fl) {
    if(fl->free_list == NULL) {
        return NULL;  /* Plus de nœuds disponibles */
    }
    
    void *node = fl->free_list;
    fl->free_list = *(void **) node;  /* Passer au nœud suivant */
    fl->allocated++;
    return node;
}

/* Libération rapide : remettre le nœud dans la liste libre */
void freelist_free(FreeList *fl, void *node) {
    *(void **) node = fl->free_list;  /* Insérer au début */
    fl->free_list = node;
    fl->allocated--;
}






