def get_storage_path(album):

    if album.name == 'no album':
        return join(album.artist.name.encode('utf-8'))

    return join(album.artist.name.encode('utf-8'), album.name.encode('utf-8'))
