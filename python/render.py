import os
import boto3
import requests
import argparse

API_BASE_URL = "https://kekule.games/GL/API/Gamelist/"
API_AUTH = os.environ['API_KEY']

def check_gid_input(value):
    ivalue = int(value)
    if ivalue < 0:
        raise argparse.ArgumentTypeError("%s is an invalid Game ID" % value)
    elif requests.request('GET', f"{API_BASE_URL}/{value}/", headers = {'Authorization': API_AUTH}).status_code != 200:
        raise argparse.ArgumentTypeError("%s Does not exist on the system" % value)
    return ivalue


class Round:
    class Turn:
        list = []
        number = 0

    _Turns = {}
    number = 0

    def get_turn(self, number):
        return self._Turns[number]


arg_parser = argparse.ArgumentParser(description='Render Round')

# Add the arguments
arg_parser.add_argument('GID',
                        metavar='Game ID',
                        type=check_gid_input,
                        help='Game ID')

arg_parser.add_argument('RID',
                        metavar='Round ID',
                        type=int,
                        choices=range(1, 12),
                        help='Round ID')

args = arg_parser.parse_args()

game_id = args.GID
round_id = args.RID

s3 = boto3.client("s3")
s3.download_file(
    Bucket="kekule-web-private", Key=f"gamelogs/{game_id}.gamelog", Filename="game.gamelog"
)


