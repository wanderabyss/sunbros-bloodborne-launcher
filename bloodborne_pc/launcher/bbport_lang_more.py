# SPDX-License-Identifier: GPL-2.0-or-later
"""Launcher texts added with online co-op and Add to Steam (see bbport_lang.py). Russian is
listed here too, since these texts have no Russian next to them in the launcher. Each language
maps every English text in MORE_KEYS to its translation."""

MORE_KEYS = [
    'Online co-op',
    "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.",
    'Play online',
    'Off: the game stays offline, as before.',
    'Game server (messages, bloodstains, ghosts)',
    'Game server',
    "The Hunter's Dream by default. Only the name is needed; the game picks the ports.",
    'Co-op server (bells and summons)',
    'Server address',
    'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.',
    'WebAPI address',
    'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.',
    'Account',
    'Online ID (NPID)',
    'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.',
    'Password',
    'Saved on this PC with the other launcher settings.',
    'Connection',
    'UPnP (open a port on the router automatically)',
    'Turn it off on Tailscale or another VPN.',
    'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.',
    'Online',
    'Offline',
    'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.',
    'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.',
    'The Online ID is the account name (NPID) you registered on the server, not your email address.',
    'Steam was not found on this PC (or nobody has signed in to it yet).',
    'Game server {0}: reachable',
    'Server {0}: reachable',
    'Checking…',
    'Test connection',
    'Steam has to close while the game is added; it starts again afterwards. Close Steam now?',
    'Steam did not close. Close it yourself and try again.',
    'Game server {0}: not reachable ({1})',
    'Server {0}: not reachable ({1})',
    'WebAPI {0}: reachable',
    'WebAPI {0}: answered, but it is not a shadNet server',
    'WebAPI {0}: not reachable ({1})',
    'by Super Medo',
    'Add to Steam',
    'The WebAPI box holds the game server address; it is ignored.',
    '"Play online" is off: the game starts offline.',
    'Could not add the game to Steam: {}',
    'DLC folder',
    'Choose the DLC folder',
    'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.',
    'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges',
]

