def cluster_key(product, version, platform, type):
    return '-'.join((product.short, version, platform, type.short))
