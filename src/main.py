import sys
import os
import spotipy
import dateutil.parser
import spotipy.util as sp_util
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOauthError
from spotipy.client import SpotifyException
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

# Define the scopes that we need access to
# https://developer.spotify.com/web-api/using-scopes/
scope = 'user-library-read playlist-read-private'


ALBUM_A_DAY_ID = '5Exd8CXJ9NSrUWhd1iMwXI'
OWNER_ID = 'markster3910'
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')


################################################################################
# Main Demo Function
################################################################################

def main():
    """
    Our main function that will get run when the program executes
    """
    print_header('Album a day updater', length=50)

    albums = get_albums()
    update_sheet(albums)

    print_header('Done!')


################################################################################
# Convenience Functions
################################################################################

def print_header(message, length=30):
    """
    Given a message, print it with a buncha stars all header-like
    :param message: The message you want to print
    :param length: The number of stars you want to surround it
    """
    print('\n' + ('*' * length))
    print(message)
    print('*' * length)


def track_string(track):
    """
    Given a track, return a string describing the track:
    Track Name - Artist1, Artist2, etc...
    :param track:
    :return: A string describing the track
    """
    track_name = track.get('name')
    artist_names = ', '.join([artist.get('name') for artist in track.get('artists', [])])
    return '{} - {}'.format(track_name, artist_names)




################################################################################
# Authentication Functions
################################################################################

def authenticate_client():
    """
    Using credentials from the environment variables, attempt to authenticate with the spotify web API.  If successful,
    create a spotipy instance and return it.
    :return: An authenticated Spotipy instance
    """
    try:
        # Get an auth token for this user
        client_credentials = SpotifyClientCredentials()

        spotify = spotipy.Spotify(client_credentials_manager=client_credentials)
        return spotify
    except SpotifyOauthError as e:
        print('API credentials not set.  Please see README for instructions on setting credentials.')
        sys.exit(1)


def authenticate_user():
    """
    Prompt the user for their username and authenticate them against the Spotify API.
    (NOTE: You will have to paste the URL from your browser back into the terminal)
    :return: (username, spotify) Where username is the user's username and spotify is an authenticated spotify (spotipy) client
    """
    # Prompt the user for their username
    username = input('\nWhat is your Spotify username: ')

    try:
        # Get an auth token for this user
        token = sp_util.prompt_for_user_token(username, scope=scope)

        spotify = spotipy.Spotify(auth=token)
        return username, spotify
    except SpotifyException as e:
        print('API credentials not set.  Please see README for instructions on setting credentials.')
        sys.exit(1)
    except SpotifyOauthError as e:
        redirect_uri = os.environ.get('SPOTIPY_REDIRECT_URI')
        if redirect_uri is not None:
            print("""
    Uh oh! It doesn't look like that URI was registered as a redirect URI for your application.
    Please check to make sure that "{}" is listed as a Redirect URI and then Try again.'
            """.format(redirect_uri))
        else:
            print("""
    Uh oh! It doesn't look like you set a redirect URI for your application.  Please add
    export SPOTIPY_REDIRECT_URI='http://localhost/'
    to your `credentials.sh`, and then add "http://localhost/" as a Redirect URI in your Spotify Application page.
    Once that's done, try again.'""")
        sys.exit(1)


################################################################################
# Demo Functions
################################################################################

def get_albums():
    """
    This function will get all of a user's playlists and allow them to choose songs that they want audio features
    for.
    """
    # Initialize Spotipy
    spotify = authenticate_client()

    # Get the playlist tracks
    tracks = []
    total = 1
    # The API paginates the results, so we need to keep fetching until we have all of the items
    while len(tracks) < total:
        tracks_response = spotify.user_playlist_tracks(OWNER_ID, ALBUM_A_DAY_ID, offset=len(tracks))
        tracks.extend(tracks_response.get('items', []))
        total = tracks_response.get('total')

    album_map = {}

    for track in tracks:
        added_at = dateutil.parser.parse(track.get('added_at'))
        track_info = track.get('track', {})
        album_info = track_info.get('album', {})
        album_id = album_info.get('id')

        if album_id not in album_map:
            album_map[album_id] = {
                'date': added_at.strftime('%m/%d/%Y'),
                'name': album_info.get('name'),
                'artists': ', '.join([a.get('name') for a in album_info.get('artists', [])]),
                'uri': album_info.get('uri')
            }


    # Print out our tracks along with the list of artists for each
    # print_header('Albums List')

    albums_list = sorted(album_map.values(), key=lambda x: x.get('date'))

    # Separate columns by a pipe -- https://support.google.com/docs/answer/6325535?co=GENIE.Platform%3DDesktop&hl=en
    # for album in albums_list:
    #     print('{date}||{name}|{artists}|{uri}'.format(**album))

    return albums_list

def update_sheet(albums):
    # Build some google creds
    credentials = GoogleCredentials.get_application_default()
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')
    service = build('sheets',
        'v4',
        credentials=credentials,
        discoveryServiceUrl=discoveryUrl)

    rangeName = 'Listened!A2:E'
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=rangeName).execute()
    rows = result.get('values', [])

    # Pull out the spotify URIs
    sheet_uris = [row[4] for row in rows if len(row) >= 5 and row[4] != '']

    albums_to_add = [album for album in albums if album.get('uri') not in sheet_uris]
    print(albums_to_add)


    offset = '=IF(ISBLANK(INDIRECT("A" & ROW())), "", (-1*(DATEDIF(DATE(2017,1,1),INDIRECT("A" & ROW()),"D")-(ROW()-2))))'
    values = [[a['date'], offset, a['name'], a['artists'], a['uri']] for a in albums_to_add]

    body = {
      "range": rangeName,
      "majorDimension": "ROWS",
      "values": values
    }

    service.spreadsheets().values().append(spreadsheetId=SHEET_ID,
        range=rangeName,
        valueInputOption='USER_ENTERED',
        body=body).execute()


if __name__ == '__main__':
    main()
