from random import shuffle
from copy import deepcopy

class Game(object):
    def __init__(self, cid, initiator):
        self.playerlist = {}
        self.player_sequence = []
        self.cid = cid
        self.board = None
        self.initiator = initiator
        self.dateinitvote = None
        self.last_action = {'id': 0, 'depth': 0}
        self.secret_actions = []
        self.spectators = []

    def add_player(self, uid, player):
        self.playerlist[uid] = player

    def get_hitler(self):
        for uid in self.playerlist:
            if self.playerlist[uid].role == "Hitler":
                return self.playerlist[uid]

    def get_fascists(self):
        fascists = []
        for uid in self.playerlist:
            if self.playerlist[uid].role == "Fascist":
                fascists.append(self.playerlist[uid])
        return fascists

    def get_liberals(self):
        liberals = []
        for uid in self.playerlist:
            if (self.playerlist[uid].role != "Fascist" and self.playerlist[uid].role != "Hitler"):
                liberals.append(self.playerlist[uid])
        return liberals

    def shuffle_player_sequence(self):
        for uid in self.playerlist:
            self.player_sequence.append(self.playerlist[uid])
        shuffle(self.player_sequence)

    def remove_from_player_sequence(self, Player):
        for p in self.player_sequence:
            if p.uid == Player.uid:
                p.remove(Player)

    def print_roles(self):
        rtext = ""
        if self.board is None:
            #game was not started yet
            return rtext
        else:
            for p in self.playerlist:
                rtext += self.playerlist[p].name + "'s "
                if self.playerlist[p].is_dead:
                    rtext += "(dead) "
                rtext += "secret role was " + self.playerlist[p].role + "\n"
            return rtext

    def store_last_action(self, action):
        if self.last_action['depth'] > 2:
            self.last_action['state'].last_action['state'].last_action = {'depth': 0}
            self.last_action['state'].last_action['depth'] -= 1
            self.last_action['depth'] -= 1
        self.last_action = {'id': self.last_action['id'] + 1, 'function': action, 'state': deepcopy(self), 'depth': self.last_action['depth'] + 1}

    def get_last_action(self, id):
        if self.last_action['depth'] == 0:
            return None
        elif self.last_action['id'] == id:
            return self.last_action
        else:
            return self.last_action['state'].get_last_action(id)
