import sqlite3
from Constants.Config import RANKING_DB

class Ranking(object):
    def __init__(self):
        self.conn = sqlite3.connect(RANKING_DB)
        self.conn.row_factory = sqlite3.Row

    def increment_game(self, group_id, player):
        self.add_player(group_id, player)
        stmt = self.conn.cursor()
        params = (player.uid, group_id);
        stmt.execute('UPDATE ranking SET quantity = quantity + 1 WHERE player_id = ? AND group_id = ?', params)
        self.conn.commit()

    def add_player(self, group_id, player):
        c = self.conn.cursor()
        params = (player.uid, group_id)
        c.execute('SELECT * FROM `ranking` WHERE `player_id` = ? AND `group_id` = ?', params)
        if c.fetchone() == None:
            c.execute('INSERT INTO `ranking` (`player_id`, `group_id`, `player_name`) VALUES (?, ?, ?)', (player.uid, group_id, player.name))
        self.conn.commit()

    def decay_non_active(self, group_id):
        if group_id:
            c = self.conn.cursor()
            updateSql = 'UPDATE `ranking` SET total = total - 0.3 WHERE `group_id` = ?'
            c.execute(updateSql, (group_id))
            self.conn.commit()

    def update_ranking(self, group_id, players, is_liberal):
        c = self.conn.cursor()
        group = 'fascist = fascist + 1.3'
        if is_liberal:
            group = 'liberal = liberal + 1.3'

        for player in players:
            self.add_player(group_id, player)
            updateSql = 'UPDATE `ranking` SET total = total + 1, %s WHERE `group_id` = ? AND `player_id` = ?' % (group)
            c.execute(updateSql, (group_id, player.uid))
            self.conn.commit()

    def print_ranking(self, group_id):
        c = self.conn.cursor()
        c.execute('SELECT * FROM `ranking` WHERE `group_id` = ? ORDER BY CAST(`total` AS FLOAT) / quantity DESC LIMIT 10', (group_id,))
        index = 1
        output = ''
        ranking_format = '%d | %.1f%s | %s | %d \n'
        for row in c:
            perc = 0
            if row['quantity'] > 0:
                perc = (row['total']/row['quantity']) * 100
            name = row['player_name'][:7].ljust(7)
            if index == 1:
                name = '[%s](tg://user?id=%d)' % (row['player_name'], row['player_id'])
            params = (index, perc, '%', name, row['quantity'])
            output += ranking_format % params
            index += 1
        return output
