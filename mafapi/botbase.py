import asyncio
import logging
from asyncinit import asyncinit
from mafapi.session import Session
from mafapi.connection import Connection

def traceback(e):
    print('Custom traceback:')
    print('File "{}", line {}, in {}'.format(e.__traceback__.tb_frame.f_code.co_filename,
                                             e.__traceback__.tb_frame.f_code.co_firstlineno,
                                             e.__traceback__.tb_frame.f_code.co_name))
    with open(e.__traceback__.tb_frame.f_code.co_filename) as f:
        lines = f.readlines()
        line = e.__traceback__.tb_lineno-1
        funcline = e.__traceback__.tb_frame.f_code.co_firstlineno-1
        print('    {}\t{}'.format(funcline, lines[funcline][:-1]))
        print('    {}\t{}'.format(line-1, lines[line-1][:-1]))
        print('>>> {}\t{}'.format(line,   lines[line][:-1]))
        print('    {}\t{}'.format(line+1, lines[line+1][:-1]))
        print('{}: {}'.format(str(type(e))[8:-2], str(e)))
        f.close()

@asyncinit
class BotBase:
    async def __init__(self, config):
        self.session = await Session()
        await self.session.login(config.USERNAME, config.PASSWORD)
        self.ws = None
        if config.ROOMID:
            self.ws = await self.session.joinRoomById(config.ROOMID)
            print(f'Joined https://mafia.gg/game/{config.ROOMID}')
        else:
            roomid = await self.session.createRoom(config.ROOMNAME, config.UNLISTED)
            print(f'Joined https://mafia.gg/game/{roomid}')
            self.ws = await self.session.joinRoomById(roomid)
        await self._extended_init__()
    async def _extended_init__(self):
        pass
    async def send(self, string):
        return await self.ws.sendchat(string)
    async def sendPacket(self, packet):
        if packet['type']=='newGame':
            logging.info('Joined https://mafia.gg/game/%s', packet['roomId'])
        return await self.ws.send(packet)
    async def updateOpts(self):
        return await self.ws.send(self.ws.options)
    async def run(self):
        await self._on_help(None, [])
        while True:
            data = await self.ws.get()
            asyncio.create_task(self.parse_packet(data))
    async def parse_packet(self, packet):
        await self.side_effects(packet)
        filtered = await self.filter_packet(packet)
        if filtered:
            #userobj = filtered[0]
            #command = filtered[1]
            #args = filtered[:2]
            userobj, command, *args = filtered
            return await self.exec_command(userobj, command, args)
        return
    async def update_presence(self, isPlayer):
        return await self.sendPacket({'type': 'presence', 'isPlayer': isPlayer})
    async def force_spec(self):
        return await self.sendPacket({'type': 'forceSpectate'})
    async def side_effects(self, packet):
        await self._extra_side_effects(packet)
        if packet['type']=='userJoin':
            await self._greet(packet)
        if packet['type']=='userQuit':
            await self._goodbye(packet)
        if packet['type'] == 'userUpdate':
            await self._user_update(packet)
        if packet['type']=='startGame':
            await self._start_game(packet)
        if packet['type']=='endGame': # insert avengers end game referece here
            await self._game_end_packet(packet)
        if packet['type']=='system' and packet['message'].startswith('Winning teams:'):
            await self._game_finish(packet['message'])
    async def filter_packet(self, packet):
        if packet['type']!='chat': return []
        if packet['from']['userId'] == self.session.user.id: return []
        msg = packet['message'].strip()
        if not msg.startswith('/'): return []
        command, *args = msg.split(' ')
        command = command.lower()
        return [(await self.session.getUser(packet['from']['userId']))[0], command[1:], *args]
    async def exec_command(self, userobj, command, args):
        func = None
        try:
            func = getattr(self, '_on_{}'.format(command))
        except AttributeError as e:
            return await self._invalid(userobj, command, args)
        finally:
            if func:
                return await func(userobj, args)
            #func = eval('self.___{}'.format(command))
            #logging.debug('%r: %r', type(e), e.args[0])
    async def _extra_side_effects(self, packet):
        pass
    async def _game_finish(self, winningteams):
        pass
    async def _start_game(self, packet):
        pass
    async def _game_end_packet(self, packet):
        pass
    async def _user_update(self, packet):
        pass
    async def _greet(self, generatedname):
        pass
    async def _goodbye(self, generatedname):
        pass
    async def _invalid(self, userobj, command, args):
        pass
