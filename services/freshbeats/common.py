from os.path import join

def get_storage_path(album):

    if album.name == 'no album':
        return join(album.artist.name)

    return join(album.artist.name, album.name)
