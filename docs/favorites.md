# 收藏导出

在电脑微信打开“收藏”及需要的附件，再在 Moect 的“收藏”页面刷新资源快照。首次没有收藏库读取凭据时，需要打开微信收藏后重新连接并整理微信。支持类型、日期和关键词筛选；全选指整个筛选结果，分页不会限制导出条数。

每次导出包含 HTML 浏览页、逐条 Markdown、结构化 JSON 和可读取的附件。HTML 使用当前主题，可筛选日期、搜索、预览图片和打印。导入笔记软件时，请整体复制导出文件夹，保留 Markdown 与 resources 的相对位置，图片链接才能正常显示。收藏图片使用现有图片密钥与解码组件；收藏语音复用 SILK/WAV 转换。恢复图片读取不替代刷新收藏及语音数据库。

公众号文章正文可选联网读取，只请求微信和腾讯的公开资源地址，不使用第三方转存或代理服务。不执行网页脚本，不使用微信登录 Cookie，不自动控制微信窗口。文章失效、验证页或网络失败会明确标注并保留标题、摘要及原链接；不会将验证页当作正文。其他网站的收藏链接保留原链接，不自动抓取整站页面。

## 实现依据

- [wechat-cli 收藏读取](https://github.com/huohuoer/wechat-cli/blob/a3789232d4f79bf0b30634d9dadbce71e4acd601/wechat_cli/commands/favorites.py)：核对 Windows 微信 4.x 的 `favorite/favorite.db`、`fav_db_item` 和 XML 字段。
- [WeChatDataAnalysis 收藏解析](https://github.com/LifeArchiveProject/WeChatDataAnalysis/blob/22583491de87c574d26547e80ecbf9520419237f/src/wechat_decrypt_tool/routers/favorites.py)及[媒体匹配](https://github.com/LifeArchiveProject/WeChatDataAnalysis/blob/22583491de87c574d26547e80ecbf9520419237f/src/wechat_decrypt_tool/media_helpers.py)：核对收藏类型与聊天记录子项类型的差异，以及 `business/favorite` 不透明缓存文件的匹配方式。
- [wechat-favorites-rescue](https://github.com/tars1230/wechat-favorites-rescue)：参考文章正文与原链接分开保存的思路。其部分类型编号与本机数据库不符，未直接沿用其编号、截断长度、外部代理或解密脚本。

本项目实现以现有快照、媒体组件和本机实际库结构为准。缓存文件必须在解密后通过收藏记录中的内容 MD5 匹配，不能按不透明文件名猜测归属。收藏库以只读方式打开，导出不会改写微信数据。正文和导出页采用文本节点或结构化字段，图片密钥、CDN 凭据和本地绝对路径不进入归档。
