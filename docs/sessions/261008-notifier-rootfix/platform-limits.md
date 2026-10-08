# 一手平台限制与本库计量口径

核验日期：2026-10-08。只记录官方公开文档明确写出的限制；没有明文的字段上限保留未知。

## 企业微信自定义机器人

来源：<https://developer.work.weixin.qq.com/document/path/91770>（官方“群机器人配置说明 / 自定义机器人发送消息”文档，读取页面内容 1,795,167 字节）。

- `text`：官方字段说明原文：**“文本内容，最长不超过2048个字节，必须是utf8编码”**。限制对象是解析后 `text.content` 字符串的 UTF-8 字节数，不是整个 JSON 请求体。
- `markdown_v2`：官方字段说明原文：**“markdown_v2内容，最长不超过4096个字节，必须是utf8编码。”** 限制对象是解析后 `markdown_v2.content` 字符串的 UTF-8 字节数。
- 本库分别使用 2048 字节和 3800 字节的分段预算；markdown_v2 保留低于官方 4096 字节的缓冲。页码、表头、补围栏均在此预算内。
- 没有在该文档中找到企微 JSON 整请求字节上限；此项未知，不以 PreparedRequest 大小作企微规范判断。

## 飞书自定义机器人

来源：<https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot.md>（官方“自定义机器人使用指南” Markdown 正文，HTTP 200，38,357 字节；同页面 HTML URL：<https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot>）。

- 注意事项原文：**“发送消息时，请求体的数据大小不能超过 20 KB。”** 这是整请求体限制，不是单独 Markdown 正文上限。
- 同一文档“发送飞书卡片”说明：**“发送卡片时，需要将消息体的 `content` 字符串替换为 `card` 结构体，并对整个请求消息体进行 JSON 转义。”** 示例中 `interactive` 卡片以 `card.body.elements[].content` 承载 Markdown。
- 文档没有给卡片标题、Markdown 元素各自的独立字节上限，也没有解释 KB 是十进制还是二进制；独立字段限制未知。实施按保守的十进制 20,000 body bytes 限制，涵盖卡片标题、模板、卡片包装、签名字段、页码与正文。
- 实际请求大小按 `requests.Request(..., json=...).prepare().body` 的字节数计量，并在发送前为整条计划预检。正文切分成本采用与 requests JSON 字符串字段相同的转义字节增量；成功入口测试再断言真实传输边界的 `PreparedRequest.body` 不超过 20,000 字节。没有用手工紧凑 JSON 重编码代替线上 requests 字节。

## 不作推断的项

- 飞书卡片标题字段单独长度、Markdown 渲染后长度、特殊字符渲染兼容范围：官方所引页面没有单独数值，未知。
- 企微 JSON 整请求字节数：未知。
- 飞书文档的“20 KB”是否特指 20,000 或 20,480 字节：文档未声明换算；实现选更严格的 20,000 字节，不宣称这是平台对 KB 的官方定义。
