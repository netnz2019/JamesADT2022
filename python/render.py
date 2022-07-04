import os
import io
import cv2
import glob
import boto3
import requests
import argparse
import warnings
from natsort import natsorted
from math import cos, sin, pi
from PIL import Image, ImageDraw, ImageFont
from matplotlib import pyplot as plt

# Kekule Games API URL
API_BASE_URL = "https://kekule.games/GL/API/Gamelist"


def check_gid_input(value):
    """
    This Function checks the game ID against the Kekule Games Server to ensure that the supplied game actually exists.
    If the ID does NOT exist it raises an argparse error

    :param value: Input Game ID
    :type value: str
    :return: Input Game ID
    :rtype: int
    """

    ivalue = int(value)

    # no game ID should be less than 0. check this first to avoid unnecessary requests to the Kekule Games API
    if ivalue < 0:
        raise argparse.ArgumentTypeError("%s is an invalid Game ID" % value)
    elif requests.request('GET', f"{API_BASE_URL}/{ivalue}/", headers={'Authorization': API_AUTH}).status_code != 200:
        # if GID does not exist
        raise argparse.ArgumentTypeError("%s Does not exist on the system" % value)

    return ivalue


def convert_coords(x, y):
    """
    This Function takes non-oblique (2D) image coordinates and translates them 30 degrees to make the coordinates
    oblique

    :param x: 2D x coordinate
    :type x: int
    :param y: 2D y coordinate
    :type y: int
    :return: Oblique (3D) coordinates
    :rtype: tuple[int, int]
    """

    # math to convert coords
    x_prime = 960 + cos(30 * pi / 180) * x - cos(30 * pi / 180) * y
    y_prime = sin(30 * pi / 180) * x + sin(30 * pi / 180) * y
    return int(x_prime), int(y_prime)


def clamp(n, minn, maxn):
    """
    Clamps values to remain within specified range
    :param n: input number
    :type n: float
    :param minn: Minimum to clamp to
    :type minn: int
    :param maxn: Maximum to clamp to
    :type maxn: int
    :return: clamped input number
    :rtype: float
    """

    return max(min(maxn, n), minn)


class Round:
    """
    This class represents a Game Round. A round comprises turns
    """

    class Turn:
        """
        This class represents a Round Turn.
        """

        list = []  # Turn list
        number = 0  # Turn number within round

    _Turns = {}  # Hidden list of turns
    __turn_counter = 0  # counter of how many turns are in the round.

    def get_turn(self, number):
        """
        This function gets a specified turn from a supplied number
        :param number: Wanted turn number
        :type number: int
        :return: specified Turn object
        :rtype: Round.Turn
        """

        # Try to get the specified turn raise a key error if it doesn't exist
        try:
            return self._Turns[number]
        except KeyError:
            raise KeyError("That Turn does not exist within this Round")

    def get_number_turns(self):
        """
        Get how many turns in round
        :return: Amount of turns within round
        :rtype: int
        """

        return len(self._Turns)

    def add_turn(self, in_list, t_number=None):
        """
        Adds a Turn to the Round.

        :param in_list: list representation of the turn
        :type in_list: list
        :param t_number: Turn number
        :type t_number: int
        """

        if t_number is not None:
            number = t_number
        else:
            self.__turn_counter += 1
            number = self.__turn_counter

        self._Turns[number] = self.Turn()
        self._Turns[number].list = in_list
        self._Turns[number].number = number


def convert_frames_to_video(pathIn, pathOut, fps):
    """
    Collates all .png files in a directory into a mp4 file and saves to disk

    :param pathIn: file path to images
    :type pathIn: str
    :param pathOut: Path to save mp4 to
    :type pathOut: str
    :param fps: Frame rate of the video
    :type fps: int
    """

    frame_size = (1920, 1080)

    out = cv2.VideoWriter(pathOut, cv2.VideoWriter_fourcc(*'avc1'), fps, frame_size)

    for filename in natsorted(glob.glob(os.path.join(pathIn, '*.png'))):
        img = cv2.imread(filename)
        out.write(img)

    out.release()