MORE = {
    'ru': {
        'Online co-op': 'Онлайн-кооператив',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "Сообщения, пятна крови и призраки приходят с сервера The Hunter's Dream; колокола и призывы идут через сервер shadNet.",
        'Play online': 'Играть онлайн',
        'Off: the game stays offline, as before.': 'Выключено: игра остаётся офлайн, как раньше.',
        'Game server (messages, bloodstains, ghosts)': 'Игровой сервер (сообщения, пятна крови, призраки)',
        'Game server': 'Игровой сервер',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "По умолчанию The Hunter's Dream. Нужно только имя, порты игра выберет сама.",
        'Co-op server (bells and summons)': 'Сервер кооператива (колокола и призывы)',
        'Server address': 'Адрес сервера',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 — публичный сервер shadPS4. Для частного сервера введите host:port от его владельца.',
        'WebAPI address': 'Адрес WebAPI',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            'Сервера shadNet, а не игрового сервера. Оставьте пустым: будет использован адрес сервера с портом 31315.',
        'Account': 'Учётная запись',
        'Online ID (NPID)': 'Онлайн-ID (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'Имя вашей учётной записи shadNet, а не почта. Зарегистрируйтесь на shadnet.shadps4.net или спросите владельца частного сервера.',
        'Password': 'Пароль',
        'Saved on this PC with the other launcher settings.':
            'Хранится на этом ПК вместе с остальными настройками лаунчера.',
        'Connection': 'Подключение',
        'UPnP (open a port on the router automatically)': 'UPnP (автоматически открыть порт на роутере)',
        'Turn it off on Tailscale or another VPN.': 'Выключите при Tailscale или другом VPN.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'У всех в сессии должна быть одна версия игры (1.09) и один сервер. Читы меняют игру и для других игроков: выключайте их, когда играете вместе.',
        'Online': 'Онлайн',
        'Offline': 'Офлайн',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne добавлен в библиотеку Steam. Игра запускается с настройками, сохранёнными в этом лаунчере.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'Учётная запись указана, но «Играть онлайн» выключено.\n\nДа: играть онлайн.   Нет: играть офлайн.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            'Онлайн-ID — это имя учётной записи (NPID), зарегистрированной на сервере, а не адрес почты.',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            'Steam не найден на этом ПК (или в него ещё никто не входил).',
        'Game server {0}: reachable': 'Игровой сервер {0}: доступен',
        'Server {0}: reachable': 'Сервер {0}: доступен',
        'Checking…': 'Проверка…',
        'Test connection': 'Проверить подключение',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            'Пока игра добавляется, Steam нужно закрыть; потом он запустится снова. Закрыть Steam сейчас?',
        'Steam did not close. Close it yourself and try again.':
            'Steam не закрылся. Закройте его сами и попробуйте ещё раз.',
        'Game server {0}: not reachable ({1})': 'Игровой сервер {0}: недоступен ({1})',
        'Server {0}: not reachable ({1})': 'Сервер {0}: недоступен ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: доступен',
        'WebAPI {0}: answered, but it is not a shadNet server':
            'WebAPI {0}: отвечает, но это не сервер shadNet',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: недоступен ({1})',
        'by Super Medo': 'автор: Super Medo',
        'Add to Steam': 'Добавить в Steam',
        'The WebAPI box holds the game server address; it is ignored.':
            'В поле WebAPI указан адрес игрового сервера; он не используется.',
        '"Play online" is off: the game starts offline.':
            '«Играть онлайн» выключено: игра запустится офлайн.',
        'Could not add the game to Steam: {}': 'Не удалось добавить игру в Steam: {}',
        'DLC folder': 'Папка DLC',
        'Choose the DLC folder': 'Выберите папку DLC',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            'Ваши дампы дополнений, по папке на каждое, с именем вроде SPEXPANSIONDLC03 (The Old Hunters). Нужно только для дампа базовой игры: в издании Game of the Year (CUSA03173) оно уже есть.',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'Японская раскладка: Круг — подтверждение и действие, Крест — уклонение',
    },
    'ar': {
        'Online co-op': 'اللعب التعاوني عبر الإنترنت',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "الرسائل وبقع الدم والأشباح تأتي من خادم The Hunter's Dream، أما الأجراس والاستدعاء فتمر عبر خادم shadNet.",
        'Play online': 'العب عبر الإنترنت',
        'Off: the game stays offline, as before.': 'عند الإيقاف: تبقى اللعبة بدون إنترنت كما كانت.',
        'Game server (messages, bloodstains, ghosts)': 'خادم اللعبة (الرسائل، بقع الدم، الأشباح)',
        'Game server': 'خادم اللعبة',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "The Hunter's Dream افتراضيًا. يكفي الاسم فقط، واللعبة تختار المنافذ.",
        'Co-op server (bells and summons)': 'خادم اللعب التعاوني (الأجراس والاستدعاء)',
        'Server address': 'عنوان الخادم',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 هو خادم shadPS4 العام. لخادم خاص، أدخل host:port من الشخص الذي يشغّله.',
        'WebAPI address': 'عنوان WebAPI',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            'الخاص بخادم shadNet وليس خادم اللعبة. اتركه فارغًا ليُستخدم عنوان الخادم مع المنفذ 31315.',
        'Account': 'الحساب',
        'Online ID (NPID)': 'المعرّف (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'اسم حسابك في shadNet وليس بريدك الإلكتروني. سجّل حسابًا على shadnet.shadps4.net أو اسأل صاحب الخادم الخاص.',
        'Password': 'كلمة المرور',
        'Saved on this PC with the other launcher settings.':
            'تُحفظ على هذا الحاسوب مع باقي إعدادات المشغّل.',
        'Connection': 'الاتصال',
        'UPnP (open a port on the router automatically)': 'UPnP (فتح منفذ على الراوتر تلقائيًا)',
        'Turn it off on Tailscale or another VPN.': 'أوقفه عند استخدام Tailscale أو أي VPN.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'يجب أن يستخدم الجميع في الجلسة نفس إصدار اللعبة (1.09) ونفس الخادم. الغش يغيّر اللعبة للاعبين الآخرين أيضًا، فأوقفه عند اللعب معًا.',
        'Online': 'متصل',
        'Offline': 'غير متصل',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'أُضيفت Bloodborne إلى مكتبة Steam، وتعمل بالإعدادات المحفوظة في هذا المشغّل.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'تم إدخال حساب، لكن خيار «العب عبر الإنترنت» متوقف.\n\nنعم: العب عبر الإنترنت.   لا: العب بدون إنترنت.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            'المعرّف هو اسم الحساب (NPID) الذي سجّلته على الخادم، وليس بريدك الإلكتروني.',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            'لم يُعثر على Steam في هذا الحاسوب (أو لم يسجّل أحد الدخول إليه بعد).',
        'Game server {0}: reachable': 'خادم اللعبة {0}: متاح',
        'Server {0}: reachable': 'الخادم {0}: متاح',
        'Checking…': 'جارٍ الفحص…',
        'Test connection': 'اختبار الاتصال',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            'يجب إغلاق Steam أثناء إضافة اللعبة، ثم يُعاد تشغيله. هل تريد إغلاق Steam الآن؟',
        'Steam did not close. Close it yourself and try again.':
            'لم يُغلق Steam. أغلقه بنفسك ثم حاول مجددًا.',
        'Game server {0}: not reachable ({1})': 'خادم اللعبة {0}: غير متاح ({1})',
        'Server {0}: not reachable ({1})': 'الخادم {0}: غير متاح ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: متاح',
        'WebAPI {0}: answered, but it is not a shadNet server': 'WebAPI {0}: يستجيب، لكنه ليس خادم shadNet',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: غير متاح ({1})',
        'by Super Medo': 'بواسطة Super Medo',
        'Add to Steam': 'إضافة إلى Steam',
        'The WebAPI box holds the game server address; it is ignored.':
            'حقل WebAPI يحتوي على عنوان خادم اللعبة، ولن يُستخدم.',
        '"Play online" is off: the game starts offline.':
            'خيار «العب عبر الإنترنت» متوقف: ستبدأ اللعبة بدون إنترنت.',
        'Could not add the game to Steam: {}': 'تعذّرت إضافة اللعبة إلى Steam: {}',
        'DLC folder': 'مجلد المحتوى الإضافي',
        'Choose the DLC folder': 'اختر مجلد المحتوى الإضافي',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            'نسخ الإضافات الخاصة بك، مجلد لكل إضافة باسم مثل SPEXPANSIONDLC03 (The Old Hunters). مطلوب فقط مع نسخة اللعبة الأساسية؛ إصدار Game of the Year (CUSA03173) يتضمنها.',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'أزرار يابانية/آسيوية: الدائرة للتأكيد والتفاعل، وX للمراوغة',
    },
    'es': {
        'Online co-op': 'Cooperativo en línea',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "Los mensajes, manchas de sangre y fantasmas vienen de The Hunter's Dream; las campanas y las invocaciones pasan por un servidor shadNet.",
        'Play online': 'Jugar en línea',
        'Off: the game stays offline, as before.': 'Desactivado: el juego sigue sin conexión, como antes.',
        'Game server (messages, bloodstains, ghosts)':
            'Servidor del juego (mensajes, manchas de sangre, fantasmas)',
        'Game server': 'Servidor del juego',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "The Hunter's Dream por defecto. Basta con el nombre; el juego elige los puertos.",
        'Co-op server (bells and summons)': 'Servidor cooperativo (campanas e invocaciones)',
        'Server address': 'Dirección del servidor',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 es el servidor público de shadPS4. Para un servidor privado, escribe el host:puerto que te dé quien lo gestiona.',
        'WebAPI address': 'Dirección WebAPI',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            'La del servidor shadNet, no la del servidor del juego. Déjala vacía: se usa la dirección del servidor con el puerto 31315.',
        'Account': 'Cuenta',
        'Online ID (NPID)': 'ID en línea (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'El nombre de tu cuenta shadNet, no tu correo. Regístrate en shadnet.shadps4.net o pídesela al dueño de un servidor privado.',
        'Password': 'Contraseña',
        'Saved on this PC with the other launcher settings.':
            'Se guarda en este PC con el resto de ajustes del lanzador.',
        'Connection': 'Conexión',
        'UPnP (open a port on the router automatically)':
            'UPnP (abrir un puerto en el router automáticamente)',
        'Turn it off on Tailscale or another VPN.': 'Desactívalo con Tailscale u otra VPN.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'Todos en la sesión necesitan la misma versión del juego (1.09) y el mismo servidor. Los trucos cambian el juego también para los demás: desactívalos cuando juguéis juntos.',
        'Online': 'En línea',
        'Offline': 'Sin conexión',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne está en tu biblioteca de Steam. Se inicia con los ajustes guardados en este lanzador.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'Hay una cuenta en línea, pero «Jugar en línea» está desactivado.\n\nSí: jugar en línea.   No: jugar sin conexión.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            'El ID en línea es el nombre de cuenta (NPID) que registraste en el servidor, no tu correo.',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            'No se encontró Steam en este PC (o nadie ha iniciado sesión todavía).',
        'Game server {0}: reachable': 'Servidor del juego {0}: accesible',
        'Server {0}: reachable': 'Servidor {0}: accesible',
        'Checking…': 'Comprobando…',
        'Test connection': 'Probar la conexión',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            'Steam debe cerrarse mientras se añade el juego; después se vuelve a abrir. ¿Cerrar Steam ahora?',
        'Steam did not close. Close it yourself and try again.':
            'Steam no se cerró. Ciérralo tú y vuelve a intentarlo.',
        'Game server {0}: not reachable ({1})': 'Servidor del juego {0}: no accesible ({1})',
        'Server {0}: not reachable ({1})': 'Servidor {0}: no accesible ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: accesible',
        'WebAPI {0}: answered, but it is not a shadNet server':
            'WebAPI {0}: responde, pero no es un servidor shadNet',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: no accesible ({1})',
        'by Super Medo': 'por Super Medo',
        'Add to Steam': 'Añadir a Steam',
        'The WebAPI box holds the game server address; it is ignored.':
            'El campo WebAPI contiene la dirección del servidor del juego; se ignora.',
        '"Play online" is off: the game starts offline.':
            '«Jugar en línea» está desactivado: el juego se inicia sin conexión.',
        'Could not add the game to Steam: {}': 'No se pudo añadir el juego a Steam: {}',
        'DLC folder': 'Carpeta de DLC',
        'Choose the DLC folder': 'Elige la carpeta de DLC',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            'Tus add-ons volcados, una carpeta por cada uno con un nombre como SPEXPANSIONDLC03 (The Old Hunters). Solo hace falta con un volcado del juego base; la edición Game of the Year (CUSA03173) ya lo incluye.',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'Botones japoneses/asiáticos: Círculo confirma e interactúa, Equis esquiva',
    },
    'pt': {
        'Online co-op': 'Cooperativo online',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "Mensagens, manchas de sangue e fantasmas vêm do The Hunter's Dream; sinos e invocações passam por um servidor shadNet.",
        'Play online': 'Jogar online',
        'Off: the game stays offline, as before.': 'Desligado: o jogo continua offline, como antes.',
        'Game server (messages, bloodstains, ghosts)':
            'Servidor do jogo (mensagens, manchas de sangue, fantasmas)',
        'Game server': 'Servidor do jogo',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "The Hunter's Dream por padrão. Basta o nome; o jogo escolhe as portas.",
        'Co-op server (bells and summons)': 'Servidor cooperativo (sinos e invocações)',
        'Server address': 'Endereço do servidor',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 é o servidor público do shadPS4. Para um servidor privado, digite o host:porta de quem o administra.',
        'WebAPI address': 'Endereço WebAPI',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            'Do servidor shadNet, não do servidor do jogo. Deixe vazio: é usado o endereço do servidor com a porta 31315.',
        'Account': 'Conta',
        'Online ID (NPID)': 'ID online (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'O nome da sua conta shadNet, não o seu e-mail. Registre-se em shadnet.shadps4.net ou peça ao dono de um servidor privado.',
        'Password': 'Senha',
        'Saved on this PC with the other launcher settings.':
            'Salva neste PC com as outras configurações do launcher.',
        'Connection': 'Conexão',
        'UPnP (open a port on the router automatically)':
            'UPnP (abrir uma porta no roteador automaticamente)',
        'Turn it off on Tailscale or another VPN.': 'Desligue com Tailscale ou outra VPN.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'Todos na sessão precisam da mesma versão do jogo (1.09) e do mesmo servidor. Trapaças mudam o jogo para os outros jogadores também: desligue-as quando jogarem juntos.',
        'Online': 'Online',
        'Offline': 'Offline',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne está na sua biblioteca da Steam. Ele abre com as configurações salvas neste launcher.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'Uma conta online está preenchida, mas "Jogar online" está desligado.\n\nSim: jogar online.   Não: jogar offline.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            'O ID online é o nome da conta (NPID) registrada no servidor, não o seu e-mail.',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            'A Steam não foi encontrada neste PC (ou ninguém entrou nela ainda).',
        'Game server {0}: reachable': 'Servidor do jogo {0}: acessível',
        'Server {0}: reachable': 'Servidor {0}: acessível',
        'Checking…': 'Verificando…',
        'Test connection': 'Testar conexão',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            'A Steam precisa fechar enquanto o jogo é adicionado; depois ela abre de novo. Fechar a Steam agora?',
        'Steam did not close. Close it yourself and try again.':
            'A Steam não fechou. Feche-a você mesmo e tente de novo.',
        'Game server {0}: not reachable ({1})': 'Servidor do jogo {0}: inacessível ({1})',
        'Server {0}: not reachable ({1})': 'Servidor {0}: inacessível ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: acessível',
        'WebAPI {0}: answered, but it is not a shadNet server':
            'WebAPI {0}: respondeu, mas não é um servidor shadNet',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: inacessível ({1})',
        'by Super Medo': 'por Super Medo',
        'Add to Steam': 'Adicionar à Steam',
        'The WebAPI box holds the game server address; it is ignored.':
            'O campo WebAPI contém o endereço do servidor do jogo; ele é ignorado.',
        '"Play online" is off: the game starts offline.':
            '"Jogar online" está desligado: o jogo abre offline.',
        'Could not add the game to Steam: {}': 'Não foi possível adicionar o jogo à Steam: {}',
        'DLC folder': 'Pasta de DLC',
        'Choose the DLC folder': 'Escolha a pasta de DLC',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            'Seus add-ons extraídos, uma pasta para cada um com nome como SPEXPANSIONDLC03 (The Old Hunters). Só é necessário com um dump do jogo base; a edição Game of the Year (CUSA03173) já inclui.',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'Botões japoneses/asiáticos: Círculo confirma e interage, Xis esquiva',
    },
    'fr': {
        'Online co-op': 'Coopération en ligne',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "Les messages, taches de sang et fantômes viennent de The Hunter's Dream ; les cloches et invocations passent par un serveur shadNet.",
        'Play online': 'Jouer en ligne',
        'Off: the game stays offline, as before.': 'Désactivé : le jeu reste hors ligne, comme avant.',
        'Game server (messages, bloodstains, ghosts)': 'Serveur du jeu (messages, taches de sang, fantômes)',
        'Game server': 'Serveur du jeu',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "The Hunter's Dream par défaut. Le nom suffit ; le jeu choisit les ports.",
        'Co-op server (bells and summons)': 'Serveur de coopération (cloches et invocations)',
        'Server address': 'Adresse du serveur',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            "srv.shadps4.net:31313 est le serveur public de shadPS4. Pour un serveur privé, entrez l'hôte:port donné par la personne qui le gère.",
        'WebAPI address': 'Adresse WebAPI',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            "Celle du serveur shadNet, pas du serveur du jeu. Laissez vide : l'adresse du serveur avec le port 31315 est utilisée.",
        'Account': 'Compte',
        'Online ID (NPID)': 'ID en ligne (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            "Le nom de votre compte shadNet, pas votre e-mail. Inscrivez-vous sur shadnet.shadps4.net ou demandez au propriétaire d'un serveur privé.",
        'Password': 'Mot de passe',
        'Saved on this PC with the other launcher settings.':
            'Enregistré sur ce PC avec les autres réglages du lanceur.',
        'Connection': 'Connexion',
        'UPnP (open a port on the router automatically)':
            'UPnP (ouvrir un port sur le routeur automatiquement)',
        'Turn it off on Tailscale or another VPN.': 'Désactivez-le avec Tailscale ou un autre VPN.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            "Tous les joueurs d'une session doivent avoir la même version du jeu (1.09) et le même serveur. Les triches changent aussi le jeu des autres : désactivez-les quand vous jouez ensemble.",
        'Online': 'En ligne',
        'Offline': 'Hors ligne',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne est dans votre bibliothèque Steam. Il démarre avec les réglages enregistrés dans ce lanceur.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'Un compte en ligne est renseigné, mais « Jouer en ligne » est désactivé.\n\nOui : jouer en ligne.   Non : jouer hors ligne.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            "L'ID en ligne est le nom de compte (NPID) enregistré sur le serveur, pas votre adresse e-mail.",
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            "Steam est introuvable sur ce PC (ou personne ne s'y est encore connecté).",
        'Game server {0}: reachable': 'Serveur du jeu {0} : accessible',
        'Server {0}: reachable': 'Serveur {0} : accessible',
        'Checking…': 'Vérification…',
        'Test connection': 'Tester la connexion',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            "Steam doit être fermé pendant l'ajout du jeu ; il redémarre ensuite. Fermer Steam maintenant ?",
        'Steam did not close. Close it yourself and try again.':
            "Steam ne s'est pas fermé. Fermez-le vous-même et réessayez.",
        'Game server {0}: not reachable ({1})': 'Serveur du jeu {0} : inaccessible ({1})',
        'Server {0}: not reachable ({1})': 'Serveur {0} : inaccessible ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0} : accessible',
        'WebAPI {0}: answered, but it is not a shadNet server':
            "WebAPI {0} : répond, mais ce n'est pas un serveur shadNet",
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0} : inaccessible ({1})',
        'by Super Medo': 'par Super Medo',
        'Add to Steam': 'Ajouter à Steam',
        'The WebAPI box holds the game server address; it is ignored.':
            "Le champ WebAPI contient l'adresse du serveur du jeu ; elle est ignorée.",
        '"Play online" is off: the game starts offline.':
            '« Jouer en ligne » est désactivé : le jeu démarre hors ligne.',
        'Could not add the game to Steam: {}': "Impossible d'ajouter le jeu à Steam : {}",
        'DLC folder': 'Dossier des DLC',
        'Choose the DLC folder': 'Choisissez le dossier des DLC',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            "Vos extensions extraites, un dossier chacune nommé comme SPEXPANSIONDLC03 (The Old Hunters). Nécessaire seulement avec un dump du jeu de base ; l'édition Game of the Year (CUSA03173) l'inclut.",
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'Boutons japonais/asiatiques : Rond valide et interagit, Croix esquive',
    },
    'de': {
        'Online co-op': 'Online-Koop',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "Nachrichten, Blutflecken und Geister kommen von The Hunter's Dream; Glocken und Beschwörungen laufen über einen shadNet-Server.",
        'Play online': 'Online spielen',
        'Off: the game stays offline, as before.': 'Aus: Das Spiel bleibt wie bisher offline.',
        'Game server (messages, bloodstains, ghosts)': 'Spielserver (Nachrichten, Blutflecken, Geister)',
        'Game server': 'Spielserver',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "Standardmäßig The Hunter's Dream. Der Name genügt; die Ports wählt das Spiel.",
        'Co-op server (bells and summons)': 'Koop-Server (Glocken und Beschwörungen)',
        'Server address': 'Serveradresse',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 ist der öffentliche shadPS4-Server. Für einen privaten Server Host:Port vom Betreiber eintragen.',
        'WebAPI address': 'WebAPI-Adresse',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            'Die des shadNet-Servers, nicht des Spielservers. Leer lassen: Dann wird die Serveradresse mit Port 31315 verwendet.',
        'Account': 'Konto',
        'Online ID (NPID)': 'Online-ID (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'Dein shadNet-Kontoname, nicht deine E-Mail. Registriere dich auf shadnet.shadps4.net oder frag den Betreiber eines privaten Servers.',
        'Password': 'Passwort',
        'Saved on this PC with the other launcher settings.':
            'Wird auf diesem PC mit den anderen Launcher-Einstellungen gespeichert.',
        'Connection': 'Verbindung',
        'UPnP (open a port on the router automatically)': 'UPnP (Port am Router automatisch öffnen)',
        'Turn it off on Tailscale or another VPN.': 'Bei Tailscale oder einem anderen VPN ausschalten.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'Alle in einer Sitzung brauchen dieselbe Spielversion (1.09) und denselben Server. Cheats verändern das Spiel auch für die anderen: Schaltet sie beim gemeinsamen Spielen aus.',
        'Online': 'Online',
        'Offline': 'Offline',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne ist in deiner Steam-Bibliothek. Es startet mit den in diesem Launcher gespeicherten Einstellungen.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'Ein Online-Konto ist eingetragen, aber „Online spielen“ ist aus.\n\nJa: online spielen.   Nein: offline spielen.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            'Die Online-ID ist der auf dem Server registrierte Kontoname (NPID), nicht deine E-Mail-Adresse.',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            'Steam wurde auf diesem PC nicht gefunden (oder es hat sich noch niemand angemeldet).',
        'Game server {0}: reachable': 'Spielserver {0}: erreichbar',
        'Server {0}: reachable': 'Server {0}: erreichbar',
        'Checking…': 'Wird geprüft…',
        'Test connection': 'Verbindung testen',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            'Steam muss geschlossen werden, während das Spiel hinzugefügt wird; danach startet es wieder. Steam jetzt schließen?',
        'Steam did not close. Close it yourself and try again.':
            'Steam wurde nicht geschlossen. Schließe es selbst und versuche es erneut.',
        'Game server {0}: not reachable ({1})': 'Spielserver {0}: nicht erreichbar ({1})',
        'Server {0}: not reachable ({1})': 'Server {0}: nicht erreichbar ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: erreichbar',
        'WebAPI {0}: answered, but it is not a shadNet server':
            'WebAPI {0}: antwortet, ist aber kein shadNet-Server',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: nicht erreichbar ({1})',
        'by Super Medo': 'von Super Medo',
        'Add to Steam': 'Zu Steam hinzufügen',
        'The WebAPI box holds the game server address; it is ignored.':
            'Das WebAPI-Feld enthält die Adresse des Spielservers; sie wird ignoriert.',
        '"Play online" is off: the game starts offline.':
            '„Online spielen“ ist aus: Das Spiel startet offline.',
        'Could not add the game to Steam: {}': 'Das Spiel konnte nicht zu Steam hinzugefügt werden: {}',
        'DLC folder': 'DLC-Ordner',
        'Choose the DLC folder': 'DLC-Ordner wählen',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            'Deine gedumpten Erweiterungen, je ein Ordner mit einem Namen wie SPEXPANSIONDLC03 (The Old Hunters). Nur bei einem Dump des Grundspiels nötig; die Game of the Year Edition (CUSA03173) enthält sie.',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'Japanische/asiatische Tasten: Kreis bestätigt und interagiert, Kreuz weicht aus',
    },
    'it': {
        'Online co-op': 'Cooperativa online',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "Messaggi, macchie di sangue e fantasmi arrivano da The Hunter's Dream; campane ed evocazioni passano da un server shadNet.",
        'Play online': 'Gioca online',
        'Off: the game stays offline, as before.': 'Disattivato: il gioco resta offline, come prima.',
        'Game server (messages, bloodstains, ghosts)':
            'Server di gioco (messaggi, macchie di sangue, fantasmi)',
        'Game server': 'Server di gioco',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "The Hunter's Dream come predefinito. Basta il nome; le porte le sceglie il gioco.",
        'Co-op server (bells and summons)': 'Server cooperativo (campane ed evocazioni)',
        'Server address': 'Indirizzo del server',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 è il server pubblico di shadPS4. Per un server privato, inserisci host:porta forniti da chi lo gestisce.',
        'WebAPI address': 'Indirizzo WebAPI',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            "Quello del server shadNet, non del server di gioco. Lascia vuoto: viene usato l'indirizzo del server con la porta 31315.",
        'Account': 'Account',
        'Online ID (NPID)': 'ID online (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'Il nome del tuo account shadNet, non la tua email. Registrati su shadnet.shadps4.net o chiedi al proprietario di un server privato.',
        'Password': 'Password',
        'Saved on this PC with the other launcher settings.':
            'Salvata su questo PC con le altre impostazioni del launcher.',
        'Connection': 'Connessione',
        'UPnP (open a port on the router automatically)': 'UPnP (apri automaticamente una porta sul router)',
        'Turn it off on Tailscale or another VPN.': "Disattivalo con Tailscale o un'altra VPN.",
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'Tutti nella sessione devono avere la stessa versione del gioco (1.09) e lo stesso server. I trucchi cambiano il gioco anche per gli altri: disattivali quando giocate insieme.',
        'Online': 'Online',
        'Offline': 'Offline',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne è nella tua libreria di Steam. Si avvia con le impostazioni salvate in questo launcher.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'È inserito un account online, ma "Gioca online" è disattivato.\n\nSì: gioca online.   No: gioca offline.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            "L'ID online è il nome dell'account (NPID) registrato sul server, non il tuo indirizzo email.",
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            "Steam non è stato trovato su questo PC (o nessuno vi ha ancora effettuato l'accesso).",
        'Game server {0}: reachable': 'Server di gioco {0}: raggiungibile',
        'Server {0}: reachable': 'Server {0}: raggiungibile',
        'Checking…': 'Verifica in corso…',
        'Test connection': 'Prova la connessione',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            'Steam deve chiudersi mentre il gioco viene aggiunto; poi si riapre. Chiudere Steam ora?',
        'Steam did not close. Close it yourself and try again.':
            'Steam non si è chiuso. Chiudilo tu e riprova.',
        'Game server {0}: not reachable ({1})': 'Server di gioco {0}: non raggiungibile ({1})',
        'Server {0}: not reachable ({1})': 'Server {0}: non raggiungibile ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: raggiungibile',
        'WebAPI {0}: answered, but it is not a shadNet server':
            'WebAPI {0}: risponde, ma non è un server shadNet',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: non raggiungibile ({1})',
        'by Super Medo': 'di Super Medo',
        'Add to Steam': 'Aggiungi a Steam',
        'The WebAPI box holds the game server address; it is ignored.':
            "Il campo WebAPI contiene l'indirizzo del server di gioco; viene ignorato.",
        '"Play online" is off: the game starts offline.':
            '"Gioca online" è disattivato: il gioco parte offline.',
        'Could not add the game to Steam: {}': 'Impossibile aggiungere il gioco a Steam: {}',
        'DLC folder': 'Cartella DLC',
        'Choose the DLC folder': 'Scegli la cartella DLC',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            "I tuoi contenuti aggiuntivi estratti, una cartella ciascuno con un nome come SPEXPANSIONDLC03 (The Old Hunters). Serve solo con un dump del gioco base; l'edizione Game of the Year (CUSA03173) li include già.",
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'Tasti giapponesi/asiatici: Cerchio conferma e interagisce, Croce schiva',
    },
    'pl': {
        'Online co-op': 'Kooperacja online',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "Wiadomości, plamy krwi i duchy pochodzą z The Hunter's Dream; dzwony i przywołania idą przez serwer shadNet.",
        'Play online': 'Graj online',
        'Off: the game stays offline, as before.': 'Wyłączone: gra zostaje offline, jak dotąd.',
        'Game server (messages, bloodstains, ghosts)': 'Serwer gry (wiadomości, plamy krwi, duchy)',
        'Game server': 'Serwer gry',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "Domyślnie The Hunter's Dream. Wystarczy nazwa; porty wybiera gra.",
        'Co-op server (bells and summons)': 'Serwer kooperacji (dzwony i przywołania)',
        'Server address': 'Adres serwera',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 to publiczny serwer shadPS4. Dla serwera prywatnego wpisz host:port od osoby, która go prowadzi.',
        'WebAPI address': 'Adres WebAPI',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            'Serwera shadNet, nie serwera gry. Zostaw puste: użyty zostanie adres serwera z portem 31315.',
        'Account': 'Konto',
        'Online ID (NPID)': 'ID online (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'Nazwa twojego konta shadNet, nie e-mail. Zarejestruj się na shadnet.shadps4.net albo zapytaj właściciela prywatnego serwera.',
        'Password': 'Hasło',
        'Saved on this PC with the other launcher settings.':
            'Zapisane na tym PC razem z innymi ustawieniami launchera.',
        'Connection': 'Połączenie',
        'UPnP (open a port on the router automatically)': 'UPnP (automatycznie otwórz port na routerze)',
        'Turn it off on Tailscale or another VPN.': 'Wyłącz przy Tailscale lub innym VPN.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'Wszyscy w sesji potrzebują tej samej wersji gry (1.09) i tego samego serwera. Kody zmieniają grę także innym graczom: wyłączcie je, gdy gracie razem.',
        'Online': 'Online',
        'Offline': 'Offline',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne jest w twojej bibliotece Steam. Uruchamia się z ustawieniami zapisanymi w tym launcherze.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'Konto online jest wpisane, ale „Graj online” jest wyłączone.\n\nTak: graj online.   Nie: graj offline.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            'ID online to nazwa konta (NPID) zarejestrowanego na serwerze, a nie adres e-mail.',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            'Nie znaleziono Steam na tym PC (albo nikt się jeszcze nie zalogował).',
        'Game server {0}: reachable': 'Serwer gry {0}: dostępny',
        'Server {0}: reachable': 'Serwer {0}: dostępny',
        'Checking…': 'Sprawdzanie…',
        'Test connection': 'Sprawdź połączenie',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            'Steam musi zostać zamknięty na czas dodawania gry; potem uruchomi się ponownie. Zamknąć Steam teraz?',
        'Steam did not close. Close it yourself and try again.':
            'Steam się nie zamknął. Zamknij go sam i spróbuj ponownie.',
        'Game server {0}: not reachable ({1})': 'Serwer gry {0}: niedostępny ({1})',
        'Server {0}: not reachable ({1})': 'Serwer {0}: niedostępny ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: dostępne',
        'WebAPI {0}: answered, but it is not a shadNet server':
            'WebAPI {0}: odpowiada, ale to nie jest serwer shadNet',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: niedostępne ({1})',
        'by Super Medo': 'autor: Super Medo',
        'Add to Steam': 'Dodaj do Steam',
        'The WebAPI box holds the game server address; it is ignored.':
            'Pole WebAPI zawiera adres serwera gry; zostanie pominięte.',
        '"Play online" is off: the game starts offline.':
            '„Graj online” jest wyłączone: gra uruchomi się offline.',
        'Could not add the game to Steam: {}': 'Nie udało się dodać gry do Steam: {}',
        'DLC folder': 'Folder DLC',
        'Choose the DLC folder': 'Wybierz folder DLC',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            'Twoje zrzuty dodatków, każdy w osobnym folderze o nazwie np. SPEXPANSIONDLC03 (The Old Hunters). Potrzebne tylko przy zrzucie gry podstawowej; edycja Game of the Year (CUSA03173) już je zawiera.',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'Przyciski japońskie/azjatyckie: Kółko potwierdza i wchodzi w interakcję, Krzyżyk to unik',
    },
    'tr': {
        'Online co-op': 'Çevrim içi ortak oyun',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "Mesajlar, kan lekeleri ve hayaletler The Hunter's Dream'den gelir; çanlar ve çağırmalar bir shadNet sunucusundan geçer.",
        'Play online': 'Çevrim içi oyna',
        'Off: the game stays offline, as before.': 'Kapalı: oyun eskisi gibi çevrim dışı kalır.',
        'Game server (messages, bloodstains, ghosts)': 'Oyun sunucusu (mesajlar, kan lekeleri, hayaletler)',
        'Game server': 'Oyun sunucusu',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "Varsayılan olarak The Hunter's Dream. Yalnızca ad yeterli; bağlantı noktalarını oyun seçer.",
        'Co-op server (bells and summons)': 'Ortak oyun sunucusu (çanlar ve çağırmalar)',
        'Server address': 'Sunucu adresi',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 herkese açık shadPS4 sunucusudur. Özel bir sunucu için, onu çalıştıran kişiden aldığın host:port bilgisini gir.',
        'WebAPI address': 'WebAPI adresi',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            'Oyun sunucusunun değil, shadNet sunucusunun adresi. Boş bırak: sunucu adresi 31315 bağlantı noktasıyla kullanılır.',
        'Account': 'Hesap',
        'Online ID (NPID)': 'Çevrim içi kimlik (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'shadNet hesap adın, e-posta adresin değil. shadnet.shadps4.net üzerinden kaydol veya özel sunucunun sahibine sor.',
        'Password': 'Parola',
        'Saved on this PC with the other launcher settings.':
            'Diğer başlatıcı ayarlarıyla birlikte bu bilgisayarda saklanır.',
        'Connection': 'Bağlantı',
        'UPnP (open a port on the router automatically)':
            'UPnP (yönlendiricide otomatik bağlantı noktası aç)',
        'Turn it off on Tailscale or another VPN.': 'Tailscale veya başka bir VPN ile kapat.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'Oturumdaki herkesin aynı oyun sürümüne (1.09) ve aynı sunucuya ihtiyacı var. Hileler oyunu diğer oyuncular için de değiştirir: birlikte oynarken kapatın.',
        'Online': 'Çevrim içi',
        'Offline': 'Çevrim dışı',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne Steam kitaplığında. Bu başlatıcıda kayıtlı ayarlarla açılır.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'Bir çevrim içi hesap girilmiş, ancak "Çevrim içi oyna" kapalı.\n\nEvet: çevrim içi oyna.   Hayır: çevrim dışı oyna.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            'Çevrim içi kimlik, sunucuda kaydettiğin hesap adıdır (NPID), e-posta adresin değil.',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            'Bu bilgisayarda Steam bulunamadı (veya henüz kimse oturum açmadı).',
        'Game server {0}: reachable': 'Oyun sunucusu {0}: erişilebilir',
        'Server {0}: reachable': 'Sunucu {0}: erişilebilir',
        'Checking…': 'Denetleniyor…',
        'Test connection': 'Bağlantıyı sına',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            "Oyun eklenirken Steam'in kapanması gerekiyor; sonra yeniden açılır. Steam şimdi kapatılsın mı?",
        'Steam did not close. Close it yourself and try again.':
            'Steam kapanmadı. Kendin kapatıp yeniden dene.',
        'Game server {0}: not reachable ({1})': 'Oyun sunucusu {0}: erişilemiyor ({1})',
        'Server {0}: not reachable ({1})': 'Sunucu {0}: erişilemiyor ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: erişilebilir',
        'WebAPI {0}: answered, but it is not a shadNet server':
            'WebAPI {0}: yanıt veriyor ama bir shadNet sunucusu değil',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: erişilemiyor ({1})',
        'by Super Medo': 'Super Medo tarafından',
        'Add to Steam': "Steam'e ekle",
        'The WebAPI box holds the game server address; it is ignored.':
            'WebAPI alanında oyun sunucusunun adresi var; yok sayılıyor.',
        '"Play online" is off: the game starts offline.':
            '"Çevrim içi oyna" kapalı: oyun çevrim dışı başlar.',
        'Could not add the game to Steam: {}': "Oyun Steam'e eklenemedi: {}",
        'DLC folder': 'DLC klasörü',
        'Choose the DLC folder': 'DLC klasörünü seçin',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            'Dökümünü aldığın ek içerikler, her biri SPEXPANSIONDLC03 (The Old Hunters) gibi adlandırılmış ayrı bir klasörde. Yalnızca temel oyun dökümüyle gerekir; Game of the Year sürümü (CUSA03173) bunu zaten içerir.',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            'Japon/Asya tuşları: Daire onaylar ve etkileşir, Çarpı kaçınır',
    },
    'zh': {
        'Online co-op': '在线合作',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "留言、血迹和幽灵来自 The Hunter's Dream；铃铛和召唤通过 shadNet 服务器进行。",
        'Play online': '在线游玩',
        'Off: the game stays offline, as before.': '关闭：游戏保持离线，和以前一样。',
        'Game server (messages, bloodstains, ghosts)': '游戏服务器（留言、血迹、幽灵）',
        'Game server': '游戏服务器',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "默认为 The Hunter's Dream。只需填写名称，端口由游戏决定。",
        'Co-op server (bells and summons)': '合作服务器（铃铛和召唤）',
        'Server address': '服务器地址',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 是 shadPS4 的公共服务器。如使用私人服务器，请填写服务器管理者提供的 host:port。',
        'WebAPI address': 'WebAPI 地址',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            '这是 shadNet 服务器的地址，不是游戏服务器的。留空即可：将使用服务器地址加端口 31315。',
        'Account': '账户',
        'Online ID (NPID)': '在线 ID (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            '你的 shadNet 账户名，不是邮箱。可在 shadnet.shadps4.net 注册，或向私人服务器的管理者索取。',
        'Password': '密码',
        'Saved on this PC with the other launcher settings.': '与启动器的其他设置一起保存在这台电脑上。',
        'Connection': '连接',
        'UPnP (open a port on the router automatically)': 'UPnP（自动在路由器上打开端口）',
        'Turn it off on Tailscale or another VPN.': '使用 Tailscale 或其他 VPN 时请关闭。',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            '同一场次的所有玩家需要相同的游戏版本 (1.09) 和相同的服务器。作弊也会影响其他玩家的游戏：一起游玩时请关闭。',
        'Online': '在线',
        'Offline': '离线',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne 已加入你的 Steam 库，会使用此启动器中保存的设置启动。',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            '已填写在线账户，但“在线游玩”未开启。\n\n是：在线游玩。   否：离线游玩。',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            '在线 ID 是你在服务器上注册的账户名 (NPID)，不是邮箱地址。',
        'Steam was not found on this PC (or nobody has signed in to it yet).': '在这台电脑上找不到 Steam（或者还没有人登录过）。',
        'Game server {0}: reachable': '游戏服务器 {0}：可连接',
        'Server {0}: reachable': '服务器 {0}：可连接',
        'Checking…': '正在检查…',
        'Test connection': '测试连接',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            '添加游戏时需要关闭 Steam，之后会重新启动。现在关闭 Steam 吗？',
        'Steam did not close. Close it yourself and try again.': 'Steam 没有关闭。请手动关闭后重试。',
        'Game server {0}: not reachable ({1})': '游戏服务器 {0}：无法连接 ({1})',
        'Server {0}: not reachable ({1})': '服务器 {0}：无法连接 ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}：可连接',
        'WebAPI {0}: answered, but it is not a shadNet server': 'WebAPI {0}：有响应，但不是 shadNet 服务器',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}：无法连接 ({1})',
        'by Super Medo': '作者：Super Medo',
        'Add to Steam': '添加到 Steam',
        'The WebAPI box holds the game server address; it is ignored.': 'WebAPI 栏中填写的是游戏服务器地址，将被忽略。',
        '"Play online" is off: the game starts offline.': '“在线游玩”未开启：游戏将以离线方式启动。',
        'Could not add the game to Steam: {}': '无法将游戏添加到 Steam：{}',
        'DLC folder': 'DLC 文件夹',
        'Choose the DLC folder': '选择 DLC 文件夹',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            '你转储的追加内容，每个一个文件夹，名称如 SPEXPANSIONDLC03（The Old Hunters）。仅在使用本体游戏转储时需要；年度版（CUSA03173）已包含。',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges': '日版/亚洲版按键：圆圈键确认和互动，叉键闪避',
    },
    'ja': {
        'Online co-op': 'オンライン協力プレイ',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "メッセージ、血痕、幻影は The Hunter's Dream から届きます。鐘と召喚は shadNet サーバーを経由します。",
        'Play online': 'オンラインでプレイ',
        'Off: the game stays offline, as before.': 'オフ：これまでどおりオフラインで起動します。',
        'Game server (messages, bloodstains, ghosts)': 'ゲームサーバー（メッセージ、血痕、幻影）',
        'Game server': 'ゲームサーバー',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "既定は The Hunter's Dream。名前だけで十分で、ポートはゲームが選びます。",
        'Co-op server (bells and summons)': '協力プレイサーバー（鐘と召喚）',
        'Server address': 'サーバーアドレス',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313 は shadPS4 の公開サーバーです。プライベートサーバーの場合は、運営者から聞いた host:port を入力してください。',
        'WebAPI address': 'WebAPI アドレス',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            'ゲームサーバーではなく shadNet サーバーのものです。空欄にすると、サーバーアドレスとポート 31315 が使われます。',
        'Account': 'アカウント',
        'Online ID (NPID)': 'オンライン ID (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            'shadNet のアカウント名です（メールアドレスではありません）。shadnet.shadps4.net で登録するか、プライベートサーバーの運営者に頼んでください。',
        'Password': 'パスワード',
        'Saved on this PC with the other launcher settings.': 'ランチャーの他の設定と一緒にこの PC に保存されます。',
        'Connection': '接続',
        'UPnP (open a port on the router automatically)': 'UPnP（ルーターのポートを自動で開く）',
        'Turn it off on Tailscale or another VPN.': 'Tailscale などの VPN を使うときはオフにしてください。',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            'セッションの全員が同じゲームバージョン (1.09) と同じサーバーを使う必要があります。チートは他のプレイヤーのゲームにも影響するので、一緒に遊ぶときはオフにしてください。',
        'Online': 'オンライン',
        'Offline': 'オフライン',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne を Steam ライブラリに追加しました。このランチャーに保存された設定で起動します。',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            'オンラインアカウントが入力されていますが、「オンラインでプレイ」がオフです。\n\nはい：オンラインでプレイ。   いいえ：オフラインでプレイ。',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            'オンライン ID はサーバーに登録したアカウント名 (NPID) で、メールアドレスではありません。',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            'この PC に Steam が見つかりません（またはまだ誰もサインインしていません）。',
        'Game server {0}: reachable': 'ゲームサーバー {0}：接続可能',
        'Server {0}: reachable': 'サーバー {0}：接続可能',
        'Checking…': '確認中…',
        'Test connection': '接続テスト',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            'ゲームを追加する間は Steam を閉じる必要があり、その後また起動します。今すぐ Steam を閉じますか？',
        'Steam did not close. Close it yourself and try again.': 'Steam が閉じませんでした。手動で閉じてからもう一度お試しください。',
        'Game server {0}: not reachable ({1})': 'ゲームサーバー {0}：接続できません ({1})',
        'Server {0}: not reachable ({1})': 'サーバー {0}：接続できません ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}：接続可能',
        'WebAPI {0}: answered, but it is not a shadNet server': 'WebAPI {0}：応答はありますが shadNet サーバーではありません',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}：接続できません ({1})',
        'by Super Medo': '制作：Super Medo',
        'Add to Steam': 'Steam に追加',
        'The WebAPI box holds the game server address; it is ignored.':
            'WebAPI 欄にゲームサーバーのアドレスが入っているため、無視されます。',
        '"Play online" is off: the game starts offline.': '「オンラインでプレイ」がオフのため、オフラインで起動します。',
        'Could not add the game to Steam: {}': 'ゲームを Steam に追加できませんでした: {}',
        'DLC folder': 'DLC フォルダー',
        'Choose the DLC folder': 'DLC フォルダーを選択',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            'ダンプした追加コンテンツ。SPEXPANSIONDLC03（The Old Hunters）のような名前で 1 つずつフォルダーに入れてください。本編のダンプを使う場合のみ必要で、Game of the Year Edition（CUSA03173）には含まれています。',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges': '日本/アジア配置：○で決定・調べる、×で回避',
    },
    'ko': {
        'Online co-op': '온라인 협동',
        "Messages, bloodstains and ghosts come from The Hunter's Dream; bells and summons go through a shadNet server.":
            "메시지, 혈흔, 유령은 The Hunter's Dream에서 오고, 종과 소환은 shadNet 서버를 거칩니다.",
        'Play online': '온라인으로 플레이',
        'Off: the game stays offline, as before.': '끄면: 게임이 지금처럼 오프라인으로 실행됩니다.',
        'Game server (messages, bloodstains, ghosts)': '게임 서버 (메시지, 혈흔, 유령)',
        'Game server': '게임 서버',
        "The Hunter's Dream by default. Only the name is needed; the game picks the ports.":
            "기본값은 The Hunter's Dream입니다. 이름만 있으면 되고 포트는 게임이 고릅니다.",
        'Co-op server (bells and summons)': '협동 서버 (종과 소환)',
        'Server address': '서버 주소',
        'srv.shadps4.net:31313 is the public shadPS4 server. For a private server, enter host:port from the person who runs it.':
            'srv.shadps4.net:31313은 shadPS4 공개 서버입니다. 개인 서버라면 운영자에게 받은 host:port를 입력하세요.',
        'WebAPI address': 'WebAPI 주소',
        'Of the shadNet server, not the game server. Leave empty: the server address with port 31315 is used.':
            '게임 서버가 아니라 shadNet 서버의 주소입니다. 비워 두면 서버 주소와 포트 31315가 사용됩니다.',
        'Account': '계정',
        'Online ID (NPID)': '온라인 ID (NPID)',
        'Your shadNet account name, not your email. Register one at shadnet.shadps4.net, or ask the owner of a private server.':
            '이메일이 아닌 shadNet 계정 이름입니다. shadnet.shadps4.net에서 가입하거나 개인 서버 운영자에게 요청하세요.',
        'Password': '비밀번호',
        'Saved on this PC with the other launcher settings.': '다른 런처 설정과 함께 이 PC에 저장됩니다.',
        'Connection': '연결',
        'UPnP (open a port on the router automatically)': 'UPnP (라우터 포트 자동 열기)',
        'Turn it off on Tailscale or another VPN.': 'Tailscale이나 다른 VPN을 쓸 때는 끄세요.',
        'Everyone in a session needs the same game version (1.09) and the same server. Cheats change the game for the other players too: turn them off when you play together.':
            '세션의 모든 플레이어는 같은 게임 버전(1.09)과 같은 서버를 써야 합니다. 치트는 다른 플레이어의 게임도 바꾸니 함께 플레이할 때는 끄세요.',
        'Online': '온라인',
        'Offline': '오프라인',
        'Bloodborne is in your Steam library. It starts with the settings saved in this launcher.':
            'Bloodborne이 Steam 라이브러리에 추가되었습니다. 이 런처에 저장된 설정으로 실행됩니다.',
        'An online account is filled in, but "Play online" is off.\n\nYes: play online.   No: play offline.':
            '온라인 계정이 입력되어 있지만 "온라인으로 플레이"가 꺼져 있습니다.\n\n예: 온라인으로 플레이.   아니요: 오프라인으로 플레이.',
        'The Online ID is the account name (NPID) you registered on the server, not your email address.':
            '온라인 ID는 서버에 등록한 계정 이름(NPID)이며 이메일 주소가 아닙니다.',
        'Steam was not found on this PC (or nobody has signed in to it yet).':
            '이 PC에서 Steam을 찾을 수 없습니다 (또는 아직 아무도 로그인하지 않았습니다).',
        'Game server {0}: reachable': '게임 서버 {0}: 연결 가능',
        'Server {0}: reachable': '서버 {0}: 연결 가능',
        'Checking…': '확인 중…',
        'Test connection': '연결 테스트',
        'Steam has to close while the game is added; it starts again afterwards. Close Steam now?':
            '게임을 추가하는 동안 Steam을 닫아야 하며, 그 후 다시 실행됩니다. 지금 Steam을 닫을까요?',
        'Steam did not close. Close it yourself and try again.': 'Steam이 닫히지 않았습니다. 직접 닫은 뒤 다시 시도하세요.',
        'Game server {0}: not reachable ({1})': '게임 서버 {0}: 연결 불가 ({1})',
        'Server {0}: not reachable ({1})': '서버 {0}: 연결 불가 ({1})',
        'WebAPI {0}: reachable': 'WebAPI {0}: 연결 가능',
        'WebAPI {0}: answered, but it is not a shadNet server': 'WebAPI {0}: 응답은 있지만 shadNet 서버가 아닙니다',
        'WebAPI {0}: not reachable ({1})': 'WebAPI {0}: 연결 불가 ({1})',
        'by Super Medo': '제작: Super Medo',
        'Add to Steam': 'Steam에 추가',
        'The WebAPI box holds the game server address; it is ignored.': 'WebAPI 칸에 게임 서버 주소가 들어 있어 무시됩니다.',
        '"Play online" is off: the game starts offline.': '"온라인으로 플레이"가 꺼져 있어 오프라인으로 시작합니다.',
        'Could not add the game to Steam: {}': '게임을 Steam에 추가할 수 없습니다: {}',
        'DLC folder': 'DLC 폴더',
        'Choose the DLC folder': 'DLC 폴더 선택',
        'Your dumped add-ons, one folder each named like SPEXPANSIONDLC03 (The Old Hunters). Only needed with a base-game dump; the Game of the Year edition (CUSA03173) has it.':
            '덤프한 추가 콘텐츠를 SPEXPANSIONDLC03 (The Old Hunters) 같은 이름의 폴더에 하나씩 넣으세요. 본편 덤프를 쓸 때만 필요하며, Game of the Year 에디션(CUSA03173)에는 이미 포함되어 있습니다.',
        'Japanese/Asian buttons: Circle confirms and interacts, Cross dodges':
            '일본/아시아 버튼 배치: 동그라미로 결정·상호작용, 엑스로 회피',
    },
}
