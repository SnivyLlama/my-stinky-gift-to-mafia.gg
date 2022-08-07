import mafapi, asyncio, random, time
from json import load

with open('data.json') as f:
    data: dict[str] = load(f)

def trusted(user: mafapi.User) -> bool:
    return user is None or user.username in data['trusted']

def size(setup: dict[int, int]):
    total = 0
    for i, j in setup.items():
        total += j
    return total

def full(players: dict[int, bool], setup: dict[int, int]):
    playing = 0
    for i, j in players.items():
        if j:
            playing += 1
    if playing >= size(setup):
        return True
    else:
        return False

class Vote:
    def __init__(self) -> None:
        self.realvote: bool = None
        self.deckvote: int = None
        self.rvlt = 0
        self.dvlt = 0
        self.tir = 0
    
    def yes(self):
        return self.tir == 0 or self.tir + 3600 > time.time()

class SnivyBot(mafapi.BotBase):
    GIST_TOKEN = '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'
    GIST_ID = '58b03edd1f7dc52603a9e4cbab20ac47'

    async def _extended_init__(self):
        self.afkcheck = False
        self.afkwaiting = False
        self.players: dict[int, bool] = {}
        self.votes: dict[int, Vote] = {}
        self.abusers: set[int] = set()
        self.specswantin: set[int] = set()
        self.nospecswant: set[int] = set()
        self.ingameplayers: dict[str, str] = {}
        self.afkids: set[str] = set()
        self.kicknextgame: set[int] = set()
        self.lastpreset = 'randumbs'
        self.preset = 'randumbs'
        self.lastdeck = -1
        self.wanters: list[int] = []
        self.lastjoin = time.time()
        self.minimum = 3
        self.host = True
        for i in self.ws.info['users']:
            self.players[i['userId']] = i['isPlayer']
            self.votes[i['userId']] = Vote()
            if i['userId'] == 371804:
                self.host = i['isHost']
        await self.session.session.patch(f'https://api.github.com/gists/{self.GIST_ID}', headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'token {self.GIST_TOKEN}'
        }, data=f'{{"description":"This file contains the link to my bot room on mafia.gg","files":{{"mafia.txt":{{"content":"BOT ROOM AT: https://mafia.gg/game/{self.ws.roomid}"}}}}}}')
        self.newgame = 0
        await self._on_fit(None, [])
        self.newgame = time.time()
        asyncio.create_task(self._keep_alive_loop())

    async def _keep_alive_loop(self):
        while True:
            await asyncio.sleep(250)
            if any([True for i in self.ws.events if i['type'] == 'startGame']):
                await self.send('.')
            else:
                await self.ws.send(self.ws.options)

    async def _greet(self, packet):
        if packet['userId'] in self.kicknextgame:
            await self.ws.kick(packet['userId'])
            return
        if packet['userId'] not in self.nospecswant:
            self.specswantin.add(packet['userId'])
        self.players = {**self.players, packet['userId']: False}
        self.votes = {packet['userId']: Vote(), **self.votes}
        self.votes[packet['userId']].tir = 0
        us = (await self.session.getUser(packet['userId']))[0].username
        if us not in data['trusted'] and time.time() > self.lastjoin + 300:
            await self.send(f'We haven\'t gotten a player recently! Welcome {us}!')
        if us not in data['trusted']:
            self.lastjoin = time.time()
        if packet['userId'] not in self.nospecswant:
            await self._on_fit(None, [])
            await asyncio.sleep(20)
            try:
                if packet['userId'] in self.specswantin:
                    self.specswantin.remove(packet['userId'])
                    self.nospecswant.add(packet['userId'])
                    await self._on_fit(None, [])
            except KeyError:
                pass

    async def _goodbye(self, packet):
        if self.afkwaiting and self.players[packet['userId']]:
            self.abusers.add(packet['userId'])
            person = (await self.session.getUser(packet['userId']))[0]
            print(f'User {person.username} with id {person.id} left during the first part of the afk check!')
        if packet['userId'] in self.specswantin:
            self.specswantin.remove(packet['userId'])
            self.nospecswant.add(packet['userId'])
        try:
            del self.players[packet['userId']]
        except:
            pass
        self.votes[packet['userId']].tir = time.time()
        await self._on_fit(None, [])

    async def _user_update(self, packet):
        if packet['userId'] == 371804:
            self.host = packet['isHost']
        if not packet['isPlayer'] and self.players[packet['userId']] and self.afkwaiting:
            self.abusers.add(packet['userId'])
            person = (await self.session.getUser(packet['userId']))[0]
            print(f'User {person.username} with id {person.id} left during the first part of the afk check!')
        if packet['isPlayer'] and packet['userId'] in self.specswantin:
            self.specswantin.remove(packet['userId'])
        self.players[packet['userId']] = packet['isPlayer']
        if not any([True for i in self.ws.events if i['type'] == 'startGame']):
            await self._on_fit(None, [])
    
    async def _start_game(self, packet):
        for i in packet['players']:
            self.ingameplayers[i['playerId']] = i['name']

    async def _game_end_packet(self, packet):
        for i, j in packet['users'].items():
            if j in self.afkids:
                self.kicknextgame.add(int(i))
                print(f'User with id {i} afked out!')
        self.afkids.clear()
        await self.send('Starting a new room in 4 seconds!')
        await asyncio.sleep(4)
        options = self.ws.options
        self.players = {371804: False}
        for i, j in self.votes.items():
            if i != 371804:
                j.tir = time.time()
        self.abusers.clear()
        self.nospecswant.clear()
        self.ingameplayers.clear()
        roomid = await self.session.createRoom(self.ws.options['roomName'], self.ws.options['unlisted'])
        await self.ws.send({'type': 'newGame', 'roomId': roomid})
        self.ws = await self.session.joinRoomById(roomid)
        self.ws.options = options
        await self.ws.send(self.ws.options)
        await self._on_help(None, [])
        self.newgame = time.time()
        await self.session.session.patch(f'https://api.github.com/gists/{self.GIST_ID}', headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'token {self.GIST_TOKEN}'
        }, data=f'{{"description":"Mafia.gg bot room url holder","files":{{"mafia.txt":{{"content":"BOT ROOM AT: https://mafia.gg/game/{self.ws.roomid}"}}}}}}')
        await asyncio.sleep(10)
        await self._on_fit(None, [])

    async def _extra_side_effects(self, packet):
        print('IN: ' + str(packet))
        if packet['type'] == 'system':
            if packet['message'] == 'This room will be automatically closed in 2 minutes if the game does not begin':
                raise KeyboardInterrupt()
            for i, j in self.ingameplayers.items():
                if packet['message'] == f'Due to inactivity, {j} has been expelled from the game.':
                    self.afkids.add(i)
    
    async def _on_check(self, user, args):
        if not trusted(user):
            return
        if full(self.players, self.ws.options['roles']) and not self.afkcheck:
            self.afkcheck = True
            self.afkwaiting = True
            await self.send('Setup votes do not count beyond this point. Say /wantin within 15 seconds to expand!')
            await asyncio.sleep(15)
            while self.wanters:
                await asyncio.sleep(0.5)
            self.afkwaiting = False
            if not full(self.players, self.ws.options['roles']):
                await self.send('Someone left during the process. Setup votes will now be counted again.')
                self.afkcheck = False
                await self._on_fit(None, [])
                return
            pcbt = self.players.copy()
            await self.force_spec()
            await self.send('AFK CHECK! Join in 20 seconds to start the game!')
            for i in range(40):
                await asyncio.sleep(0.5)
                if full(self.players, self.ws.options['roles']):
                    self.afkcheck = False
                    self.wanters.clear()
                    self.kicknextgame.clear()
                    await self.ws.send({'type': 'startGame'})
                    return
            for i, j in pcbt.items():
                try:
                    if self.players[i] and not j:
                        self.abusers.add(i)
                        print(f'User with id {i} left during the second part of the afk check!')
                except KeyError:
                    print(f'User with id {i} left during the second part of the afk check!')
                    self.abusers.add(i)
            await self.send('SMH you guys are slow! Setup votes will now be counted again.')
            self.afkcheck = False
            await self._on_fit(None, [])

    async def _on_fit(self, user, args):
        if not trusted(user):
            return
        usual = self.preset == self.lastpreset
        if self.afkcheck or (self.newgame + 10 > time.time() and usual) or not self.host:
            return
        if not any([True for i in self.ws.events if i['type'] == 'startGame']):
            await self._on_index(None, [sum([1 for i, j in self.players.items() if j]) + len(self.specswantin) - 3])
            await self._on_uv(None, [])
            if usual:
                await self._on_check(None, [])
    
    async def _on_say(self, user, args):
        if not trusted(user):
            return
        await self.send(' '.join(args))

    async def _on_help(self, user, args):
        if not trusted(user):
            return
        rsvc = sum([1 for i, j in self.votes.items() if j.realvote and j.yes()])
        rdvc = sum([1 for i, j in self.votes.items() if j.realvote == False and j.yes()])
        ndvc = sum([1 for i, j in self.votes.items() if j.deckvote == -1 and j.yes()])
        navc = sum([1 for i, j in self.votes.items() if j.deckvote == 1590964743164 and j.yes()])
        btvc = sum([1 for i, j in self.votes.items() if j.deckvote == 1623983343445 and j.yes()])
        ddvc = sum([1 for i, j in self.votes.items() if j.deckvote == 1611719231322 and j.yes()])
        await self.update_presence(False)
        await self.send(f'Use /report to report anything to me! /vote RD for randumbs, /vote RS for real setups, /vote US to unvote your SETUP vote. ({rdvc}v{rsvc}) (5s cooldown + ONLY ONE VOTE EACH + votes vanish after 1 hour of gone)')
        await self.send(f'Use /vote ND for no deck, /vote NA for neko atsume, /vote BT for BTD6, /vote DD for deck deck, /vote UD to unvote your DECK vote. ({ndvc}v[{navc}v{btvc}v{ddvc}]) (5s cooldown + ONLY ONE VOTE EACH + votes vanish after 1 hour of gone)')

    async def _on_trust(self, user, args):
        if not trusted(user):
            return
        data['trusted'].append(args[0])

    async def _on_vote(self, user, args):
        farg = args[0].upper()
        if self.votes[user.id].rvlt + 5 < time.time():
            self.votes[user.id].rvlt = time.time()
            if farg == 'RD':
                self.votes[user.id].realvote = False
            elif farg == 'RS':
                self.votes[user.id].realvote = True
            elif farg == 'US':
                self.votes[user.id].realvote = None
            else:
                self.votes[user.id].rvlt = 0
            if sum([1 for i, j in self.votes.items() if j.realvote and j.yes()]) > sum([1 for i, j in self.votes.items() if j.realvote == False and j.yes()]):
                self.preset = 'real'
            else:
                self.preset = 'randumbs'
            if self.preset != self.lastpreset:
                await self._on_fit(None, [])
        if self.votes[user.id].dvlt + 5 < time.time():
            self.votes[user.id].dvlt = time.time()
            if farg == 'ND':
                self.votes[user.id].deckvote = -1
            elif farg == 'NA':
                self.votes[user.id].deckvote = 1590964743164
            elif farg == 'BT':
                self.votes[user.id].deckvote = 1623983343445
            elif farg == 'DD':
                self.votes[user.id].deckvote = 1611719231322
            elif farg == 'UD':
                self.votes[user.id].deckvote = None
            else:
                self.votes[user.id].dvlt = 0
            ndv = sum([1 for i, j in self.votes.items() if j.deckvote == -1 and j.yes()])
            nav = sum([1 for i, j in self.votes.items() if j.deckvote == 1590964743164 and j.yes()])
            btv = sum([1 for i, j in self.votes.items() if j.deckvote == 1623983343445 and j.yes()])
            ddv = sum([1 for i, j in self.votes.items() if j.deckvote == 1611719231322 and j.yes()])
            result = max(nav, btv, ddv)
            deck = 1611719231322
            if ndv >= nav + btv + ddv:
                deck = -1
            elif result == nav:
                deck = 1590964743164
            elif result == btv:
                deck = 1623983343445
            if deck != self.lastdeck:
                self.ws.options['deck'] = deck
                self.lastdeck = deck
                await self.ws.send(self.ws.options)
    
    async def _on_uv(self, user, args):
        if not trusted(user):
            return
        if sum([1 for i, j in self.votes.items() if j.realvote and j.yes()]) > sum([1 for i, j in self.votes.items() if j.realvote == False and j.yes()]):
            self.preset = 'real'
        else:
            self.preset = 'randumbs'
        ndv = sum([1 for i, j in self.votes.items() if j.deckvote == -1 and j.yes()])
        nav = sum([1 for i, j in self.votes.items() if j.deckvote == 1590964743164 and j.yes()])
        btv = sum([1 for i, j in self.votes.items() if j.deckvote == 1623983343445 and j.yes()])
        ddv = sum([1 for i, j in self.votes.items() if j.deckvote == 1611719231322 and j.yes()])
        result = max(nav, btv, ddv)
        deck = 1611719231322
        if ndv >= nav + btv + ddv:
            deck = -1
        elif result == nav:
            deck = 1590964743164
        elif result == btv:
            deck = 1623983343445
        if self.preset != self.lastpreset:
            await self._on_fit(None, [])
        if deck != self.lastdeck:
            self.ws.options['deck'] = deck
            self.lastdeck = deck
            await self.ws.send(self.ws.options)

    async def _on_minimum(self, user, args):
        if not trusted(user):
            return
        self.minimum = int(args[0])

    async def _on_wantin(self, user, args):
        if user.id in self.abusers or self.players[user.id] or sum([1 for i, j in self.players.items() if j]) + len(self.wanters) < size(self.ws.options['roles']) or self.newgame + 10 > time.time() or user.id in self.wanters or any([True for i in self.ws.events if i['type'] == 'startGame']):
            return
        if not await self._on_expand(None, []):
            await self.send('Sorry, something went wrong.')
            return
        else:
            await self.send('Get in! Votes were tallied in this moment.')
        self.wanters.append(user.id)
        for i in range(40):
            await asyncio.sleep(0.5)
            try:
                if self.players[user.id] or full(self.players, self.ws.options['roles']):
                    self.wanters.remove(user.id)
                    return
            except:
                print(f'User {user.username} with id {user.id} abused the wantin feature!')
                self.abusers.add(user.id)
                self.wanters.remove(user.id)
                await self._on_reduce(None, [])
                return
        if not full(self.players, self.ws.options['roles']):
            print(f'User {user.username} with id {user.id} abused the wantin feature!')
            self.abusers.add(user.id)
            await self._on_reduce(None, [])
        self.wanters.remove(user.id)
    
    async def _on_preset(self, user, args):
        if not trusted(user):
            return
        self.preset = args[0]
        await self._on_fit(None, [])

    async def _on_report(self, user, args):
        message = ' '.join(args)
        print(f'Report from user {user.username}: {message}')

    async def _on_expand(self, user, args):
        if not trusted(user):
            return
        lastsize = size(self.ws.options['roles'])
        await self._on_index(None, [size(self.ws.options['roles']) - 2])
        newsize = size(self.ws.options['roles'])
        return lastsize + 1 == newsize
    
    async def _on_index(self, user, args):
        if not trusted(user):
            return
        farg = min(max(int(args[0]), self.minimum - 3), len(data['presets'][self.preset]) - 1)
        if farg + 3 == size(self.ws.options['roles']) and self.preset == self.lastpreset:
            return True
        self.lastpreset = self.preset[:]
        query = data['presets'][self.preset][farg]
        if isinstance(query, str):
            await self._on_setup(None, [query])
        else:
            await self._on_setup(None, [random.choice(query)])

    async def _on_reduce(self, user, args):
        if not trusted(user):
            return
        if size(self.ws.options['roles']) == self.minimum:
            return False
        await self._on_index(None, [size(self.ws.options['roles']) - 4])

    async def _on_kick(self, user, args):
        if not trusted(user):
            return
        await self.ws.kick([(await self.session.getUser(i))[0] for i in self.ws.users if (await self.session.getUser(i))[0].username == args[0]][0])

    async def _on_blacklist(self, user, args):
        if not trusted(user):
            return
        await self.session.blacklist(args[0])
    
    async def _on_whitelist(self, user, args):
        if not trusted(user):
            return
        # WIP LOL

    async def _on_setting(self, user, args):
        if not trusted(user):
            return
        name = ' '.join(args)
        if name == 'Informed Day Start' or name == 'Informed Daystart' or name == 'Day Start' or name == 'Daystart':
            option = 'dayStart'
            value = 'dawnStart'
        elif name == 'Uninformed Day Start' or name == 'Uninformed Daystart':
            option = 'dayStart'
            value = 'dayStart'
        elif name == 'Night Start' or name == 'Nightstart':
            option = 'dayStart'
            value = 'off'
        elif name == 'Head Start' or name == 'Headstart' or name == 'No Kill Night Start' or name == 'No Kill Nightstart':
            option = 'dayStart'
            value = 'mafiaNKn1'
        elif name == '3/4 Majority' or name == 'Three-quarters Majority':
            option = 'majorityRule'
            value = '75'
        elif name == '2/3 Majority' or name == 'Two-thirds Majority':
            option = 'majorityRule'
            value = '66'
        elif name == 'Simple Majority' or name == '1/2 Majority':
            option = 'majorityRule'
            value = '51'
        elif name == 'No Majority':
            option = 'majorityRule'
            value = '-1'
        elif name == 'Force Vote' or name == 'Must Vote':
            option = 'mustVote'
            value = True
        elif name == 'No Force Vote' or name == 'Force Vote Off' or name == 'No Must Vote' or name == 'Must Vote Off':
            option = 'mustVote'
            value = False
        elif name == 'Night Talk' or name == 'Meeting Talk':
            option = 'noNightTalk'
            value = False
        elif name == 'No Night Talk' or name == 'Night Talk Off' or name == 'No Meeting Talk' or name == 'Meeting Talk Off':
            option = 'noNightTalk'
            value = True
        elif name == 'Role Reveal On Death' or name == 'Role Reveal':
            option = 'revealSetting'
            value = 'allReveal'
        elif name == 'Alignment Reveal On Death' or name == 'Alignement Reveal':
            option = 'revealSetting'
            value = 'alignmentReveal'
        elif name == 'No Reveal On Death' or name == 'No Reveal' or name == 'RR Off':
            option = 'revealSetting'
            value = 'noReveal'
        elif name == 'Hide Setup':
            option = 'hideSetup'
            value = True
        elif name == 'Show Setup':
            option = 'hideSetup'
            value = False
        elif name == 'Disable Vote Lock' or name == 'Disable Vote Lock Peroid' or name == 'Disable Votelock':
            option = 'disableVoteLock'
            value = True
        elif name == 'Enable Vote Lock' or name == 'Enable Vote Lock Peroid' or name == 'Enable Votelock' or name == 'Vote Lock Period':
            option = 'disableVoteLock'
            value = False
        elif name == 'Scale Timer' or name == 'Enable Scale Timer':
            option = 'scaleTimer'
            value = True
        elif name == 'Disable Scale Timer':
            option = 'scaleTimer'
            value = False
        elif name == 'Mafia 1KP' or name == '1KP':
            option = 'twoKp'
            value = '0'
        elif name == 'Mafia 2KP' or name == '2KP':
            option = 'twoKp'
            value = '1'
        elif name.startswith('Mafia 2KP until '):
            option = 'twoKp'
            value = name[16:]
        elif name.startswith('Day Length '):
            option = 'dayLength'
            value = name[11:]
        elif name.startswith('Night Length '):
            option = 'nightLength'
            value = name[13:]
        elif name.startswith('Room Name '):
            option = 'roomName'
            value = name[10:]
        elif name.startswith('Deck '):
            option = 'deck'
            value = (await self.session.getDeckSamples(name[5:]))[0].id
        elif name == 'No Deck':
            option = 'deck'
            value = -1
        elif name == 'Public':
            option = 'unlisted'
            value = False
        elif name == 'Private' or name == 'Unlisted':
            option = 'unlisted'
            value = True
        self.ws.options[option] = value
        await self.ws.send(self.ws.options)

    async def _on_start(self, user, args):
        if not trusted(user):
            return
        await self.ws.send({'type': 'startGame'})

    async def _on_transfer(self, user, args):
        if not trusted(user):
            return
        await self.sendPacket({'type': 'transferHost', 'userId': user.id})

    async def _on_setup(self, user, args):
        if not trusted(user):
            return
        name = ' '.join(args)
        try:
            if data['setups'][name]:
                self.ws.options = {**self.ws.options, 'roles': dict(map(lambda x:[int(i) for i in str.split(x, 'a')], str.split(data['setups'][name]['code'], 'b'))), 'roomName': Config.ROOMNAME + ' | ' + name, 'revealSetting': 'allReveal'}
                await self._on_setting(None, [data['setups'][name]['start']])
                return
        except KeyError:
            try:
                self.ws.options = {**self.ws.options, 'roles': dict(map(lambda x:[int(i) for i in str.split(x, 'a')], str.split(args[0], 'b'))), 'roomName': Config.ROOMNAME + ' | ' + self.preset.capitalize()}
                await self._on_setting(None, ['Nightstart'])
                return
            except:
                await self.send('That\'s not a valid setup!')

    async def _on_afk(self, user, args):
        if not trusted(user):
            return
        await self.force_spec()

    async def _on_disconnect(self, user, args):
        if not trusted(user):
            return
        if len(args) == 1:
            await asyncio.sleep(int(args[0]))
        await self.send('Goodbye!')
        raise KeyboardInterrupt()

class Config:
    USERNAME = 'USERNAME HERE'
    PASSWORD = 'PASSWORD HERE'
    ROOMNAME = 'goodbye'

    def __init__(self, unl: bool = None, id: str = None):
        self.ROOMID = id
        self.UNLISTED = unl

async def main():
    if input('Room ID? [y/n] ') == 'y':
        bot = await SnivyBot(Config(id=input('Room ID: ')))
        await bot.run()
    else:
        bot = await SnivyBot(Config(unl=True if input('Unlisted? [y/n] ') == 'y' else False))
        await bot.run()

if __name__ == '__main__':
    asyncio.run(main())
