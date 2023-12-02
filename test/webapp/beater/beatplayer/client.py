from webapp.beater.beatplayer.client import BeatplayerClient

def printresults(response_json):

    print(f'response_json ({type(response_json)})')
    print(f'content: {response_json}')

client = BeatplayerClient('http://127.0.0.1:9000')

printresults(client.echo())

# printresults(client.healthz())

# response_json = client.healthz()

# print(f'response_json')
# print(f'type: {type(response_json)}')
# print(f'content: {response_json}')

# response_json = client.play('http://play.url', '///some/filepath', 'http://127.0.0.1:8001', 'http://127.0.0.1:9000')

# print(f'response_json')
# print(f'type: {type(response_json)}')
# print(f'content: {response_json}')