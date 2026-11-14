"""WeChat's fixed game results; dice protocol values 4..9 mean 1..6 dots.

The content value is authoritative. A known result-image MD5 also identifies
older records which omit gameext. No random/default result is ever generated.
"""

DICE = (
    'da1c289d4e363f3ce1ff36538903b92f',
    '9e3f303561566dc9342a3ea41e6552a6',
    'dbcc51db2765c1d0106290bae6326fc4',
    '9a21c57defc4974ab5b7c842e3232671',
    '3a8e16d650f7e66ba5516b2780512830',
    '5ba8e9694b853df10b9f2a77b312cc09',
)
RPS = (
    '514914788fc461e7205bf0b6ba496c49', # scissors
    'f790e342a02e0f99d34b316547f9aeab', # rock
    '091577322c40c05aa3dd701da29d6423', # paper
)


def result(kind, number):
    values = DICE if kind=='dice' else RPS if kind=='rps' else ()
    if type(number) is not int or not 1<=number<=len(values):return None
    label='骰子：%s 点'%number if kind=='dice' else '猜拳：'+('剪刀','石头','布')[number-1]
    return {'type':kind,'value':number,'label':label,'md5':values[number-1]}


def from_hash(digest):
    if not isinstance(digest,str):return None
    digest=digest.lower()
    for kind,values in (('dice',DICE),('rps',RPS)):
        if digest in values:return result(kind,values.index(digest)+1)
    return None


def describe_game(root):
    if root is None:return None
    nodes=list(root.iter())
    for node in nodes:
        if node.tag.rsplit('}',1)[-1].lower()!='gameext':continue
        try:
            kind=int(node.get('type') or node.findtext('type') or '')
            number=int(node.get('content') or node.findtext('content') or '')
        except (ValueError,TypeError):continue
        if kind==2 and 4<=number<=9:return result('dice',number-3)
        if kind==1 and 1<=number<=3:return result('rps',number)
    for node in nodes:
        if node.tag.rsplit('}',1)[-1].lower()!='emoji':continue
        for key in ('md5','androidmd5','s60v3md5','s60v5md5'):
            found=from_hash(node.get(key))
            if found:return found
    return None