def main():

    # set up argument handler
    arg_parser = argparse.ArgumentParser(description='Render Round')

    # Add arguments
    arg_parser.add_argument('GID',
                            metavar='Game ID',
                            type=check_gid_input,
                            help='Game ID')

    arg_parser.add_argument('RID',
                            metavar='Round ID',
                            type=int,
                            choices=range(1, 12),
                            help='Round ID')

    # Add keyword arguments
    arg_parser.add_argument('--speed', metavar='Speed', type=float, default=100, help='Speed of output video in %')

    arg_parser.add_argument('--dark', help='Enable dark mode', action="store_true")

    arg_parser.add_argument('--offline', help='Disable S3 connectivity', action="store_false")

    args = arg_parser.parse_args()

    # map arguments to variables
    game_id = args.GID
    round_id = args.RID
    speed = args.speed
    dark = args.dark
    online = args.offline

    # get info about the game form the kekule games API
    game_info = requests.request('GET', f"{API_BASE_URL}/{game_id}/", headers={'Authorization': API_AUTH}).json()

    if online: # if online mode enabled
        s3 = boto3.client("s3")  # set up s3 connection
        # download gamelog from S3 bucket and save
        s3.download_file(
            Bucket="kekule-web-private", Key=f"gamelogs/{game_id}.gamelog", Filename="game.gamelog"
        )

    # open gamelog
    with open('game.gamelog', 'r') as file:
        content = file.read()
        content = content.partition(f'game = {round_id}')  # partition to get the start of game specified
        content = content[2].partition(f'game = {int(round_id) + 1}')  # get lines to the end of the game
        content = content[0].split('\n')  # split into list by new line
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
                    raise RuntimeError(
                        f"Token outside board! To many stray Tokens. Please check the log file {game_id}.gamelog, round {round_id}. Terminating")
        data.add_turn(turn)

    rstr_all = []
    bstr_all = []

    for turn_number in range(1, data.get_number_turns()):
        rstr = 0
        bstr = 0
        hist = [[], []]
        all_draw = []
        turn = data.get_turn(turn_number)

        img = Image.new("RGB", (1920, 1080))
        img1 = ImageDraw.Draw(img)
        if dark:
            img1.rectangle((0, 0) + img.size, fill='black')
            white = "black"
            black = "white"
        else:
            img1.rectangle((0, 0) + img.size, fill='white')
            line_fill = "#b4b4b4"
            white = "white"
            black = "black"

        if dark:
            plt.style.use('dark_background')
        img1.polygon(
            [(convert_coords(0, 0)), (convert_coords(0, 1010)), (convert_coords(1010, 1010)), (convert_coords(1010, 0))],
            white, black)

        # vertical lines at an interval of "line_distance" pixel
        for x in range(10, 1010, 10):
            img1.line(convert_coords(x, 0) + convert_coords(x, 1010), fill="#b4b4b4")
        # horizontal lines at an interval of "line_distance" pixel
        for y in range(10, 1010, 10):
            img1.line(convert_coords(0, y) + convert_coords(1010, y), fill="#b4b4b4")

        img1.polygon(
            [(convert_coords(0, 1010)),
             (85, 523),
             (960, 1030),
             (960, 1010)],
            fill='grey'
        )

        img1.polygon(
            [(1835, 505),
             (1835, 525),
             (960, 1030),
             (960, 1010)],
            fill='grey'
        )

        for tup in turn.list:
            if tup[3] == 'B':
                rgb = (clamp(220 - (11 * int(tup[2])), 0, 255), clamp(220 - (11 * int(tup[2])), 0, 255), 255)
                hex_result = "".join([format(val, '02X') for val in rgb])
                outline_cl = 'blue'
                bstr += tup[2]
                hist[0].append(tup[2])
            elif tup[3] == 'R':
                rgb = (255, clamp(220 - (11 * int(tup[2])), 0, 255), clamp(220 - (11 * int(tup[2])), 0, 255))
                hex_result = "".join([format(val, '02X') for val in rgb])
                outline_cl = 'red'
                rstr += tup[2]
                hist[1].append(tup[2])


            bottom_coords = [(convert_coords(tup[0] * 10, (tup[1] * 10) + 10)),
                             (convert_coords((tup[0] * 10) + 10, (tup[1] * 10) + 10)),
                             (convert_coords((tup[0] * 10) + 10, tup[1] * 10))]

            in_coords = [(convert_coords(tup[0] * 10 + 2, tup[1] * 10 + 2)),
                         (convert_coords(tup[0] * 10 + 2, (tup[1] * 10) + 10 - 2)),
                         (convert_coords((tup[0] * 10) + 10 - 2, (tup[1] * 10) + 10 - 2)),
                         (convert_coords((tup[0] * 10) + 10 - 2, tup[1] * 10 + 2))]

            top_coords = []

            for tup in in_coords:
                tup_out = (tup[0], tup[1] - 5)
                top_coords.append(tup_out)

            fill_coords = bottom_coords.copy()
            int_coords = top_coords.copy()[1:]
            int_coords.sort(reverse=True)
            fill_coords.extend(int_coords)
            all_draw.append({"fill": fill_coords,
                             "bottom": bottom_coords,
                             "top": top_coords,
                             "hex": hex_result,
                             "outline": outline_cl
                             })

        for token in all_draw:
            img1.line(
                token["bottom"],
                fill=token["outline"],
            )

        for token in all_draw:
            img1.polygon(
                token["fill"],
                fill=f'#{token["hex"]}'
            )

        for token in all_draw:
            img1.polygon(
                token["top"],
                fill=f'#{token["hex"]}',
                outline=token["outline"]
            )

        rstr_all.append(rstr)
        bstr_all.append(bstr)
        x = [i for i in range(len(bstr_all))]

        if dark:
            plt.style.use('dark_background')
        plt.plot(x, rstr_all, color='red')
        plt.plot(x, bstr_all, color='blue')
        plt.xlabel("Turn Number")
        plt.ylabel("Total Strength")

        img_buf = io.BytesIO()

        plt.savefig(img_buf, format='png', bbox_inches='tight', pad_inches=0)
        plt.close()
        plot = Image.open(img_buf)
        plot.thumbnail((400, 400), Image.ANTIALIAS)
        img.paste(plot, (40, 2))

        img_buf.close()
        img_buf = io.BytesIO()

        if dark:
            plt.style.use('dark_background')
        plt.hist(hist, histtype='bar', label=['blue', 'red'], color=['blue', 'red'], log=True)
        plt.ylabel("Number")
        plt.xlabel("Strength")
        plt.legend()
        plt.savefig(img_buf, format='png', bbox_inches='tight', pad_inches=0)
        plt.close()
        plot = Image.open(img_buf)
        plot.thumbnail((400, 400), Image.ANTIALIAS)
        img.paste(plot, (40, 750))

        Font20 = ImageFont.truetype('DejaVuSans.ttf', 20)
        Font10 = ImageFont.truetype('DejaVuSans.ttf', 10)

        # Add Text to an image
        img1.text((1650, 785), "# Tokens", font=Font20, fill=black)
        img1.text((1650, 815), f"Red {len(hist[1])}", font=Font20, fill="red")
        img1.text((1650, 845), f"Blue {len(hist[0])}", font=Font20, fill="blue")

        img1.rectangle([(1650, 70), (1690, 90)], fill="blue")
        img1.text((1710, 70), game_info['player1'], font=Font20, fill=black)
        img1.rectangle([(1650, 110), (1690, 130)], fill="red")
        img1.text((1710, 110), game_info['player2'], font=Font20, fill=black)

        img.save(f"{turn_number}.png")

    convert_frames_to_video(os.getcwd(), f'{game_id}_{round_id}.mp4', 24 * (speed / 100))

    if online:

        s3.upload_file(f'{game_id}_{round_id}.mp4', "kekule-web-media", f'video/{game_id}_{round_id}.mp4',)


        payload = {'rendered': True}
        headers = {'Authorization': API_AUTH}
        url = f"https://kekule.games/GL/API/Gamelist/{game_id}/"

        response = requests.request("PUT", url, headers=headers, data=payload)
        if response.status_code != 200:
            warnings.warn("Possible failure communicating to Kekule Games API. Please check server log", Warning)


if __name__ == "__main__":
    # Get Kekule Games API credentials from the environment
    API_AUTH = os.environ['API_KEY']
    main()
