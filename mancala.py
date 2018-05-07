#!/usr/bin/env python3

import random
import enum
import argparse
import json
from typing import List, Dict, Optional, NewType

#    0   1   2   3   4   5   6
#       13  12  11  10   9   8   7

Pot = NewType('Pot', int)
Pos = NewType('Pos', int)


class Player(enum.Enum):
    ONE = 1
    TWO = 2

    @property
    def other(self) -> "Player":
        """
        >>> Player.ONE.other == Player.TWO
        True
        >>> Player.TWO.other == Player.ONE
        True
        """
        return Player.ONE if self == Player.TWO else Player.TWO


def display_row(ns):
    return " ".join(["%2d" % x for x in ns])


class State:
    def __init__(self, board, runs=100, verbose=False) -> None:
        assert (len(board) % 2) == 0, f"Board length must be even, not {self.END}"
        self.board = board
        self.runs = runs
        self.verbose = verbose

        self.START = Pos(0)
        self.HALF = Pos(len(board) // 2)
        self.END = Pos(len(board))
        self.POTS = [Pot(n) for n in range(1, self.HALF)]
        self.OFFSETS = {
            Player.ONE: self.START,
            Player.TWO: self.HALF,
        }

    def __str__(self) -> str:
        return "%s    \n   %s" % (
            display_row(self.board[self.START:self.HALF]),
            display_row(self.board[self.END:self.HALF-1:-1]),
        )

    def __repr__(self) -> str:
        return "State(%r)" % self.board

    def __eq__(self, b) -> bool:
        """
        >>> State([1, 2, 3, 4]) == State([1, 2, 3, 4])
        True
        >>> State([1, 2, 4, 5]) == State([1, 2, 3, 5])
        False
        """
        return self.board == b.board

    def in_p1_range(self, pos: Pos) -> bool:
        """
        >>> s = State([0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6])
        >>> [s.in_p1_range(Pos(x)) for x in range(len(s.board))]
        [False, True, True, True, True, True, True, False, False, False, False, False, False, False]

        >>> s = State([0, 1, 2, 3, 0, 1, 2, 3])
        >>> [s.in_p1_range(Pos(x)) for x in range(len(s.board))]
        [False, True, True, True, False, False, False, False]
        """
        assert 0 <= pos < self.END
        return pos != self.OFFSETS[Player.ONE] and ((pos // self.HALF) % 2) == 0

    def in_p2_range(self, pos: Pos) -> bool:
        """
        >>> s = State([0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6])
        >>> [s.in_p2_range(Pos(x)) for x in range(len(s.board))]
        [False, False, False, False, False, False, False, False, True, True, True, True, True, True]

        >>> s = State([0, 1, 2, 3, 0, 1, 2, 3])
        >>> [s.in_p2_range(Pos(x)) for x in range(len(s.board))]
        [False, False, False, False, False, True, True, True]
        """
        assert 0 <= pos < self.END
        return pos != self.OFFSETS[Player.TWO] and ((pos // self.HALF) % 2) == 1

    def get_opposite(self, pos: Pos) -> Optional[Pos]:
        """
        Find the opposite pot, excluding bases

        >>> s = State([0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6])
        >>> [s.get_opposite(Pos(x)) for x in range(len(s.board))]
        [None, 13, 12, 11, 10, 9, 8, None, 6, 5, 4, 3, 2, 1]

        >>> s = State([0, 1, 2, 3, 0, 1, 2, 3])
        >>> [s.get_opposite(Pos(x)) for x in range(len(s.board))]
        [None, 7, 6, 5, None, 3, 2, 1]
        """
        assert 0 <= pos < self.END
        if pos in self.OFFSETS.values():
            return None
        return Pos(self.END - pos)

    def move(self, player: Player, src_pos: Pot) -> "State":
        """
        Simple move on our own side, to our own side:

        >>> State([0, 1, 1, 2, 0, 1, 1, 2]).move(Player.ONE, Pot(3))
        State([0, 2, 2, 0, 0, 1, 1, 2])
        >>> State([0, 1, 1, 2, 0, 1, 1, 2]).move(Player.TWO, Pot(3))
        State([0, 1, 1, 2, 0, 2, 2, 0])

        Move wraps from our side to the opponent:

        >>> State([0, 0, 0, 4, 0, 0, 0, 4]).move(Player.ONE, Pot(3))
        State([1, 1, 1, 0, 0, 0, 0, 5])
        >>> State([0, 0, 0, 4, 0, 0, 0, 4]).move(Player.TWO, Pot(3))
        State([0, 0, 0, 5, 1, 1, 1, 0])

        Move wraps round twice, should skip opponent's base:

        >>> State([0, 0, 0, 8, 0, 0, 0, 8]).move(Player.ONE, Pot(3))  # skip p2 base
        State([1, 1, 2, 1, 0, 1, 1, 9])
        >>> State([0, 0, 0, 8, 0, 0, 0, 8]).move(Player.TWO, Pot(3))  # skip p1 base
        State([0, 1, 1, 9, 1, 1, 2, 1])

        Move ends in an empty space, on our own side:
        Should claim the opposing beads

        >>> State([0, 0, 0, 2, 0, 0, 0, 2]).move(Player.ONE, Pot(3))
        State([2, 1, 1, 0, 0, 0, 0, 0])
        >>> State([0, 0, 0, 2, 0, 0, 0, 2]).move(Player.TWO, Pot(3))
        State([0, 0, 0, 0, 2, 1, 1, 0])
        """
        assert src_pos in self.POTS, "Invalid choice of pot"
        new_board = [x for x in self.board]
        pos = self.OFFSETS[player] + src_pos

        # pick up beads from the given spot
        beads = new_board[pos]
        if beads == 0:
            raise Exception("Can't move a spot with 0 beads")
        new_board[pos] = 0

        # drop off beads around the board
        while True:
            pos = (pos - 1) % self.END

            # skip the opponent's base
            if not (
                (player == Player.ONE and pos == self.OFFSETS[Player.TWO]) or
                (player == Player.TWO and pos == self.OFFSETS[Player.ONE])
            ):
                new_board[pos] += 1
                beads -= 1
            if beads == 0:
                break
        final_pos = pos

        # if our final bead is placed in an empty space,
        # then claim any beads opposite
        if final_pos != self.OFFSETS[Player.ONE] and final_pos != self.OFFSETS[Player.TWO]:
            # if our current place has 1 now, then it was empty before
            if new_board[final_pos] == 1:
                if (
                    (player == Player.ONE and self.in_p1_range(final_pos)) or
                    (player == Player.TWO and self.in_p2_range(final_pos))
                ):
                    opposite = self.get_opposite(final_pos)
                    new_board[self.OFFSETS[player]] += new_board[opposite]
                    new_board[opposite] = 0

        # return new state
        return State(new_board, self.runs, self.verbose)

    def possible_moves(self, player: Player) -> List[Pot]:
        """
        List all non-empty pots on our side of the board

        >>> State([0, 3, 3, 3, 3, 3, 3, 0, 3, 3, 3, 3, 3, 3]).possible_moves(Player.ONE)
        [1, 2, 3, 4, 5, 6]
        >>> State([0, 3, 3, 3, 3, 3, 3, 0, 3, 3, 3, 3, 3, 3]).possible_moves(Player.TWO)
        [1, 2, 3, 4, 5, 6]

        >>> State([0, 3, 0, 3, 0, 3, 3, 0, 3, 3, 3, 3, 0, 0]).possible_moves(Player.ONE)
        [1, 3, 5, 6]
        >>> State([0, 3, 0, 3, 0, 3, 3, 0, 3, 3, 3, 3, 0, 0]).possible_moves(Player.TWO)
        [1, 2, 3, 4]
        """
        offset = self.OFFSETS[player]
        return [
            pot
            for pot
            in self.POTS
            if self.board[offset + pot]
        ]

    def p1_wins_by(self) -> int:
        """
        >>> State([1, 1, 1, 0, 0, 0]).p1_wins_by()
        3
        >>> State([0, 0, 0, 1, 1, 1]).p1_wins_by()
        -3
        >>> State([1, 1, 1, 1, 1, 1]).p1_wins_by()
        0
        """
        s1 = sum(self.board[0:self.HALF])
        s2 = sum(self.board[self.HALF:self.END])
        # return (s1>s2)-(s1<s2)
        return s1 - s2

    def tree(self, player: Player) -> int:
        """
        >>> State([1, 1, 0, 0]).tree(Player.ONE)  # p2 no moves, p1 wins immediately
        2
        >>> State([1, 1, 0, 0]).tree(Player.TWO)  # p2 no moves, p1 wins immediately
        2
        >>> State([0, 0, 1, 1]).tree(Player.ONE)  # p1 no moves, p2 wins immediately
        -2
        >>> State([0, 0, 1, 1]).tree(Player.TWO)  # p1 no moves, p2 wins immediately
        -2
        >>> State([1, 0, 1, 0]).tree(Player.ONE)  # p1 no moves, draw
        0
        >>> State([1, 0, 1, 0]).tree(Player.TWO)  # p2 no moves, draw
        0

        >>> State([4, 1, 1, 1]).tree(Player.ONE)  # p1 one move, p1 wins
        3
        >>> State([4, 1, 1, 1]).tree(Player.TWO)  # p2 one move, p1 wins
        3
        >>> State([1, 1, 4, 1]).tree(Player.ONE)  # p1 one move, p2 wins
        -3
        >>> State([1, 1, 4, 1]).tree(Player.TWO)  # p2 one move, p2 wins
        -3
        >>> State([3, 1, 3, 1]).tree(Player.ONE)  # p1 one move, draw
        0
        >>> State([3, 1, 3, 1]).tree(Player.TWO)  # p2 one move, draw
        0

        >> import time
        >> t1 = time.time()
        >> for n in range(0, 10000):
        ..     x = State([0, 3, 3, 3, 3, 3, 3, 0, 3, 3, 3, 3, 3, 3]).tree(Player.ONE)
        >> (time.time() - t1) < 5.0  # check that 10,000 trees takes < 5s
        """
        if not self.possible_moves(player.other):
            return self.p1_wins_by()

        possible_moves = self.possible_moves(player)
        if not possible_moves:
            return self.p1_wins_by()

        n = random.choice(possible_moves)
        s = self.move(player, n)
        return s.tree(player.other)

    def hypothetical_moves(self, player: Player) -> Dict[Pot, int]:
        """
        Return average win margin of each possible move

        >>> State([0, 1, 1, 0, 1, 1]).hypothetical_moves(Player.ONE)  # p1 is guaranteed win by 2 if they choose pot 1
        {1: 2.0, 2: -2.0}
        """
        results = {}
        for n in self.possible_moves(player):
            hypothetical = self.move(player, n)
            results[n] = 0
            for x in range(self.runs):
                results[n] += hypothetical.tree(player.other)

            # results = odds of p1 winning
            if player == Player.TWO:
                results[n] *= -1

        # normalise to average margin of victory for each option
        for n in results:
            results[n] /= self.runs

        return results

    def suggest(self, player: Player) -> Optional[Pot]:
        """
        Given a bunch of moves, select the one that gives the best
        chance of winning

        >>> State([0, 1, 1, 0, 1, 1]).suggest(Player.ONE)  # p1 is guaranteed win if they take pot 1
        1
        """
        results = self.hypothetical_moves(player)
        if self.verbose:
            print(results)
        if not results:
            return None
        best = sorted([(v, k) for k, v in results.items()])[-1][1]
        return best

    @property
    def to_web(self):
        return ','.join([str(x) for x in self.board])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=int, nargs="*", default=[0, 3, 3, 3, 3, 3, 3, 0, 3, 3, 3, 3, 3, 3])
    parser.add_argument("-m", "--move-p1", action="store_true", default=False)
    parser.add_argument("-n", "--move-p2", action="store_true", default=False)
    parser.add_argument("-p", "--human-p1", action="store_true", default=False)
    parser.add_argument("-q", "--human-p2", action="store_true", default=False)
    parser.add_argument("-v", "--verbose", action="store_true", default=False)
    parser.add_argument("-r", "--runs", type=int, default=1000)
    args = parser.parse_args()

    assert 4 <= len(args.board) <= 100
    assert 0 < args.runs <= 1000

    s = State(args.board, args.runs, args.verbose)
    if args.move_p1 or args.move_p2:
        if args.move_p1:
            s = s.move(Player.ONE, s.suggest(Player.ONE))
        else:
            s = s.move(Player.TWO, s.suggest(Player.TWO))
        print(json.dumps(s.board))
        return

    while True:
        print()
        print("*" * 40)
        print(("   " + display_row(range(1, s.HALF)) + "    ").replace(" ", "="))
        print(s)
        if not s.possible_moves(Player.ONE):
            break

        if args.human_p1:
            while True:
                try:
                    n = int(input("p1> "))
                    s = s.move(Player.ONE, Pot(n))
                    break
                except Exception as e:
                    print(e)
        else:
            n = s.suggest(Player.ONE)
            print(f"p1 picks up from pot {n}")
            s = s.move(Player.ONE, n)

        print()
        print("*" * 40)
        print(s)
        print(("   " + display_row(range(s.HALF-1, 0, -1)) + "    ").replace(" ", "="))
        if not s.possible_moves(Player.TWO):
            break

        if args.human_p2:
            while True:
                try:
                    n = int(input("p2> "))
                    s = s.move(Player.TWO, Pot(n))
                    break
                except Exception as e:
                    print(e)
        else:
            n = s.suggest(Player.TWO)
            print(f"p2 picks up from pot {n}")
            s = s.move(Player.TWO, n)

    s1 = sum(s.board[0:s.HALF])
    s2 = sum(s.board[s.HALF:s.END])
    print(f"Score: {s1} : {s2}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass


def main_web(args):
    from aiohttp import web

    template = """
<html>
    <head>
        <style>
            H1, H2 {text-align: center;}
            H1 {font-size: 5vh;}
            H2 {font-size: 3vh;}
            .game TABLE {margin: auto; width: 20vh;}
            .game TD {text-align: center;}
            .game TFOOT TD, .game TBODY TD:nth-child(1) {background-color: #AFA;}
            .game THEAD TD, .game TBODY TD:nth-child(2) {background-color: #FAA;}
            .game BUTTON {border: none; background: #AFA; font-family: sans;}
            .game TBODY TD {width: 50%%;}
            .game TD, .game BUTTON {font-size: 7vh;}

            @media only screen and (min-width: 1024px) {
                .game {float: left; width: 30vw;}
                .rules {float: right; width: 65vw;}
            }
        </style>
    </head>
    <body>%s</body>
</html>
"""

    async def game(request: web.Request):
        raw_state = request.match_info.get(
            'state',
            '0,3,3,3,3,3,3,0,3,3,3,3,3,3'
        )
        state = State([int(x) for x in raw_state.split(',')])
        return web.Response(content_type="text/html", text=template % f"""
        <form action="/move/{raw_state}" method="POST">
            <h1>Mancala</h1>

            <div class="game">
            <table border="1">
                <thead>
                    <tr>
                        <td colspan="2">{state.board[7]}</td>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><button type="submit" name="pot" value="6">{state.board[6]}</button></td>
                        <td>{state.board[8]}</td>
                    </tr>
                    <tr>
                        <td><button type="submit" name="pot" value="5">{state.board[5]}</button></td>
                        <td>{state.board[9]}</td>
                    </tr>
                    <tr>
                        <td><button type="submit" name="pot" value="4">{state.board[4]}</button></td>
                        <td>{state.board[10]}</td>
                    </tr>
                    <tr>
                        <td><button type="submit" name="pot" value="3">{state.board[3]}</button></td>
                        <td>{state.board[11]}</td>
                    </tr>
                    <tr>
                        <td><button type="submit" name="pot" value="2">{state.board[2]}</button></td>
                        <td>{state.board[12]}</td>
                    </tr>
                    <tr>
                        <td><button type="submit" name="pot" value="1">{state.board[1]}</button></td>
                        <td>{state.board[13]}</td>
                    </tr>
                </tbody>
                <tfoot>
                    <tr>
                        <td colspan="2">{state.board[0]}</td>
                    </tr>
                </tfoot>
            </table>
            </div>

            <div class="rules">
            <h2>The Rules</h2>
            <ol>
                <li>In this game, the human is green
                <li>Pick up beads from one of your pots, place one bead in each pot below it (beads move anticlockwise), ending up in your base
                <li>If you still have beads after getting to your base, place one in each of your opponent's pots above it
                <li>If you still have beads after filling all your opponent's pots, skip their base and continue filling your own pots, still anti-clockwise
                <li>When one player has no beads in their pots, whoever has the most beads on their side (pots + base) wins
                <li>If the last bead that you place lands in an empty pot on your side, you can claim all the beads from the adjacent opposing pot into your base
            </ol>
            <br>Note that there are over 9000 variations of the rules, these are the ones that the AI has been taught, which may differ from the ones you use
            </div>
        </form>
        """)

    async def move(request: web.Request):
        raw_state = request.match_info['state']
        post_data = await request.post()
        move1 = Pot(int(post_data['pot']))

        state = State([int(x) for x in raw_state.split(',')])
        if move1 not in state.possible_moves(Player.ONE):
            raise web.HTTPTemporaryRedirect(f"/game/{state.to_web}")

        state = state.move(Player.ONE, move1)
        if not state.possible_moves(Player.ONE) or not state.possible_moves(Player.TWO):
            raise web.HTTPTemporaryRedirect(f"/end/{state.to_web}")

        move2 = state.suggest(Player.TWO)
        state = state.move(Player.TWO, move2)
        if not state.possible_moves(Player.ONE) or not state.possible_moves(Player.TWO):
            raise web.HTTPTemporaryRedirect(f"/end/{state.to_web}")

        raise web.HTTPTemporaryRedirect(f"/game/{state.to_web}")

    async def end(request: web.Request):
        raw_state = request.match_info.get(
            'state',
            '0,3,3,3,3,3,3,0,3,3,3,3,3,3'
        )
        state = State([int(x) for x in raw_state.split(',')])
        p1w = state.p1_wins_by()
        if p1w == 0:
            title = "Draw!"
        elif p1w > 0:
            title = f"Human wins by {p1w}!"
        else:
            title = f"AI wins by {-p1w}!"
        return web.Response(content_type="text/html", text=template % f"""
            <h1>{title}</h1>
            <div class="game">
            <table border="1">
                <thead>
                    <tr>
                        <td colspan="2">{state.board[7]}</td>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>{state.board[6]}</td>
                        <td>{state.board[8]}</td>
                    </tr>
                    <tr>
                        <td>{state.board[5]}</td>
                        <td>{state.board[9]}</td>
                    </tr>
                    <tr>
                        <td>{state.board[4]}</td>
                        <td>{state.board[10]}</td>
                    </tr>
                    <tr>
                        <td>{state.board[3]}</td>
                        <td>{state.board[11]}</td>
                    </tr>
                    <tr>
                        <td>{state.board[2]}</td>
                        <td>{state.board[12]}</td>
                    </tr>
                    <tr>
                        <td>{state.board[1]}</td>
                        <td>{state.board[13]}</td>
                    </tr>
                </tbody>
                <tfoot>
                    <tr>
                        <td colspan="2">{state.board[0]}</td>
                    </tr>
                </tfoot>
            </table>
            </div>
            <h2><a href="/">Play Again</a></h2>
        """)

    app = web.Application()
    app.router.add_get('/', game)
    app.router.add_get('/game/{state}', game)
    app.router.add_post('/game/{state}', game)
    app.router.add_post('/move/{state}', move)
    app.router.add_get('/end/{state}', end)
    app.router.add_post('/end/{state}', end)
    # web.run_app(app)
    return app
