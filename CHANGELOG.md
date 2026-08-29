# 更新日志

## v0.1.1 (2026-08-29)

修复（维护性，免费家族「仅维护性修复」边界内）：

- **ClawHub 发布归属（关键修复）**：`publish` 生成的 clawhub 命令默认带 `--owner yottameta`
  （org handle），避免漏传导致发布到 CLI 登录的个人账号（2026-08-29 元造 / 元守曾误发到
  @gon-kvs，已用 ClawHub transfer 转移修复）；新增 `--clawhub-owner` 可覆盖归属。
- **GitHub 建仓描述上限**：gh repo create --description 上限 350 字符，package.json 长描述
  超限会报 GraphQL 错；计划自动截断（>350 → 前 347 + "..."）。
- 测试：38 → 41 用例（+2 回归：clawhub --owner 默认 / 覆盖）Python 3.8 + 3.13 双版本全绿。

## v0.1.0 (2026-08-29)

初始发布：

- 定位：元守 —— 发布前守门（0 元免费开源，工坊 / 质量与工程线）。把元阁「发布规范 + 已踩过的坑」
  固化成确定性 CLI，任何智能体照流程走不踩坑。
- CLI：零依赖（Python 3.8+ 标准库）yotta_publish_guard.py —— check（full / github / self 三档模式，
  聚合元安 / 元审 / 元信 verdict，输出发布就绪报告）/ pack（npm pack --dry-run 无 pyc、关键文件在包内，
  npm 不可用本地回退）/ versions（package / SKILL / CHANGELOG / CLI 四件对齐）/ names（npm / GitHub /
  ClawHub 三通道查重，网络失败降级提示）/ publish（默认 dry-run 打印计划，--exec 执行，--force 显式
  跳过推送闸门；--channels / --github-only 渠道可选；发布计划对含空格/引号的值自动加引号
  （--name '元X yotta-x' / -m '...' / --description '...'，修复 ClawHub --name 未加引号被拆参的坑）。
- 推送闸门：未通过校验默认阻断；网络命令优雅降级，不伪造结果；只读（不修改被测技能目录）。
- references：check-items.md（校验项明细）/ publish-flow.md（三源发布流程与已踩坑清单）/ tutorial.md（中文教程）。
- 测试：38 用例（三档模式 / 版本四件 / pack / names / 渠道 / 闸门 / 回归 / 发布计划引号渲染）Python 3.8 + 3.13 双版本全绿。
- 文档：SKILL.md + README 中英双版 + 四方式安装（发布规范 §3.3.1）。
