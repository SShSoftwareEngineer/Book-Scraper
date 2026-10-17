from importlib.metadata import distributions

for dist in distributions():
    for f in dist.files or []:
        if str(f).replace('\\', '/').startswith('redis/'):
            print(dist.metadata['Name'], dist.version)
            break