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
    return int(x_prime), int(y_prime)  # return converted coordinates


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
    This class represents a Game Round. A round comprises turns.

    The class holds two hidden variables:
    _Turns: A dictionary that holds all the turns within this round.
    __turn_counter: An integer used by get_number_turns to return the amount of turns within the round and
     used by add_turn to automatically set the turn number if it is undefined on call.
    """

    class Turn:
        """
        This class represents a Turn.
        It holds two Variables:
        list: list representation of turn data
        number: the turn number
        """

        list = []  # Turn list
        number = 0  # Turn number within round

    _Turns = {}  # Hidden list of turns
    __turn_counter = 0  # counter of how many turns are in the round.

    def get_turn(self, number):
        """
        This function gets a specified turn from a supplied turn number
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

    if online:  # if online mode enabled
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
        # remove unwanted spacing and tagging if it exists
        if content[0] == '':
            content.pop(0)
        if content[-1] == '':
            content.pop(-1)
        elif content[-1] == "end":
            content.pop(-1)
    data = Round()  # create round

    for turn in content:  # for turn in input file
        turn = eval(turn)
        for tup in turn:  # for tuple in turn list
            if tup[0] not in range(0, 100) or tup[1] not in range(0, 100):  # if token not on board
                raise RuntimeError(
                    f"Token outside board! To many stray Tokens. Please check the log file {game_id}.gamelog, round {round_id}. Terminating")
        data.add_turn(turn)

    rstr_all = []  # persistent across turns red strength data
    bstr_all = []  # persistent across turns blue strength data

    for turn_number in range(1, data.get_number_turns()):
        rstr = 0  # red strength
        bstr = 0  # blue strength
        hist = [[], []]  # data for histogram
        all_draw = []   # tokens to draw
        turn = data.get_turn(turn_number)  # retrieve turn

        img = Image.new("RGB", (1920, 1080))  # create PIL image
        img1 = ImageDraw.Draw(img)  # set up drawing on PIL image
        if dark:
            img1.rectangle((0, 0) + img.size, fill='black')  # draw background
            white = "black"  # set colour of everything that would normally be white to black
            black = "white"  # set colour of everything that would normally be balck to white
        else:
            img1.rectangle((0, 0) + img.size, fill='white')  # draw background
            white = "white"  # set white to be white since dark mode is not enabled
            black = "black"  # set black to be black since dark mode is not enabled

        if dark:
            plt.style.use('dark_background')
        img1.polygon(
            [(convert_coords(0, 0)), (convert_coords(0, 1010)), (convert_coords(1010, 1010)), (convert_coords(1010, 0))],
            white, black)  # make board outline

        """ The following creates squares within the previously made board"""
        # vertical lines at an interval of "line_distance" pixel
        for x in range(10, 1010, 10):
            img1.line(convert_coords(x, 0) + convert_coords(x, 1010), fill="#b4b4b4")
        # horizontal lines at an interval of "line_distance" pixel
        for y in range(10, 1010, 10):
            img1.line(convert_coords(0, y) + convert_coords(1010, y), fill="#b4b4b4")

        # draw grey box's below board
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

        for tup in turn.list:  # for token in turn
            if tup[3] == 'B':  # if the token is blue's
                # change blue colour according to the tokens strength
                rgb = (clamp(220 - (11 * int(tup[2])), 0, 255), clamp(220 - (11 * int(tup[2])), 0, 255), 255)
                # convert rgb values to hex
                hex_result = "".join([format(val, '02X') for val in rgb])
                outline_cl = 'blue'
                # add the strength of this token to the blue total
                bstr += tup[2]
                # add the strength of this token to the blue histogram dat
                hist[0].append(tup[2])
            elif tup[3] == 'R':
                # change red colour according to the tokens strength
                rgb = (255, clamp(220 - (11 * int(tup[2])), 0, 255), clamp(220 - (11 * int(tup[2])), 0, 255))
                # convert rgb values to hex
                hex_result = "".join([format(val, '02X') for val in rgb])
                outline_cl = 'red'
                # add the strength of this token to the red total
                rstr += tup[2]
                # add the strength of this token to the red histogram dat
                hist[1].append(tup[2])

            # generate coordinates of the bottom of the token to be drawn later on
            bottom_coords = [(convert_coords(tup[0] * 10, (tup[1] * 10) + 10)),
                             (convert_coords((tup[0] * 10) + 10, (tup[1] * 10) + 10)),
                             (convert_coords((tup[0] * 10) + 10, tup[1] * 10))]

            # generate intermediary coordinates of the top of the token
            in_coords = [(convert_coords(tup[0] * 10 + 2, tup[1] * 10 + 2)),
                         (convert_coords(tup[0] * 10 + 2, (tup[1] * 10) + 10 - 2)),
                         (convert_coords((tup[0] * 10) + 10 - 2, (tup[1] * 10) + 10 - 2)),
                         (convert_coords((tup[0] * 10) + 10 - 2, tup[1] * 10 + 2))]

            top_coords = []

            for tup in in_coords:
                tup_out = (tup[0], tup[1] - 5)  # remove 5 pixels from the intermediate coordinates to make them go
                # up the image when drawn
                top_coords.append(tup_out)

            """ The following creates the coordinates needed for 
            drawing the fill between the top and bottom of the token """
            fill_coords = bottom_coords.copy()
            int_coords = top_coords.copy()[1:]
            int_coords.sort(reverse=True)
            fill_coords.extend(int_coords)
            # add all the coordinates and colour to a dict then append to the list to be drawn later
            all_draw.append({"fill": fill_coords,
                             "bottom": bottom_coords,
                             "top": top_coords,
                             "hex": hex_result,
                             "outline": outline_cl
                             })

        # draw the bottom of all the tokens
        for token in all_draw:
            img1.line(
                token["bottom"],
                fill=token["outline"],
            )

        # draw the fill of all the tokens
        for token in all_draw:
            img1.polygon(
                token["fill"],
                fill=f'#{token["hex"]}'
            )

        # draw the top of all the tokens
        for token in all_draw:
            img1.polygon(
                token["top"],
                fill=f'#{token["hex"]}',
                outline=token["outline"]
            )

        # append strengths to all strength list for each player
        rstr_all.append(rstr)
        bstr_all.append(bstr)

        if dark:
            plt.style.use('dark_background')

        x = [i for i in range(len(bstr_all))]  # make x coord for plot
        # plot lines
        plt.plot(x, rstr_all, color='red')
        plt.plot(x, bstr_all, color='blue')
        # add labels
        plt.xlabel("Turn Number")
        plt.ylabel("Total Strength")

        img_buf = io.BytesIO()  # set up buffer to save plot to

        plt.savefig(img_buf, format='png', bbox_inches='tight', pad_inches=0)  # save plot
        plt.close()
        plot = Image.open(img_buf)  # open plot in PIL
        plot.thumbnail((400, 400), Image.ANTIALIAS)  # resize plot
        img.paste(plot, (40, 2))  # paste onto main image

        img_buf.close()
        img_buf = io.BytesIO()  # set up buffer to save plot to

        if dark:
            plt.style.use('dark_background')
        plt.hist(hist, histtype='bar', label=['blue', 'red'], color=['blue', 'red'], log=True)  # make plot
        # add labels
        plt.ylabel("Number")
        plt.xlabel("Strength")
        plt.legend()  # add legend

        plt.savefig(img_buf, format='png', bbox_inches='tight', pad_inches=0)  # save plot
        plt.close()
        plot = Image.open(img_buf)  # open plot in PIL
        plot.thumbnail((400, 400), Image.ANTIALIAS)  # resize plot
        img.paste(plot, (40, 750))  # paste onto main image

        Font20 = ImageFont.truetype('DejaVuSans.ttf', 20)

        # Add number of tokens to image
        img1.text((1650, 785), "# Tokens", font=Font20, fill=black)
        img1.text((1650, 815), f"Red {len(hist[1])}", font=Font20, fill="red")
        img1.text((1650, 845), f"Blue {len(hist[0])}", font=Font20, fill="blue")

        # add player legend to image
        img1.rectangle([(1650, 70), (1690, 90)], fill="blue")
        img1.text((1710, 70), game_info['player1'], font=Font20, fill=black)
        img1.rectangle([(1650, 110), (1690, 130)], fill="red")
        img1.text((1710, 110), game_info['player2'], font=Font20, fill=black)

        img.save(f"{turn_number}.png")  # save main image to disk

    convert_frames_to_video(os.getcwd(), f'{game_id}_{round_id}.mp4', 24 * (speed / 100))  # convert all images to video

    if online:  # if online mode enabled

        # Upload resultant mp4 video to S3
        s3.upload_file(f'{game_id}_{round_id}.mp4', "kekule-web-media", f'video/{game_id}_{round_id}.mp4',)

        payload = {'rendered': True}
        headers = {'Authorization': API_AUTH}
        url = f"https://kekule.games/GL/API/Gamelist/{game_id}/"

        response = requests.request("PUT", url, headers=headers, data=payload)  # Update Kekule Games' system via API
        if response.status_code != 200:
            warnings.warn("Possible failure communicating to Kekule Games API. Please check server log", Warning)


if __name__ == "__main__":
    # Get Kekule Games API credentials from the environment
    API_AUTH = os.environ['API_KEY']
    main()  # run main code
