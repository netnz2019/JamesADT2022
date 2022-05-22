import os
import boto3
import requests
import argparse
import warnings
from math import cos, sin, pi
from PIL import Image, ImageDraw

# Kekule Games API URL
API_BASE_URL = "https://kekule.games/GL/API/Gamelist/"

# Get Kekule Games API credentials from the environment
API_AUTH = os.environ['API_KEY']


def check_gid_input(value):
    """
    This Function checks the game ID against the Kekule Games Server to ensure that the supplied game actually exists.
    If the ID does NOT exist it raises an argparse error

    :param value: Input Game ID
    :return: Input Game ID if it is valid
    """
    ivalue = int(value)

    # no game ID should be less than 0. check this first to avoid unnecessary requests to the Kekule Games API
    if ivalue < 0:
        raise argparse.ArgumentTypeError("%s is an invalid Game ID" % value)
    elif requests.request('GET', f"{API_BASE_URL}/{value}/", headers = {'Authorization': API_AUTH}).status_code != 200:
        raise argparse.ArgumentTypeError("%s Does not exist on the system" % value)
    return ivalue


def convert_coords(x, y):
    x_prime = 960 + cos(30 * pi / 180) * x - cos(30 * pi / 180) * y
    y_prime = sin(30 * pi / 180) * x + sin(30 * pi / 180) * y
    print(x_prime, y_prime)
    return int(x_prime), int(y_prime)


class Round:
    class Turn:
        list = []
        number = 0

    _Turns = {}
    __turn_counter = 0

    def get_turn(self, number):
        try:
            return self._Turns[number]
        except KeyError:
            raise KeyError("That Turn does not exist within this Round")

    def get_number_turns(self):
        return len(self._Turns)

    def add_turn(self, in_list, t_number=-1):
        if t_number != -1:
            number = t_number
        else:
            self.__turn_counter += 1
            number = self.__turn_counter

        self._Turns[number] = self.Turn()
        self._Turns[number].list = in_list
        self._Turns[number].number = number



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


# Uncomment to test
# s3 = boto3.client("s3")
# s3.download_file(
#     Bucket="kekule-web-private", Key=f"gamelogs/{game_id}.gamelog", Filename="game.gamelog"
# )

with open('game.gamelog', 'r') as file:
    content = file.read()
    content = content.partition(f'game = {round_id}')
    content = content[2].partition(f'game = {int(round_id) + 1}')
    content = content[0].split('\n')
    if content[0] == '':
        content.pop(0)
    if content[-1] == '':
        content.pop(-1)
    elif content[-1] == "end":
        content.pop(-1)
data = Round()

error_count = 0
for turn in content:
    turn = eval(turn)
    for tup in turn:
        if tup[0] not in range(0, 100) or tup[1] not in range(0, 100):
            error_count += 1
            if error_count <= 3:
                warnings.warn(f"Token outside board! Ignoring Turn. {error_count} of 3", RuntimeWarning)
            else:
                raise RuntimeError(f"Token outside board! To many stray Tokens. Please check the log file {game_id}.gamelog, round {round_id}. Terminating")
    data.add_turn(turn)

for turn_number in range(1, data.get_number_turns()):
    turn = data.get_turn(turn_number)

    img = Image.new("RGB", (1920, 1080))
    img1 = ImageDraw.Draw(img)
    img1.rectangle((0, 0) + img.size, fill='white')

    img1.polygon([(convert_coords(0, 0)), (convert_coords(0, 1080)), (convert_coords(1080, 1080)), (convert_coords(1080, 0))], "white", "black")

    # vertical lines at an interval of "line_distance" pixel
    for x in range(10, 1080, 10):
        img1.line(convert_coords(x, 0) + convert_coords(x, img.height), fill="#b4b4b4")
    # # horizontal lines at an interval of "line_distance" pixel
    # for y in range(line_distance, img.height, line_distance):
    #     img1.line((0, y) + (img.width, y), fill="#b4b4b4")

    img1.polygon(
        [(convert_coords(0, 0)), (convert_coords(0, 10)), (convert_coords(10, 10)), (convert_coords(10, 0))],
        "yellow")





